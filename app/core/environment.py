from pathlib import Path
from typing import ClassVar

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    twitch_enabled: bool
    twitch_oauth_enabled: bool = False
    twitch_client_id: str
    twitch_client_secret: SecretStr

    twitch_bot_id: str
    twitch_owner_id: str
    twitch_broadcaster_id: str

    twitch_bot_login: str
    twitch_channel_login: str

    twitch_admin_redirect_uri: str
    session_secret: SecretStr
    session_cookie_secure: bool = False
    session_max_age_seconds: int = Field(default=28_800, gt=0)

    twitch_command_prefix: str = "!"

    giveaway_config_file: Path = PROJECT_ROOT / "data" / "settings.json"
