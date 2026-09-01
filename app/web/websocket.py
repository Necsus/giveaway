from fastapi import WebSocket, WebSocketDisconnect


class OverlayConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

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

        for websocket in self._connections:
            try:
                await self.send_state(websocket, state)
            except (RuntimeError, WebSocketDisconnect):
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)
