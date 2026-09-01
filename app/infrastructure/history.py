import sqlite3
from datetime import UTC, datetime
from typing import cast

from app.domain.giveaway import GiveawayEngine, GiveawayState, Participant


def create_giveaway(connection: sqlite3.Connection, giveaway_id: str, lot: str) -> None:
    created_at = datetime.now(UTC).isoformat()

    cursor = connection.execute(
        """
        INSERT INTO giveaways (id, lot, status, created_at)
        VALUES (?, ?, 'WAITING', ?)
        """,
        (giveaway_id, lot, created_at),
    )
    cursor.close()
    connection.commit()


def open_giveaway(connection: sqlite3.Connection, giveaway_id: str) -> None:
    opened_at = datetime.now(UTC).isoformat()

    cursor = connection.execute(
        """
        UPDATE giveaways
        SET status = 'OPEN', opened_at = ?
        WHERE id = ? AND status = 'WAITING'
        """,
        (opened_at, giveaway_id),
    )

    updated_rows = cursor.rowcount
    cursor.close()

    if updated_rows != 1:
        connection.rollback()
        raise RuntimeError("The giveaway is not waiting")

    connection.commit()


def add_participant(
    connection: sqlite3.Connection,
    giveaway_id: str,
    participant: Participant,
) -> bool:
    joined_at = datetime.now(UTC).isoformat()

    cursor = connection.execute(
        """
        INSERT INTO participants (
            giveaway_id,
            twitch_user_id,
            login,
            display_name,
            joined_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (giveaway_id, twitch_user_id) DO NOTHING
        """,
        (
            giveaway_id,
            participant.twitch_user_id,
            participant.login,
            participant.display_name,
            joined_at,
        ),
    )
    was_added = cursor.rowcount == 1
    cursor.close()
    connection.commit()

    return was_added


def draw_giveaway(
    connection: sqlite3.Connection,
    giveaway_id: str,
    winner: Participant,
) -> None:
    drawn_at = datetime.now(UTC).isoformat()

    cursor = connection.execute(
        """
        UPDATE giveaways
        SET
            status = 'WINNER',
            drawn_at = ?,
            winner_user_id = ?,
            winner_display_name = ?
        WHERE id = ? AND status = 'OPEN'
        """,
        (drawn_at, winner.twitch_user_id, winner.display_name, giveaway_id),
    )
    updated_rows = cursor.rowcount
    cursor.close()

    if updated_rows != 1:
        connection.rollback()
        raise RuntimeError("The giveaway is not open")

    connection.commit()


def stop_giveaway(
    connection: sqlite3.Connection,
    giveaway_id: str,
) -> None:
    stopped_at = datetime.now(UTC).isoformat()

    cursor = connection.execute(
        """
        UPDATE giveaways
        SET
            status = CASE
                WHEN status = 'WINNER' THEN 'COMPLETED'
                ELSE 'CANCELLED'
            END,
            stopped_at = ?
        WHERE id = ?
            AND status IN ('WAITING', 'OPEN', 'WINNER')
        """,
        (stopped_at, giveaway_id),
    )
    updated_rows = cursor.rowcount
    cursor.close()

    if updated_rows != 1:
        connection.rollback()
        raise RuntimeError("There is no active giveaway")

    connection.commit()


def restore_active_giveaway(
    connection: sqlite3.Connection,
    engine: GiveawayEngine,
) -> bool:
    cursor = connection.execute(
        """
        SELECT id, lot, status, winner_user_id
        FROM giveaways
        WHERE status IN ('WAITING', 'OPEN', 'WINNER')
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    giveaway_row = cast(sqlite3.Row | None, cursor.fetchone())
    cursor.close()

    if giveaway_row is None:
        return False

    giveaway_id = cast(str, giveaway_row["id"])

    cursor = connection.execute(
        """
        SELECT twitch_user_id, login, display_name
        FROM participants
        WHERE giveaway_id = ?
        ORDER BY joined_at, id
        """,
        (giveaway_id,),
    )
    participant_rows = cast(list[sqlite3.Row], cursor.fetchall())
    cursor.close()

    participants = [
        Participant(
            twitch_user_id=cast(str, row["twitch_user_id"]),
            login=cast(str, row["login"]),
            display_name=cast(str, row["display_name"]),
        )
        for row in participant_rows
    ]

    engine.restore(
        giveaway_id=giveaway_id,
        lot=cast(str, giveaway_row["lot"]),
        state=GiveawayState(cast(str, giveaway_row["status"])),
        participants=participants,
        winner_user_id=cast(str | None, giveaway_row["winner_user_id"]),
    )

    return True
