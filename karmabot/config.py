from __future__ import annotations

import datetime

import pydantic_settings


class KarmabotConfig(pydantic_settings.BaseSettings):
    log_level: str
    lang: str
    slack_bot_token: str
    slack_app_token: str
    db: str
    admins: list[str]
    digest: KarmabotDigestConfig
    karma: KarmabotKarmaConfig


class KarmabotDigestConfig(pydantic_settings.BaseSettings):
    channel: str
    day: int
    hour: int
    minute: int


class KarmabotKarmaConfig(pydantic_settings.BaseSettings):
    initial_value: int
    max_diff: int
    self_karma: bool
    vote_timeout: datetime.timedelta
    keep_history: datetime.timedelta
    upvote_emoji: list[str]
    downvote_emoji: list[str]
