import asyncio
import logging
import sqlite3
from typing import cast

import aiohttp
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from twitchio.exceptions import HTTPException as TwitchHTTPException
from twitchio.exceptions import TwitchioException

from app.application.commands import GiveawayCommandHandler
from app.application.oauth_state import OAuthStateStore
from app.application.session import SESSION_COOKIE_NAME, SessionSigner
from app.core.configuration import ApplicationConfiguration
from app.core.environment import Settings
from app.infrastructure.streamers import save_active_streamer
from app.infrastructure.twitch import GiveawayTwitchBot
from app.infrastructure.twitch_oauth import (
    BOT_SCOPE_NAMES,
    STREAMER_SCOPE_NAMES,
    TwitchAuthorization,
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

    state = oauth_state_store.issue("streamer")
    authorization_url = build_authorization_url(
        client_id=settings.twitch_client_id,
        redirect_uri=settings.twitch_admin_redirect_uri,
        state=state,
        scopes=STREAMER_SCOPE_NAMES,
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/auth/twitch/bot/login",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)
def twitch_bot_login(request: Request) -> RedirectResponse:
    settings = cast(Settings, request.app.state.settings)
    oauth_state_store = cast(OAuthStateStore, request.app.state.oauth_state_store)

    state = oauth_state_store.issue("bot")
    authorization_url = build_authorization_url(
        client_id=settings.twitch_client_id,
        redirect_uri=settings.twitch_admin_redirect_uri,
        state=state,
        scopes=BOT_SCOPE_NAMES,
        force_verify=True,
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_302_FOUND,
    )


async def complete_bot_authorization(
    request: Request,
    authorization: TwitchAuthorization,
) -> RedirectResponse:
    configuration = cast(
        ApplicationConfiguration,
        request.app.state.configuration,
    )
    if authorization.twitch_user_id != configuration.twitch.bot_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The Twitch authorization does not belong to the configured bot",
        )

    twitch_bot = cast(
        GiveawayTwitchBot | None,
        request.app.state.twitch_bot,
    )
    if twitch_bot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The Twitch bot is disabled",
        )

    try:
        async with asyncio.timeout(10):
            await twitch_bot.wait_until_ready()

        await twitch_bot.authorize_bot(authorization)
    except (TimeoutError, TwitchioException, aiohttp.ClientError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to authorize the Twitch bot",
        ) from None

    return RedirectResponse(
        url="/admin",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/auth/twitch/callback")
async def twitch_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    oauth_state_store = cast(
        OAuthStateStore,
        request.app.state.oauth_state_store,
    )

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )

    oauth_flow = oauth_state_store.consume(state)
    if oauth_flow is None:
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

    required_scopes = (
        BOT_SCOPE_NAMES if oauth_flow == "bot" else STREAMER_SCOPE_NAMES
    )

    try:
        authorization = await twitch_oauth_client.exchange_code(
            code,
            required_scopes=required_scopes,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Twitch authorization",
        ) from None
    except (TwitchHTTPException, aiohttp.ClientError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Twitch authentication is temporarily unavailable",
        ) from None
    if oauth_flow == "bot":
        return await complete_bot_authorization(request, authorization)

    connection = cast(
        sqlite3.Connection,
        request.app.state.database_connection,
    )
    try:
        save_active_streamer(
            connection,
            twitch_user_id=authorization.twitch_user_id,
            login=authorization.login,
            display_name=authorization.display_name,
            profile_image_url=authorization.profile_image_url,
        )
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

    settings = cast(Settings, request.app.state.settings)
    session_signer = cast(
        SessionSigner,
        request.app.state.session_signer,
    )
    cookie_value = session_signer.create(
        authorization.twitch_user_id,
    )

    response = RedirectResponse(
        url="/admin",
        status_code=status.HTTP_303_SEE_OTHER,
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
