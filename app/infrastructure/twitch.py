import asyncio
import logging

from twitchio import ChatMessage, authentication, eventsub
from twitchio.ext import commands
from typing_extensions import override

from app.application.commands import ChatUser, GiveawayCommandHandler
from app.core.configuration import ApplicationConfiguration
from app.core.environment import Settings
from app.infrastructure.twitch_oauth import BOT_SCOPE_NAMES, TwitchAuthorization

LOGGER = logging.getLogger("uvicorn.error")

BOT_SCOPES = authentication.Scopes(BOT_SCOPE_NAMES)


class GiveawayTwitchBot(commands.AutoBot):
    def __init__(
        self,
        settings: Settings,
        configuration: ApplicationConfiguration,
        command_handler: GiveawayCommandHandler,
        active_broadcaster_id: str | None,
    ) -> None:
        twitch_configuration = configuration.twitch

        subscriptions: list[eventsub.SubscriptionPayload] = []

        if active_broadcaster_id is not None:
            subscriptions.append(
                eventsub.ChatMessageSubscription(
                    broadcaster_user_id=active_broadcaster_id,
                    user_id=twitch_configuration.bot_id,
                )
            )

        super().__init__(
            client_id=settings.twitch_client_id,
            client_secret=settings.twitch_client_secret.get_secret_value(),
            bot_id=twitch_configuration.bot_id,
            owner_id=twitch_configuration.owner_id,
            prefix=configuration.commands.prefix,
            scopes=BOT_SCOPES,
            subscriptions=subscriptions,
        )

        self._command_handler: GiveawayCommandHandler = command_handler
        self._subscription_lock: asyncio.Lock = asyncio.Lock()
        self._active_broadcaster_id: str | None = active_broadcaster_id
        self._chat_subscription_id: str | None = None

    @property
    def chat_subscription_ready(self) -> bool:
        return (
            self._active_broadcaster_id is not None
            and self._chat_subscription_id is not None
        )

    async def authorize_bot(self, authorization: TwitchAuthorization) -> None:
        if authorization.twitch_user_id != self.bot_id:
            raise ValueError("The Twitch authorization does not belong to the bot")

        if not BOT_SCOPE_NAMES.issubset(authorization.scopes):
            raise ValueError("The Twitch bot authorization is missing a required scope")

        validated_token = await self.add_token(
            authorization.access_token,
            authorization.refresh_token,
        )
        if validated_token.user_id != self.bot_id:
            if validated_token.user_id is not None:
                _ = await self.remove_token(validated_token.user_id)

            raise ValueError("The added Twitch token does not belong to the bot")

        await self.save_tokens()
        LOGGER.info("Twitch bot authorization saved: bot_id=%s", self.bot_id)

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

            # Bloque immédiatement les évènements de l'ancien canal.
            self._active_broadcaster_id = None
            self._chat_subscription_id = None

            existing_subscription_id = await self._reconcile_chat_subscriptions(
                authorization.twitch_user_id
            )
            if existing_subscription_id is not None:
                self._chat_subscription_id = existing_subscription_id
                self._active_broadcaster_id = authorization.twitch_user_id
                return

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

    async def _reconcile_chat_subscriptions(
        self,
        broadcaster_id: str,
    ) -> str | None:
        conduit = self.conduit_info.conduit
        if conduit is None:
            raise RuntimeError("No Twitch conduit is available")

        result = await self.fetch_eventsub_subscriptions(
            conduit_id=conduit.id,
        )
        matching_subscription_id: str | None = None
        stale_subscription_ids: list[str] = []

        async for subscription in result.subscriptions:
            if (
                subscription.status != "enabled"
                or subscription.type != "channel.chat.message"
                or subscription.condition.get("user_id") != self.bot_id
            ):
                continue

            if (
                subscription.condition.get("broadcaster_user_id") == broadcaster_id
                and matching_subscription_id is None
            ):
                matching_subscription_id = subscription.id
            else:
                stale_subscription_ids.append(subscription.id)

        for subscription_id in stale_subscription_ids:
            await self.delete_eventsub_subscription(subscription_id)

        if stale_subscription_ids:
            LOGGER.info(
                "Removed stale Twitch chat subscriptions: count=%d",
                len(stale_subscription_ids),
            )

        return matching_subscription_id

    @override
    async def setup_hook(self) -> None:
        await super().setup_hook()

        broadcaster_id = self._active_broadcaster_id
        if broadcaster_id is None:
            return

        conduit = self.conduit_info.conduit
        if conduit is None:
            LOGGER.warning("Unable to restore Twitch chat: no conduit available")
            return

        existing_subscription_id = await self._reconcile_chat_subscriptions(
            broadcaster_id
        )
        if existing_subscription_id is not None:
            self._chat_subscription_id = existing_subscription_id
            LOGGER.info(
                "Restored Twitch chat subscription: broadcaster_id=%s",
                broadcaster_id,
            )
            return

        chat_subscription = eventsub.ChatMessageSubscription(
            broadcaster_user_id=broadcaster_id,
            user_id=self.bot_id,
        )

        result = await self.multi_subscribe(
            [chat_subscription],
            wait=True,
            stop_on_error=False,
        )

        if len(result.success) != 1:
            LOGGER.warning(
                "Unable to recreate Twitch chat subscription: broadcaster_id=%s error=%d",
                broadcaster_id,
                len(result.errors),
            )
            return

        response_data = result.success[0].response["data"]
        if len(response_data) != 1 or not response_data[0]["id"]:
            LOGGER.warning(
                "Twitch returned an invalid chat subscription response: broadcaster_id=%s",
                broadcaster_id,
            )
            return

        self._chat_subscription_id = response_data[0]["id"]

        LOGGER.info(
            "Recreated Twitch chat subscription: broadcaster_id=%s", broadcaster_id
        )
