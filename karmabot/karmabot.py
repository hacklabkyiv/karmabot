import time
from dataclasses import dataclass
from typing import Any

from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from slack_sdk.rtm_v2 import RTMClient

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
    def __init__(self, config: KarmabotConfig) -> None:
        self._scheduler = _create_scheduler()
        self._config = config
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
        self._init_monthly_digest()

        self._transport.register_callback("team_join", self._handle_team_join)
        self._transport.register_callback("message", self._handle_message)

    def run(self):
        self._scheduler.start()
        self._transport.start()
        while True:
            now = time.time()
            self._manager.close_expired_votings(now)
            self._manager.remove_old_votings()

    def _handle_dm_cmd(self, initiator_id, channel, text):
        # Handling only DM messages and skipping own messages
        if not channel.startswith("D") or self._is_me(initiator_id):
            return False

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
                return True

            if cmd.executor(*args, channel=channel):
                logger.debug("Executed %s command", cmd.name)
            else:
                logger.error("Failed to execute %s commnad", cmd.name)
            return True

        self._transport.post(channel, self._format.cmd_error())
        return False

    def _handle_team_join(self, client: RTMClient, event: dict):
        logger.debug("Processing event: %s", event)
        user_id = event["user"]["id"]
        new_dm = self._transport.client.im_open(user=user_id)
        self._transport.post(new_dm["channel"]["id"], self._format.hello())

        logger.info("Team joined by user_id=%s", user_id)
        return True

    def _handle_message(self, client: RTMClient, event: dict) -> None:
        logger.debug("Processing event: %s", event)

        event_fields = set(event.keys())
        if not REQUIRED_MESSAGE_FIELDS.issubset(event_fields):
            logger.debug("Not enough fields for: %s", event)
            return

        initiator_id = event["user"]
        channel = event["channel"]
        text = event["text"]
        ts = event["ts"]

        if self._handle_dm_cmd(initiator_id, channel, text):
            return

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

    def _cmd_help(self, channel: str) -> None:
        self._transport.post(channel, self._format.hello())

    def _cmd_config(self, channel: str) -> None:
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
                executor=self._cmd_config,
                admin_only=False,
            ),
            Command(
                name="help",
                parser=Parse.cmd_help,
                executor=self._cmd_help,
                admin_only=False,
            ),
        ]

    def _init_monthly_digest(self) -> None:
        if self._config.digest.day <= 0:
            logger.warning("Failed to configure the montly digest: a day is less than 0")
            return
        if self._config.digest.day > 28:
            logger.warning("Failed to configure the montly digest: a day is greater than 28")
        result = self._transport.client.conversations_list(
            exclude_archived=True,
            exclude_members=True,
        )
        channels = result.get("channels") or []
        if not any(c["name"] == self._config.digest.channel for c in channels):
            logger.warning(
                "Failed to configure the montly digest: channel [%s] not found",
                self._config.digest.channel,
            )
            return
        self._scheduler.add_job(
            self._manager.digest,
            id="monthly_digest",
            trigger="cron",
            day=self._config.digest.day,
            replace_existing=True,
        )


def _create_scheduler():
    jobstores = {"default": SQLAlchemyJobStore(tablename="karmabot_scheduler")}
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
