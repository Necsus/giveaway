from dataclasses import dataclass
from typing import cast

from itsdangerous import BadSignature, URLSafeTimedSerializer

SESSION_SALT = "giveaway-admin-session-v1"
SESSION_COOKIE_NAME = "giveaway_session"


@dataclass(frozen=True)
class SessionIdentity:
    twitch_user_id: str


class SessionSigner:
    def __init__(
        self,
        secret_key: str,
        max_age_seconds: int,
    ) -> None:
        if not secret_key.strip():
            raise ValueError("The session secret cannot be empty")

        if max_age_seconds <= 0:
            raise ValueError("The session maximum age must be positive")

        self._serializer = URLSafeTimedSerializer(
            secret_key=secret_key,
            salt=SESSION_SALT,
        )
        self._max_age_seconds = max_age_seconds

    def create(self, twitch_user_id: str) -> str:
        if not twitch_user_id.strip():
            raise ValueError("The Twitch user ID cannot be empty")

        return self._serializer.dumps({"twitch_user_id": twitch_user_id})

    def verify(self, cookie_value: str) -> SessionIdentity | None:
        try:
            raw_payload: object = self._serializer.loads(
                cookie_value,
                max_age=self._max_age_seconds,
            )
        except BadSignature:
            return None

        if not isinstance(raw_payload, dict):
            return None

        payload = cast(dict[object, object], raw_payload)
        if set(payload) != {"twitch_user_id"}:
            return None

        twitch_user_id = payload.get("twitch_user_id")
        if not isinstance(twitch_user_id, str) or not twitch_user_id.strip():
            return None

        return SessionIdentity(twitch_user_id=twitch_user_id)
