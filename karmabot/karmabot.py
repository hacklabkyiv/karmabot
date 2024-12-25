import pathlib
from dataclasses import dataclass
from typing import Any

import yaml
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from slack_sdk.web import WebClient

from .config import KarmabotConfig
from .karma_manager import KarmaManager
from .logging import logger
from .parse import Parse
from .transport import Transport
from .words import Color, Format

REQUIRED_MESSAGE_FIELDS = {"user", "text", "ts", "type", "channel"}


@dataclass
class Command:
    name: str
    parser: Any
    executor: Any
    admin_only: bool


class Karmabot:
    def __init__(self, config_path: pathlib.Path) -> None:
        with config_path.open("r") as f:
            config_dict = yaml.safe_load(f)
        self._config = KarmabotConfig.model_validate(config_dict)
        self._scheduler = _create_scheduler(self._config.db)
        self._admins = self._config.admins
        self._transport = Transport(self._config.slack_token)
        self._format = Format(
            lang=self._config.lang,
            votes_up_emoji=self._config.karma.upvote_emoji,
            votes_down_emoji=self._config.karma.downvote_emoji,
            timeout=self._config.karma.vote_timeout,
        )
        self._manager = KarmaManager(
            config=self._config,
            transport=self._transport,
            fmt=self._format,
        )

        self._commands = self._init_commands()
        self._init_monthly_digest(config_path)
        self._init_voting_maintenance(config_path)

        def _team_join_callback(client, message):
            self._handle_team_join(client, message)

        self._transport.slack_app.event("team_join")(_team_join_callback)

        def _app_mention_callback(client, message):
            self._handle_app_mention(client, message)

        self._transport.slack_app.event("app_mention")(_app_mention_callback)

        def _dm_message_callback(client, message):
            self._handle_dm_cmd(client, message)

        self._transport.slack_app.event("message")(_dm_message_callback)

    def run(self) -> None:
        self._scheduler.start()
        self._transport.start()

    def _handle_team_join(self, client: WebClient, event: dict):
        logger.debug("Processing event: %s", event)
        user_id = event["user"]["id"]
        self._transport.post_im(user_id, self._format.hello())
        logger.info("Team joined by user_id=%s", user_id)

    def _handle_app_mention(self, client: WebClient, event: dict) -> None:
        logger.debug("Processing event: %s", event)

        event_fields = set(event.keys())
        if not REQUIRED_MESSAGE_FIELDS.issubset(event_fields):
            logger.debug("Not enough fields for: %s", event)
            return

        initiator_id = event["user"]
        channel = event["channel"]
        text = event["text"]
        ts = event["ts"]

        # Don't handle requests from private channels (aka groups)
        if channel.startswith("G"):
            logger.debug("Skip message in group %s", channel)
            return

        # Handle only messages with `@karmabot` at the beginning
        user_id = Parse.user_mention(text)
        if not user_id or not self._is_me(user_id):
            logger.debug("Skip message not for bot: %s", text)
            return
        self._manager.create(initiator_id, channel, text, ts)

    def _handle_dm_cmd(self, client: WebClient, event: dict) -> None:
        initiator_id = event["user"]
        channel = event["channel"]
        text = event["text"]

        # Handling only DM messages and skipping own messages
        if not channel.startswith("D") or self._is_me(initiator_id):
            return

        for cmd in self._commands:
            args = cmd.parser(text)
            if not args:
                # Command don't match
                continue

            if isinstance(args, bool):
                args = []
            elif not isinstance(args, list):
                args = [args]

            if cmd.admin_only and not self._is_admin(initiator_id):
                # Command matched, but permissions are wrong
                return

            cmd.executor(*args, channel=channel)
            return

        self._transport.post(channel, self._format.cmd_error())

    def _help(self, channel: str) -> None:
        self._transport.post(channel, self._format.hello())

    def _get_config(self, channel: str) -> None:
        message = self._config.model_dump_json(exclude={"slack_token"})
        self._transport.post(channel, Format.message(Color.INFO, message))

    def _is_admin(self, initiator_id: str) -> bool:
        return self._transport.lookup_username(initiator_id) in self._admins

    def _is_me(self, initiator_id: str) -> bool:
        return self._transport.lookup_username(initiator_id) == "karmabot"

    def _init_commands(self) -> list[Command]:
        return [
            Command(
                name="get",
                parser=Parse.cmd_get,
                executor=self._manager.get,
                admin_only=False,
            ),
            Command(
                name="set",
                parser=Parse.cmd_set,
                executor=self._manager.set,
                admin_only=True,
            ),
            Command(
                name="digest",
                parser=Parse.cmd_digest,
                executor=self._manager.digest,
                admin_only=False,
            ),
            Command(
                name="config",
                parser=Parse.cmd_config,
                executor=self._get_config,
                admin_only=True,
            ),
            Command(
                name="help",
                parser=Parse.cmd_help,
                executor=self._help,
                admin_only=False,
            ),
        ]

    def _init_monthly_digest(self, config_path: pathlib.Path) -> None:
        if self._config.digest.day <= 0:
            logger.warning("Failed to configure the montly digest: a day is less than 0")
            return
        if self._config.digest.day > 28:
            logger.warning("Failed to configure the montly digest: a day is greater than 28")
        if not self._transport.channel_exists(self._config.digest.channel):
            logger.warning(
                "Failed to configure the montly digest: channel [%s] not found",
                self._config.digest.channel,
            )
            return
        self._scheduler.add_job(
            monthly_digest_func,
            kwargs=dict(config_path=config_path),
            id="monthly_digest",
            trigger="cron",
            day=self._config.digest.day,
            replace_existing=True,
        )

    def _init_voting_maintenance(self, config_path: pathlib.Path) -> None:
        self._scheduler.add_job(
            voting_maintenance_func,
            kwargs=dict(config_path=config_path),
            id="voting_maintenance",
            trigger="cron",
            minute="*",
            replace_existing=True,
        )


