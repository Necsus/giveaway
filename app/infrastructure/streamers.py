import sqlite3
from datetime import UTC, datetime
from typing import cast

from app.domain.streamer import Streamer


def save_active_streamer(
    connection: sqlite3.Connection,
    twitch_user_id: str,
    login: str,
    display_name: str,
    profile_image_url: str,
) -> None:
    now = datetime.now(UTC).isoformat()

    try:
        cursor = connection.execute(
            """
            UPDATE streamers
            SET enabled = 0, updated_at = ?
            WHERE enabled = 1;
            """,
            (now,),
        )
        cursor.close()

        cursor = connection.execute(
            """
            INSERT INTO streamers (
                twitch_user_id,
                login,
                display_name,
                profile_image_url,
                enabled,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT (twitch_user_id) DO UPDATE SET
                login = excluded.login,
                display_name = excluded.display_name,
                profile_image_url = excluded.profile_image_url,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (twitch_user_id, login, display_name, profile_image_url, now, now),
        )
        cursor.close()

        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise


def load_active_streamer(
    connection: sqlite3.Connection,
) -> Streamer | None:
    cursor = connection.execute(
        """
        SELECT twitch_user_id, login, display_name, profile_image_url
        FROM streamers
        WHERE enabled = 1
        LIMIT 1;
        """
    )
    row = cast(sqlite3.Row | None, cursor.fetchone())
    cursor.close()

    if row is None:
        return None

    return Streamer(
        twitch_user_id=cast(str, row["twitch_user_id"]),
        login=cast(str, row["login"]),
        display_name=cast(str, row["display_name"]),
        profile_image_url=cast(str, row["profile_image_url"]),
    )


def load_streamer(
    connection: sqlite3.Connection,
    twitch_user_id: str,
) -> Streamer | None:
    cursor = connection.execute(
        """
        SELECT twitch_user_id, login, display_name, profile_image_url
        FROM streamers
        WHERE twitch_user_id = ?
        LIMIT 1;
        """,
        (twitch_user_id,),
    )
    row = cast(sqlite3.Row | None, cursor.fetchone())
    cursor.close()

    if row is None:
        return None

    return Streamer(
        twitch_user_id=cast(str, row["twitch_user_id"]),
        login=cast(str, row["login"]),
        display_name=cast(str, row["display_name"]),
        profile_image_url=cast(str, row["profile_image_url"]),
    )
