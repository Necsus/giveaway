from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TwitchConfiguration(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        str_to_lower=True,
    )

    enabled: bool = True

    bot_id: str = Field(pattern=r"^\d+$")
    owner_id: str = Field(pattern=r"^\d+$")
    broadcaster_id: str = Field(pattern=r"^\d+$")

    bot_login: str = Field(min_length=1, max_length=25)
    channel_login: str = Field(min_length=1, max_length=25)


class CommandConfiguration(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    prefix: str = Field(default="!", min_length=1, max_length=5)


class ApplicationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    twitch: TwitchConfiguration
    commands: CommandConfiguration = Field(
        default_factory=CommandConfiguration,
    )
