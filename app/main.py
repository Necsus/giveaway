import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.application.commands import GiveawayCommandHandler
from app.application.oauth_state import OAuthStateStore
from app.application.service import GiveawayService
from app.application.session import SessionSigner
from app.core.configuration import configuration_from_settings
from app.core.environment import Settings
from app.domain.giveaway import GiveawayEngine
from app.infrastructure.configuration_store import ConfigurationStore
from app.infrastructure.database import connect_database, initialize_database
from app.infrastructure.history import restore_active_giveaway
from app.infrastructure.streamers import load_active_streamer
from app.infrastructure.twitch import GiveawayTwitchBot
from app.infrastructure.twitch_oauth import TwitchOAuthClient
from app.web.routes.admin import router as admin_router
from app.web.routes.auth import router as auth_router
from app.web.routes.health import router as health_router
from app.web.routes.overlay import create_overlay_router
from app.web.websocket import OverlayConnectionManager

STATIC_DIRECTORY = Path(__file__).parent / "web" / "static"

giveaway_engine = GiveawayEngine()
overlay_connections = OverlayConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()  # pyright: ignore[reportCallIssue]

    session_signer = SessionSigner(
        secret_key=settings.session_secret.get_secret_value(),
        max_age_seconds=settings.session_max_age_seconds,
    )

    twitch_oauth_client = TwitchOAuthClient(
        client_id=settings.twitch_client_id,
        client_secret=settings.twitch_client_secret.get_secret_value(),
        redirect_uri=settings.twitch_admin_redirect_uri,
    )

    configuration_store = ConfigurationStore(settings.giveaway_config_file)
    configuration = configuration_store.load()
    if configuration is None:
        configuration = configuration_from_settings(settings)
        configuration_store.save(configuration)

    connection = connect_database()
    initialize_database(connection)

    active_streamer = load_active_streamer(connection)
    _ = restore_active_giveaway(connection, giveaway_engine)

    giveaway_service = GiveawayService(
        giveaway_engine,
        connection,
        overlay_connections,
    )

    app.state.settings = settings
    app.state.database_connection = connection
    app.state.configuration = configuration
    app.state.configuration_store = configuration_store
    app.state.session_signer = session_signer
    app.state.oauth_state_store = OAuthStateStore()
    app.state.twitch_oauth_client = twitch_oauth_client
    app.state.giveaway_service = giveaway_service

    giveaway_command_handler = GiveawayCommandHandler(
        service=giveaway_service,
        prefix=configuration.commands.prefix,
    )

    if active_streamer is not None:
        giveaway_command_handler.set_active_broadcaster(
            active_streamer.twitch_user_id,
        )

    app.state.giveaway_command_handler = giveaway_command_handler

    twitch_bot: GiveawayTwitchBot | None = None
    twitch_task: asyncio.Task[None] | None = None

    if configuration.twitch.enabled or settings.twitch_oauth_enabled:
        twitch_bot = GiveawayTwitchBot(
            settings=settings,
            configuration=configuration,
            command_handler=giveaway_command_handler,
            active_broadcaster_id=(
                active_streamer.twitch_user_id if active_streamer is not None else None
            ),
        )
        twitch_task = asyncio.create_task(
            twitch_bot.start(
                with_adapter=settings.twitch_oauth_enabled,
            ),
            name="twitch-bot",
        )

    app.state.twitch_bot = twitch_bot

    try:
        yield
    finally:
        try:
            if twitch_bot is not None:
                await twitch_bot.close()

            if twitch_task is not None:
                await twitch_task
        finally:
            try:
                await twitch_oauth_client.close()
            finally:
                connection.close()


app = FastAPI(title="Twitch Giveaway Overlay", lifespan=lifespan)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(
    create_overlay_router(
        giveaway_engine,
        overlay_connections,
        STATIC_DIRECTORY,
    )
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")
