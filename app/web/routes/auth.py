import asyncio
import logging
import sqlite3
from typing import cast

import aiohttp
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from twitchio.exceptions import HTTPException as TwitchHTTPException
from twitchio.exceptions import TwitchioException

from app.application.commands import GiveawayCommandHandler
from app.application.oauth_state import OAuthStateStore
from app.application.session import SESSION_COOKIE_NAME, SessionSigner
from app.core.environment import Settings
from app.infrastructure.streamers import save_active_streamer
from app.infrastructure.twitch import GiveawayTwitchBot
from app.infrastructure.twitch_oauth import (
    TwitchOAuthClient,
    build_authorization_url,
)

LOGGER = logging.getLogger("uvicorn.error")

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


@router.get("/auth/twitch/callback")
async def twitch_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> JSONResponse:
    oauth_state_store = cast(
        OAuthStateStore,
        request.app.state.oauth_state_store,
    )

    if state is None or not oauth_state_store.consume(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    if error is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twitch authorization was denied",
        )

    if code is None or not code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth authorization code",
        )

    twitch_oauth_client = cast(
        TwitchOAuthClient,
        request.app.state.twitch_oauth_client,
    )

    try:
        authorization = await twitch_oauth_client.exchange_code(code)

        connection = cast(
            sqlite3.Connection,
            request.app.state.database_connection,
        )
        save_active_streamer(
            connection,
            twitch_user_id=authorization.twitch_user_id,
            login=authorization.login,
            display_name=authorization.display_name,
            profile_image_url=authorization.profile_image_url,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Twitch authorization",
        ) from None
    except (TwitchHTTPException, aiohttp.ClientError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Twitch authentication is temporarily unavailable",
        ) from None
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to persist the Twitch identity",
        ) from None

    giveaway_command_handler = cast(
        GiveawayCommandHandler,
        request.app.state.giveaway_command_handler,
    )
    giveaway_command_handler.set_active_broadcaster(
        authorization.twitch_user_id,
    )

    twitch_bot = cast(
        GiveawayTwitchBot | None,
        request.app.state.twitch_bot,
    )
    request.app.state.twitch_chat_ready = False

    if twitch_bot is not None:
        try:
            async with asyncio.timeout(10):
                await twitch_bot.wait_until_ready()

            await twitch_bot.subscribe_to_streamer(authorization)
        except (
            TimeoutError,
            TwitchioException,
            aiohttp.ClientError,
            ValueError,
        ) as subscribe_error:
            LOGGER.warning(
                "Unable to subscribe to Twitch chat: streamer_id=%s error=%s",
                authorization.twitch_user_id,
                type(subscribe_error).__name__,
            )
        else:
            request.app.state.twitch_chat_ready = True

    settings = cast(Settings, request.app.state.settings)
    session_signer = cast(
        SessionSigner,
        request.app.state.session_signer,
    )
    cookie_value = session_signer.create(
        authorization.twitch_user_id,
    )

    response = JSONResponse(
        content={
            "twitch_user_id": authorization.twitch_user_id,
            "login": authorization.login,
            "display_name": authorization.display_name,
        }
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )

    return response


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(request: Request) -> Response:
    settings = cast(Settings, request.app.state.settings)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response
