from dataclasses import dataclass


@dataclass(frozen=True)
class Streamer:
    twitch_user_id: str
    login: str
    display_name: str
