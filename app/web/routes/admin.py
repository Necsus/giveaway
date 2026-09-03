from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.session import SessionIdentity
from app.web.dependencies import require_session_identity

router = APIRouter()

SessionDependency = Annotated[
    SessionIdentity,
    Depends(require_session_identity),
]


@router.get("/api/admin/session")
def admin_session(identity: SessionDependency) -> dict[str, str]:
    return {
        "twitch_user_id": identity.twitch_user_id,
    }
