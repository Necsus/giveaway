from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from typing import Literal

OAuthFlow = Literal["bot", "streamer"]


class OAuthStateStore:
    def __init__(self, ttl_seconds: float = 600) -> None:
        if ttl_seconds <= 0:
            raise ValueError("The Oauth state TTL must be positive")

        self._ttl_seconds = ttl_seconds
        self._states: dict[str, tuple[float, OAuthFlow]] = {}
        self._lock = Lock()

    def issue(self, flow: OAuthFlow) -> str:
        now = monotonic()

        with self._lock:
            self._remove_expired(now)

            state = token_urlsafe(32)
            while state in self._states:
                state = token_urlsafe(32)

            self._states[state] = (now + self._ttl_seconds, flow)

        return state

    def consume(self, state: str) -> OAuthFlow | None:
        with self._lock:
            state_data = self._states.pop(state, None)

        if state_data is None:
            return None

        expires_at, flow = state_data
        if expires_at <= monotonic():
            return None

        return flow

    def _remove_expired(self, now: float) -> None:
        expired_states = [
            state
            for state, (expires_at, _) in self._states.items()
            if expires_at <= now
        ]

        for state in expired_states:
            del self._states[state]
