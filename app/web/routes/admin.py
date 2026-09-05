import sqlite3
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse

from app.application.overlay_access import (
    GIVEAWAY_PLUGIN_SLUG,
    generate_overlay_token,
    hash_overlay_token,
)
from app.application.session import SessionIdentity
from app.core.configuration import ApplicationConfiguration
from app.infrastructure.overlay_access import (
    load_overlay_access_key_rotated_at,
    rotate_overlay_access_key,
)
from app.infrastructure.streamers import load_active_streamer, load_streamer
from app.infrastructure.twitch import GiveawayTwitchBot
from app.web.dependencies import require_session_identity
from app.web.websocket import OverlayConnectionManager

ADMIN_PAGE = (
    Path(__file__).resolve().parents[1] / "static" / "admin" / "admin.html"
)

router = APIRouter()

SessionDependency = Annotated[
    SessionIdentity,
    Depends(require_session_identity),
]


@router.get("/admin", response_class=FileResponse)
def admin_page() -> FileResponse:
    return FileResponse(ADMIN_PAGE)


@router.get("/api/admin/session")
async def admin_session(
    request: Request, identity: SessionDependency
) -> dict[str, object]:
    connection = cast(
        sqlite3.Connection,
        request.app.state.database_connection,
    )
    streamer = load_streamer(
        connection,
        identity.twitch_user_id,
    )

    if streamer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    active_streamer = load_active_streamer(connection)
    active_streamer_data: dict[str, str] | None = None

    if active_streamer is not None:
        active_streamer_data = {
            "twitch_user_id": active_streamer.twitch_user_id,
            "login": active_streamer.login,
            "display_name": active_streamer.display_name,
        }

    configuration = cast(
        ApplicationConfiguration,
        request.app.state.configuration,
    )

    twitch_bot = cast(
        GiveawayTwitchBot | None,
        request.app.state.twitch_bot,
    )
    if twitch_bot is None:
        chat_status = "disabled"
    elif twitch_bot.chat_subscription_ready:
        chat_status = "ready"
    else:
        chat_status = "degraded"

    return {
        "session": {
            "twitch_user_id": streamer.twitch_user_id,
            "login": streamer.login,
            "display_name": streamer.display_name,
            "profile_image_url": streamer.profile_image_url,
        },
        "active_streamer": active_streamer_data,
        "bot": {
            "twitch_user_id": configuration.twitch.bot_id,
            "login": configuration.twitch.bot_login,
        },
        "chat": {
            "status": chat_status,
        },
    }


@router.post("/api/admin/plugins/giveaway/overlay-access/rotate")
async def rotate_giveaway_overlay_access(
    request: Request,
    response: Response,
    identity: SessionDependency,
) -> dict[str, str]:
    token = generate_overlay_token()
    token_hash = hash_overlay_token(token)

    connection = cast(
        sqlite3.Connection,
        request.app.state.database_connection,
    )

    try:
        rotate_overlay_access_key(
            connection,
            streamer_id=identity.twitch_user_id,
            plugin_slug=GIVEAWAY_PLUGIN_SLUG,
            token_hash=token_hash,
        )
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to rotate the overlay access key",
        ) from None

    overlay_connections = cast(
        OverlayConnectionManager,
        request.app.state.overlay_connections,
    )
    await overlay_connections.disconnect_streamer(
        identity.twitch_user_id,
    )

    base_url = str(request.base_url).rstrip("/")
    overlay_url = f"{base_url}/plugins/giveaway/overlay#{token}"

    response.headers["Cache-Control"] = "no-store"

    return {
        "overlay_url": overlay_url,
    }


@router.get("/api/admin/plugins/giveaway/overlay-access")
async def giveaway_overlay_access_status(
    request: Request,
    response: Response,
    identity: SessionDependency,
) -> dict[str, object]:
    connection = cast(
        sqlite3.Connection,
        request.app.state.database_connection,
    )

    try:
        rotated_at = load_overlay_access_key_rotated_at(
            connection,
            streamer_id=identity.twitch_user_id,
            plugin_slug=GIVEAWAY_PLUGIN_SLUG,
        )
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load the overlay access status",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "configured": rotated_at is not None,
        "rotated_at": rotated_at,
    }
