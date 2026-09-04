import sqlite3
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.application.session import SessionIdentity
from app.core.configuration import ApplicationConfiguration
from app.infrastructure.streamers import load_active_streamer, load_streamer
from app.infrastructure.twitch import GiveawayTwitchBot
from app.web.dependencies import require_session_identity

ADMIN_PAGE = Path(__file__).resolve().parents[1] / "static" / "admin.html"

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
