import asyncio
import sqlite3
from pathlib import Path
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.application.overlay_access import (
    GIVEAWAY_PLUGIN_SLUG,
    hash_overlay_token,
    parse_overlay_authentication,
)
from app.domain.giveaway import GiveawayEngine
from app.infrastructure.overlay_access import resolve_overlay_access_key
from app.infrastructure.streamers import load_active_streamer
from app.web.websocket import OverlayConnectionManager


def create_overlay_router(
    engine: GiveawayEngine,
    connections: OverlayConnectionManager,
    static_directory: Path,
) -> APIRouter:
    router = APIRouter()

    @router.get("/plugins/giveaway/overlay", response_class=FileResponse)
    def overlay() -> FileResponse:
        return FileResponse(static_directory / "overlay.html")

    async def serve_registered_overlay(websocket: WebSocket) -> None:
        try:
            await connections.send_state(
                websocket,
                engine.snapshot(),
            )

            while True:
                _ = await websocket.receive_text()
        except (RuntimeError, WebSocketDisconnect):
            connections.disconnect(websocket)

    async def authenticate_giveaway_overlay(
        websocket: WebSocket,
    ) -> bool:
        await websocket.accept()

        try:
            async with asyncio.timeout(5):
                message: object = await websocket.receive_json()
        except WebSocketDisconnect:
            return False
        except (TimeoutError, ValueError):
            await websocket.close(code=1008)
            return False

        token = parse_overlay_authentication(message)
        if token is None:
            await websocket.close(code=1008)
            return False

        token_hash = hash_overlay_token(token)
        connection = cast(
            sqlite3.Connection,
            websocket.app.state.database_connection,
        )

        try:
            streamer_id = resolve_overlay_access_key(
                connection,
                plugin_slug=GIVEAWAY_PLUGIN_SLUG,
                token_hash=token_hash,
            )
            active_streamer = load_active_streamer(connection)
        except sqlite3.Error:
            await websocket.close(code=1011)
            return False

        if (
            streamer_id is None
            or active_streamer is None
            or streamer_id != active_streamer.twitch_user_id
        ):
            await websocket.close(code=1008)
            return False

        connections.register(
            websocket,
            streamer_id=streamer_id,
        )
        return True

    @router.websocket("/plugins/giveaway/ws")
    async def giveaway_overlay_websocket(websocket: WebSocket) -> None:
        if not await authenticate_giveaway_overlay(websocket):
            return

        await serve_registered_overlay(websocket)

    return router
