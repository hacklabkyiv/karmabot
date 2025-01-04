import pathlib
from dataclasses import dataclass
from typing import Any

import yaml
from slack_sdk.web import WebClient

from .config import KarmabotConfig
from .karma_manager import KarmaManager
from .logging import logger
from .parse import Parse
from .scheduler import create_scheduler, monthly_digest_func, voting_maintenance_func
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
        self._scheduler = create_scheduler(self._config.db)
        self._admins = self._config.admins
        self._transport = Transport(self._config)
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

        @self._transport.slack_app.event("team_join")
        def _team_join_callback(client, event):
            print(f"[team_join] {event}")
            self._handle_team_join(client, event)

        @self._transport.slack_app.event("app_mention")
        def _app_mention_callback(client, event):
            print(f"[app_mention] {event}")
            self._handle_app_mention(client, event)

        # @self._transport.slack_app.event("message")
        # def _dm_message_callback(client, message):
        #     print(f"[message] {message}")
        #     self._handle_dm_cmd(client, message)

    def run(self) -> None:
        self._scheduler.start()
        self._transport.start()

    def _handle_team_join(self, client: WebClient, event: dict):
        logger.info("Processing event: %s", event)
        user_id = event["user"]["id"]
        self._transport.post_im(user_id, self._format.hello())
        logger.info("Team joined by user_id=%s", user_id)

    def _handle_app_mention(self, client: WebClient, event: dict) -> None:
        logger.info("Processing event: %s", event)

        event_fields = set(event.keys())
        if not REQUIRED_MESSAGE_FIELDS.issubset(event_fields):
            logger.info("Not enough fields for: %s", event)
            return

        initiator_id = event["user"]
        channel = event["channel"]
        text = event["text"]
        ts = event["ts"]

        # Don't handle requests from private channels (aka groups)
        if channel.startswith("G"):
            logger.info("Skip message in group %s", channel)
            return

        # Handle only messages with `@karmabot` at the beginning
        user_id = Parse.user_mention(text)
        if not user_id or not self._is_me(user_id):
            logger.info("Skip message not for bot: %s", text)
            return

        # Report an error if a request has not been parsed
        result = Parse.karma_change(text)
        if not result:
            self._transport.post(channel, self._format.parsing_error(), ts=ts)
            return

        bot_id, user_id, karma = result
        error = self._karma_change_sanity_check(initiator_id, user_id, bot_id, karma)
        if error:
            self._transport.post(channel, error, ts=ts)
            return

        username = self._transport.lookup_username(user_id)
        msg = self._format.new_voting(username, karma)
        response = self._transport.post(channel, msg, ts=ts)
        bot_message_ts = response["ts"]
        self._manager.create(
            initiator_id=initiator_id,
            target_id=user_id,
            channel=channel,
            text=text,
            ts=ts,
            bot_message_ts=bot_message_ts,
            karma=karma,
        )

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
        message = self._config.model_dump_json(exclude={"slack_bot_token", "slack_app_token"})
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

    def _karma_change_sanity_check(
        self, initiator_id: str, user_id: str, bot_id: str, karma: int
    ) -> dict | None:
        if not self._config.karma.self_karma and initiator_id == user_id:
            return self._format.strange_error()
        if user_id == bot_id:
            return self._format.robo_error()
        if abs(karma) > self._config.karma.max_diff:
            return self._format.max_diff_error(self._config.karma.max_diff)
        return None
