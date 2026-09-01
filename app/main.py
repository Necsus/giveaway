import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.application.commands import GiveawayCommandHandler
from app.application.service import GiveawayService
from app.core.environment import Settings
from app.domain.giveaway import GiveawayEngine
from app.infrastructure.database import connect_database, initialize_database
from app.infrastructure.history import restore_active_giveaway
from app.infrastructure.twitch import GiveawayTwitchBot
from app.web.routes.health import router as health_router
from app.web.routes.overlay import create_overlay_router
from app.web.websocket import OverlayConnectionManager

STATIC_DIRECTORY = Path(__file__).parent / "web" / "static"

giveaway_engine = GiveawayEngine()
overlay_connections = OverlayConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()  # pyright: ignore[reportCallIssue]

    connection = connect_database()
    initialize_database(connection)
    _ = restore_active_giveaway(connection, giveaway_engine)

    giveaway_service = GiveawayService(
        giveaway_engine,
        connection,
        overlay_connections,
    )

    app.state.settings = settings
    app.state.giveaway_service = giveaway_service

    giveaway_command_handler = GiveawayCommandHandler(
        service=giveaway_service,
        broadcaster_id=settings.twitch_broadcaster_id,
        prefix=settings.twitch_command_prefix,
    )

    app.state.giveaway_command_handler = giveaway_command_handler

    twitch_bot: GiveawayTwitchBot | None = None
    twitch_task: asyncio.Task[None] | None = None

    if settings.twitch_enabled:
        twitch_bot = GiveawayTwitchBot(
            settings=settings,
            command_handler=giveaway_command_handler,
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
            connection.close()


app = FastAPI(title="Twitch Giveaway Overlay", lifespan=lifespan)
app.include_router(health_router)
app.include_router(
    create_overlay_router(
        giveaway_engine,
        overlay_connections,
        STATIC_DIRECTORY,
    )
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")
