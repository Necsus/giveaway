from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.application.session import SessionIdentity
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
def admin_session(identity: SessionDependency) -> dict[str, str]:
    return {
        "twitch_user_id": identity.twitch_user_id,
    }
