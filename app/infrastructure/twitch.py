import logging

from twitchio import ChatMessage, authentication, eventsub
from twitchio.ext import commands

from app.application.commands import ChatUser, GiveawayCommandHandler
from app.core.configuration import ApplicationConfiguration
from app.core.environment import Settings

LOGGER = logging.getLogger("uvicorn.error")


class GiveawayTwitchBot(commands.AutoBot):
    def __init__(
        self,
        settings: Settings,
        configuration: ApplicationConfiguration,
        command_handler: GiveawayCommandHandler,
    ) -> None:
        twitch_configuration = configuration.twitch

        subscription = eventsub.ChatMessageSubscription(
            broadcaster_user_id=twitch_configuration.broadcaster_id,
            user_id=twitch_configuration.bot_id,
        )

        super().__init__(
            client_id=settings.twitch_client_id,
            client_secret=settings.twitch_client_secret.get_secret_value(),
            bot_id=twitch_configuration.bot_id,
            owner_id=twitch_configuration.owner_id,
            prefix=configuration.commands.prefix,
            subscriptions=[subscription],
            force_subscribe=True,
        )

        self._command_handler = command_handler

    async def event_message(self, payload: ChatMessage) -> None:
        login = payload.chatter.name or payload.chatter.id
        display_name = payload.chatter.display_name or login

        author = ChatUser(
            twitch_user_id=payload.chatter.id,
            login=login,
            display_name=display_name,
        )

        await self._command_handler.handle(payload.text, author)

    async def event_oauth_authorized(
        self,
        payload: authentication.UserTokenPayload,
    ) -> None:
        LOGGER.info(
            "Twitch user authorized: login=%s id=%s",
            payload.user_login,
            payload.user_id,
        )

        await self.add_token(
            payload.access_token,
            payload.refresh_token,
        )
