from fastapi import WebSocket, WebSocketDisconnect


class OverlayConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, str | None] = {}

    def register(self, websocket: WebSocket, streamer_id: str | None = None) -> None:
        self._connections[websocket] = streamer_id

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def disconnect_streamer(self, streamer_id: str) -> None:
        streamers_connections = [
            websocket
            for websocket, connection_streamer_id in self._connections.items()
            if connection_streamer_id == streamer_id
        ]

        for websocket in streamers_connections:
            try:
                await websocket.close(code=1008)
            except (RuntimeError, WebSocketDisconnect):
                pass

            self.disconnect(websocket)

    async def send_state(
        self,
        websocket: WebSocket,
        state: dict[str, object],
    ) -> None:
        await websocket.send_json(
            {
                "type": "giveaway.state",
                "data": state,
            }
        )

    async def broadcast(self, state: dict[str, object]) -> None:
        disconnected: list[WebSocket] = []

        for websocket in list(self._connections):
            try:
                await self.send_state(websocket, state)
            except (RuntimeError, WebSocketDisconnect):
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)
