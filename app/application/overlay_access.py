import hashlib
import secrets
from typing import cast

GIVEAWAY_PLUGIN_SLUG = "giveaway"


def generate_overlay_token() -> str:
    return secrets.token_urlsafe(32)


def hash_overlay_token(token: str) -> str:
    if not token:
        raise ValueError("The overlay token cannot be empty")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_overlay_authentication(message: object) -> str | None:
    if not isinstance(message, dict):
        return None

    payload = cast(dict[object, object], message)

    if set(payload) != {"type", "token"}:
        return None

    message_type = payload.get("type")
    token = payload.get("token")

    if message_type != "overlay.authenticate":
        return None

    if not isinstance(token, str) or not token:
        return None

    return token
