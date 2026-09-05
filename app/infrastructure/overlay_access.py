import sqlite3
from datetime import UTC, datetime
from typing import cast


def rotate_overlay_access_key(
    connection: sqlite3.Connection,
    streamer_id: str,
    plugin_slug: str,
    token_hash: str,
) -> None:
    now = datetime.now(UTC).isoformat()

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO overlay_access_keys (
                streamer_id,
                plugin_slug,
                token_hash,
                created_at,
                rotated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (streamer_id, plugin_slug) DO UPDATE SET
                token_hash = excluded.token_hash,
                rotated_at = excluded.rotated_at
            """,
            (
                streamer_id,
                plugin_slug,
                token_hash,
                now,
                now,
            ),
        )
        cursor.close()


def resolve_overlay_access_key(
    connection: sqlite3.Connection,
    plugin_slug: str,
    token_hash: str,
) -> str | None:
    cursor = connection.execute(
        """
        SELECT streamer_id
        FROM overlay_access_keys
        WHERE plugin_slug = ? AND token_hash = ?
        LIMIT 1
        """,
        (
            plugin_slug,
            token_hash,
        ),
    )
    row = cast(sqlite3.Row | None, cursor.fetchone())
    cursor.close()

    if row is None:
        return None

    return cast(str, row["streamer_id"])


def load_overlay_access_key_rotated_at(
    connection: sqlite3.Connection,
    streamer_id: str,
    plugin_slug: str,
) -> str | None:
    cursor = connection.execute(
        """
        SELECT rotated_at
        FROM overlay_access_keys
        WHERE streamer_id = ? AND plugin_slug = ?
        LIMIT 1
        """,
        (
            streamer_id,
            plugin_slug,
        ),
    )
    row = cast(sqlite3.Row | None, cursor.fetchone())
    cursor.close()

    if row is None:
        return None

    return cast(str, row["rotated_at"])
