from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.commands import GiveawayCommandHandler
from app.database import connect_database, initialize_database
from app.giveaway import GiveawayEngine
from app.history import restore_active_giveaway
from app.service import GiveawayService
from app.settings import Settings
from app.websocket import OverlayConnectionManager

STATIC_DIRECTORY = Path(__file__).parent / "static"

giveaway_engine = GiveawayEngine()
overlay_connections = OverlayConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()

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
    app.state.giveaway_command_handler = GiveawayCommandHandler(
        service=giveaway_service,
        broadcaster_id=settings.twitch_broadcaster_id,
        prefix=settings.twitch_command_prefix,
    )

    try:
        yield
    finally:
        connection.close()


app = FastAPI(title="Twitch Giveaway Overlay", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/overlay", response_class=FileResponse)
def overlay() -> FileResponse:
    return FileResponse(STATIC_DIRECTORY / "overlay.html")


@app.get("/api/state")
def giveaway_state() -> dict[str, object]:
    return giveaway_engine.snapshot()


@app.websocket("/ws/overlay")
async def overlay_websocket(websocket: WebSocket) -> None:
    await overlay_connections.connect(websocket)

    try:
        await overlay_connections.send_state(
            websocket,
            giveaway_engine.snapshot(),
        )

        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        overlay_connections.disconnect(websocket)