def _create_scheduler(url: str):
    jobstores = {"default": SQLAlchemyJobStore(url=url, tablename="karmabot_scheduler")}
    executors = {"default": ProcessPoolExecutor()}
    job_defaults = {
        "coalesce": True,  # run only once if turns out we need to run > 1 time
        "max_instances": 1,  # max number of job of one type running simultaneously
    }
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )
    return scheduler


def monthly_digest_func(config_path: pathlib.Path) -> None:
    """Montly digest entry point.

    Notes
    =====

    1. All the arguments must be picklable.
    2. For security's and flexibility's sake the only argument passed
    is a config path. This way we avoid re-creating jobs in case if config
    was modified.
    """
    with config_path.open("r") as f:
        config_dict = yaml.safe_load(f)
    config = KarmabotConfig.model_validate(config_dict)
    transport = Transport(config.slack_token)
    format = Format(
        lang=config.lang,
        votes_up_emoji=config.karma.upvote_emoji,
        votes_down_emoji=config.karma.downvote_emoji,
        timeout=config.karma.vote_timeout,
    )
    manager = KarmaManager(
        config=config,
        transport=transport,
        fmt=format,
    )
    manager.digest()


def voting_maintenance_func(config_path: pathlib.Path) -> None:
    """Close expired and delete outdated votings."""
    with config_path.open("r") as f:
        config_dict = yaml.safe_load(f)
    config = KarmabotConfig.model_validate(config_dict)
    transport = Transport(config.slack_token)
    format = Format(
        lang=config.lang,
        votes_up_emoji=config.karma.upvote_emoji,
        votes_down_emoji=config.karma.downvote_emoji,
        timeout=config.karma.vote_timeout,
    )
    manager = KarmaManager(
        config=config,
        transport=transport,
        fmt=format,
    )
    manager.close_expired_votings()
    manager.remove_old_votings()
