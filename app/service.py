import asyncio
import sqlite3

from app.giveaway import GiveawayEngine, Participant
from app.history import (
    add_participant,
    create_giveaway,
    draw_giveaway,
    open_giveaway,
    stop_giveaway,
)
from app.websocket import OverlayConnectionManager


class GiveawayService:
    def __init__(
        self,
        engine: GiveawayEngine,
        connection: sqlite3.Connection,
        overlay_connections: OverlayConnectionManager,
    ) -> None:
        self._engine: GiveawayEngine = engine
        self._connection: sqlite3.Connection = connection
        self._overlay_connections: OverlayConnectionManager = overlay_connections
        self._lock: asyncio.Lock = asyncio.Lock()

    async def set_lot(self, lot: str) -> None:
        async with self._lock:
            self._engine.set_lot(lot)

            giveaway_id = self._engine.giveaway_id
            cleaned_lot = self._engine.lot

            if giveaway_id is None or cleaned_lot is None:
                raise RuntimeError("The giveaway was not initialized correctly")

            create_giveaway(
                self._connection,
                giveaway_id,
                cleaned_lot,
            )

            await self._broadcast_state()

    async def start(self) -> None:
        async with self._lock:
            giveaway_id = self._active_giveaway_id()

            self._engine.start()
            open_giveaway(self._connection, giveaway_id)

            await self._broadcast_state()

    async def join(self, participant: Participant) -> bool:
        async with self._lock:
            giveaway_id = self._active_giveaway_id()

            was_added = self._engine.join(participant)
            if not was_added:
                return False

            was_persisted = add_participant(
                self._connection,
                giveaway_id,
                participant,
            )
            if not was_persisted:
                raise RuntimeError("The participant already exists in the history")

            await self._broadcast_state()
            return True

    async def pull(self) -> Participant:
        async with self._lock:
            giveaway_id = self._active_giveaway_id()

            winner = self._engine.pull()
            draw_giveaway(self._connection, giveaway_id, winner)

            await self._broadcast_state()
            return winner

    async def stop(self) -> None:
        async with self._lock:
            giveaway_id = self._active_giveaway_id()

            stop_giveaway(self._connection, giveaway_id)
            self._engine.stop()

            await self._broadcast_state()

    def _active_giveaway_id(self) -> str:
        giveaway_id = self._engine.giveaway_id
        if giveaway_id is None:
            raise RuntimeError("There is no active giveaway")

        return giveaway_id

    async def _broadcast_state(self) -> None:
        await self._overlay_connections.broadcast(self._engine.snapshot())
