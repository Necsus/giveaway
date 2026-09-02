from typing import cast

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from app.application.oauth_state import OAuthStateStore
from app.core.environment import Settings
from app.infrastructure.twitch_oauth import build_authorization_url

router = APIRouter()


@router.get(
    "/auth/twitch/login",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)
def twitch_login(request: Request) -> RedirectResponse:
    settings = cast(Settings, request.app.state.settings)
    oauth_state_store = cast(OAuthStateStore, request.app.state.oauth_state_store)

    state = oauth_state_store.issue()
    authorization_url = build_authorization_url(
        client_id=settings.twitch_client_id,
        redirect_uri=settings.twitch_admin_redirect_uri,
        state=state,
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_302_FOUND,
    )
