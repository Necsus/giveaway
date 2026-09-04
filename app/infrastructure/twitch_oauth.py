import urllib.parse
from dataclasses import dataclass, field
from typing import cast

import aiohttp
from twitchio import authentication

TWITCH_AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_USERS_URL = "https://api.twitch.tv/helix/users"
REQUIRED_STREAMER_SCOPE = "channel:bot"


@dataclass(frozen=True)
class TwitchAuthorization:
    twitch_user_id: str
    login: str
    display_name: str
    profile_image_url: str
    scopes: frozenset[str]
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)


class TwitchOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._client_id = client_id
        self._oauth = authentication.OAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    async def exchange_code(self, code: str) -> TwitchAuthorization:
        if not code.strip():
            raise ValueError("The OAuth authorization code cannot be empty")

        token_payload = await self._oauth.user_access_token(code)
        validated_token = await self._oauth.validate_token(token_payload.access_token)

        if validated_token.client_id != self._client_id:
            raise ValueError("The OAuth token belongs to another application")

        if not validated_token.user_id or not validated_token.login:
            raise ValueError("The OAuth token has no Twitch user identity")

        scopes = frozenset(validated_token.scopes)
        if REQUIRED_STREAMER_SCOPE not in scopes:
            raise ValueError("The OAuth token is missing the channel:bot scope")

        login, display_name, profile_image_url = await self._fetch_profile(
            access_token=token_payload.access_token,
            expected_user_id=validated_token.user_id,
        )

        return TwitchAuthorization(
            twitch_user_id=validated_token.user_id,
            login=login,
            display_name=display_name,
            profile_image_url=profile_image_url,
            scopes=scopes,
            access_token=token_payload.access_token,
            refresh_token=token_payload.refresh_token,
        )

    async def _fetch_profile(
        self,
        access_token: str,
        expected_user_id: str,
    ) -> tuple[str, str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Client-Id": self._client_id,
        }

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                TWITCH_USERS_URL,
                headers=headers,
            ) as response,
        ):
            response.raise_for_status()
            payload = cast(dict[str, object], await response.json())

        data = payload.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise ValueError("Twitch returned an invalid user profile")

        raw_profile = data[0]
        if not isinstance(raw_profile, dict):
            raise TypeError("Twitch returned an invalid user profile")

        profile = cast(dict[str, object], raw_profile)
        twitch_user_id = profile.get("id")
        login = profile.get("login")
        display_name = profile.get("display_name")
        profile_image_url = profile.get("profile_image_url")

        if twitch_user_id != expected_user_id:
            raise ValueError("The Twitch profile does not match the OAuth identity")

        if not isinstance(login, str) or not login.strip():
            raise ValueError("The Twitch profile has no valid login")

        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("The Twitch profile has no valid display name")

        if not isinstance(profile_image_url, str):
            raise TypeError("The Twitch profile has no valid profile image URL")
        return login, display_name, profile_image_url

    async def close(self) -> None:
        await self._oauth.close()


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "channel:bot",
        "state": state,
    }

    query_string = urllib.parse.urlencode(params)

    return f"{TWITCH_AUTHORIZE_URL}?{query_string}"
