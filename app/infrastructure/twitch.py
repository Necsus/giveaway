import asyncio
import logging

from twitchio import ChatMessage, authentication, eventsub
from twitchio.ext import commands
from typing_extensions import override

from app.application.commands import ChatUser, GiveawayCommandHandler
from app.core.configuration import ApplicationConfiguration
from app.core.environment import Settings
from app.infrastructure.twitch_oauth import TwitchAuthorization

LOGGER = logging.getLogger("uvicorn.error")

BOT_SCOPES = authentication.Scopes(
    user_read_chat=True,
    user_write_chat=True,
    user_bot=True,
)


class GiveawayTwitchBot(commands.AutoBot):
    def __init__(
        self,
        settings: Settings,
        configuration: ApplicationConfiguration,
        command_handler: GiveawayCommandHandler,
    ) -> None:
        twitch_configuration = configuration.twitch

        super().__init__(
            client_id=settings.twitch_client_id,
            client_secret=settings.twitch_client_secret.get_secret_value(),
            bot_id=twitch_configuration.bot_id,
            owner_id=twitch_configuration.owner_id,
            prefix=configuration.commands.prefix,
            scopes=BOT_SCOPES,
        )

        self._command_handler: GiveawayCommandHandler = command_handler
        self._subscription_lock: asyncio.Lock = asyncio.Lock()
        self._active_broadcaster_id: str | None = None
        self._chat_subscription_id: str | None = None

    async def subscribe_to_streamer(
        self,
        authorization: TwitchAuthorization,
    ) -> None:
        validated_token = await self.add_token(
            authorization.access_token,
            authorization.refresh_token,
        )

        if validated_token.user_id != authorization.twitch_user_id:
            if validated_token.user_id is not None:
                _ = await self.remove_token(validated_token.user_id)

            raise ValueError(
                "The added Twitch token does not match the streamer identity"
            )

        async with self._subscription_lock:
            if (
                self._active_broadcaster_id == authorization.twitch_user_id
                and self._chat_subscription_id is not None
            ):
                return

            previous_subscription_id = self._chat_subscription_id

            # Bloque immédiatement les évènements de l'ancien canal
            self._active_broadcaster_id = None
            self._chat_subscription_id = None

            if previous_subscription_id is not None:
                await self.delete_eventsub_subscription(previous_subscription_id)

            subscription = eventsub.ChatMessageSubscription(
                broadcaster_user_id=authorization.twitch_user_id,
                user_id=self.bot_id,
            )

            result = await self.multi_subscribe(
                [subscription],
                wait=True,
                stop_on_error=True,
            )

            if len(result.success) != 1:
                raise RuntimeError("Twitch did not create the chat subscription")

            response_data = result.success[0].response["data"]
            if len(response_data) != 1:
                raise RuntimeError("Twitch returned an invalid subscription response")

            subscription_id = response_data[0]["id"]
            if not subscription_id:
                raise RuntimeError("Twitch returned an empty subscription ID")

            self._chat_subscription_id = subscription_id
            self._active_broadcaster_id = authorization.twitch_user_id

    @override
    async def event_message(self, payload: ChatMessage) -> None:
        if payload.broadcaster.id != self._active_broadcaster_id:
            LOGGER.debug(
                "Ignoring Twitch message from inactive broadcaster: broadcaster_id=%s",
                payload.broadcaster.id,
            )
            return

        login = payload.chatter.name or payload.chatter.id
        display_name = payload.chatter.display_name or login

        author = ChatUser(
            twitch_user_id=payload.chatter.id,
            login=login,
            display_name=display_name,
        )

        _ = await self._command_handler.handle(payload.text, author)

    @override
    async def event_oauth_authorized(
        self,
        payload: authentication.UserTokenPayload,
    ) -> None:
        if payload.user_id != self.bot_id:
            LOGGER.warning(
                "Ignoring OAuth authorization for unexpected Twitch user: id=%s",
                payload.user_id,
            )
            return

        LOGGER.info(
            "Twitch user authorized: login=%s id=%s",
            payload.user_login,
            payload.user_id,
        )

        _ = await self.add_token(
            payload.access_token,
            payload.refresh_token,
        )
