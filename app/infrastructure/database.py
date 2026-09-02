import sqlite3
from pathlib import Path

DATA_DIRECTORY = Path("data")
DATABASE_PATH = DATA_DIRECTORY / "giveaway.sqlite3"


def connect_database() -> sqlite3.Connection:
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    cursor = connection.execute("PRAGMA foreign_keys = ON")
    cursor.close()

    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    cursor = connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS streamers (
            twitch_user_id TEXT PRIMARY KEY NOT NULL,
            login TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS giveaways (
            id TEXT PRIMARY KEY,
            lot TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN (
                    'WAITING',
                    'OPEN',
                    'WINNER',
                    'COMPLETED',
                    'CANCELLED'
                )
            ),
            created_at TEXT NOT NULL,
            opened_at TEXT,
            drawn_at TEXT,
            stopped_at TEXT,
            winner_user_id TEXT,
            winner_display_name TEXT
        );

        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY,
            giveaway_id TEXT NOT NULL,
            twitch_user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT NOT NULL,
            joined_at TEXT NOT NULL,

            FOREIGN KEY (giveaway_id)
                REFERENCES giveaways(id)
                ON DELETE CASCADE,

            UNIQUE (giveaway_id, twitch_user_id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS one_active_streamer
        ON streamers ((1))
        WHERE enabled IN (1);

        CREATE UNIQUE INDEX IF NOT EXISTS one_active_giveaway
        ON giveaways ((1))
        WHERE status IN ('WAITING', 'OPEN', 'WINNER');
        """
    )
    cursor.close()
    connection.commit()
