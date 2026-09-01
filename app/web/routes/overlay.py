from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.domain.giveaway import GiveawayEngine
from app.web.websocket import OverlayConnectionManager


def create_overlay_router(
    engine: GiveawayEngine,
    connections: OverlayConnectionManager,
    static_directory: Path,
) -> APIRouter:
    router = APIRouter()

    @router.get("/overlay", response_class=FileResponse)
    def overlay() -> FileResponse:
        return FileResponse(static_directory / "overlay.html")

    @router.get("/api/state")
    def giveaway_state() -> dict[str, object]:
        return engine.snapshot()

    @router.websocket("/ws/overlay")
    async def overlay_websocket(websocket: WebSocket) -> None:
        await connections.connect(websocket)

        try:
            await connections.send_state(
                websocket,
                engine.snapshot(),
            )

            while True:
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            connections.disconnect(websocket)

    return router
