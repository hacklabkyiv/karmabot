import datetime
import logging
import pathlib
from collections.abc import Callable

import yaml
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import WebClient

from .config import KarmabotConfig
from .karma_manager import KarmaManager
from .logging import logger
from .parse import Parse
from .slack_utils import (
    lookup_channel_name,
    lookup_username,
    message_post,
    message_update,
    post_im,
    reactions_get,
)
from .words import Color, Format

REQUIRED_MESSAGE_FIELDS = {"user", "text", "ts", "type", "channel"}


class Karmabot:
    def __init__(self, config_path: pathlib.Path) -> None:
        with config_path.open("r") as f:
            config_dict = yaml.safe_load(f)
        self._config = KarmabotConfig.model_validate(config_dict)
        log_level_str = self._config.log_level.upper()
        log_level = logging.getLevelNamesMapping().get(log_level_str)
        logger.setLevel(log_level)
        self.slack_app = App(token=self._config.slack_bot_token, logger=logger)
        self._admins = self._config.admins
        self._format = Format(
            lang=self._config.lang,
            votes_up_emoji=self._config.karma.upvote_emoji,
            votes_down_emoji=self._config.karma.downvote_emoji,
            timeout=self._config.karma.vote_timeout,
        )
        self._manager = KarmaManager(config=self._config)

        @self.slack_app.event("team_join")
        def _team_join_callback(client, event):
            logger.debug("[team_join] %s", event)
            self._handle_team_join(client, event)

        @self.slack_app.event("app_mention")
        def _app_mention_callback(client, event):
            logger.debug("[app_mention] %s", event)
            self._handle_app_mention(client, event)

        @self.slack_app.command("/karma-test")
        def _command_callback(ack: Callable, respond: Callable, command: dict):
            logger.debug("[command] %s", command)
            self._handle_command(ack, respond, command)

    def run(self) -> None:
        SocketModeHandler(self.slack_app, self._config.slack_app_token).start()

    def report_digest(self) -> None:
        result = ["*username* => *karma*"]
        for r in self._manager.digest():
            username = lookup_username(self.slack_app.client, r.user_id)
            item = f"_{username}_ => *{r.karma}*"
            result.append(item)
        # TODO: add translations
        if len(result) == 1:
            message = "Seems like nothing to show. All the karma is zero"
        else:
            message = "\n".join(result)
        message_post(
            self.slack_app.client,
            self._config.digest.channel,
            self._format.message(Color.INFO, message),
        )

    def process_expired_votings(self) -> None:
        for voting in self._manager.get_expired_votings():
            logger.info("Expired voting: %s", voting)
            reactions = reactions_get(
                client=self.slack_app.client,
                channel=voting.channel,
                initial_msg_ts=voting.message_ts,
                bot_msg_ts=voting.bot_message_ts,
            )
            success = self._manager.close_voting(voting, reactions)
            username = lookup_username(self.slack_app.client, voting.target_id)
            result = self._format.voting_result(username, voting.karma, success)
            message_update(self.slack_app.client, voting.channel, result, voting.bot_message_ts)

        self._manager.remove_old_votings()

    def _handle_team_join(self, client: WebClient, event: dict):
        logger.info("Processing event: %s", event)
        user_id = event["user"]["id"]
        post_im(self.slack_app.client, user_id, self._format.hello())
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
        if not user_id or not lookup_username(self.slack_app.client, user_id) == "karmabot":
            logger.info("Skip message not for bot: %s", text)
            return

        # Report an error if a request has not been parsed
        result = Parse.karma_change(text)
        if not result:
            message_post(self.slack_app.client, channel, self._format.parsing_error(), ts=ts)
            return

        bot_id, user_id, karma = result
        error = self._karma_change_sanity_check(initiator_id, user_id, bot_id, karma)
        if error:
            message_post(self.slack_app.client, channel, error, ts=ts)
            return

        username = lookup_username(self.slack_app.client, user_id)
        msg = self._format.new_voting(username, karma)
        response = message_post(self.slack_app.client, channel, msg, ts=ts)
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

    def _handle_command(self, ack: Callable, respond: Callable, command: dict) -> None:
        ack()
        initiator_name = command["user_name"]
        channel = command["channel_id"]
        text = command["text"]
        is_admin = initiator_name in self._admins

        if user_id := Parse.cmd_get(text):
            logger.info("Handling command 'get'")
            karma = self._manager.get(user_id)
            username = lookup_username(self.slack_app.client, user_id)
            message_post(
                self.slack_app.client, channel, self._format.report_karma(username, karma)
            )
        elif args := Parse.cmd_set(text):
            logger.info("Handling command 'set'")
            if not is_admin:
                logger.warning("Only admins can set the karma")
                return
            user_id, karma = args
            self._manager.set(user_id=user_id, karma=karma)
            username = lookup_username(self.slack_app.client, user_id)
            message_post(
                self.slack_app.client, channel, self._format.report_karma(username, karma)
            )
        elif Parse.cmd_digest(text):
            logger.info("Handling command 'digest'")
            self.report_digest()
        elif Parse.cmd_pending(text):
            logger.info("Handling command 'pending'")
            result = ["*initiator* | *receiver* | *channel* | *karma* | *expired*"]
            for voting in self._manager.pending():
                dt = self._config.karma.vote_timeout
                time_left = datetime.datetime.fromtimestamp(float(voting.message_ts)) + dt
                initiator = lookup_username(self.slack_app.client, voting.initiator_id)
                target = lookup_username(self.slack_app.client, voting.target_id)
                channel_name = lookup_channel_name(self.slack_app.client, voting.channel)
                item = f"{initiator} | {target} | {channel_name} | {voting.karma} | {time_left.isoformat()}"
                result.append(item)
            # TODO: add translations
            if len(result) == 1:
                message = "Seems like nothing to show"
            else:
                message = "\n".join(result)
            message_post(self.slack_app.client, channel, self._format.message(Color.INFO, message))
        elif Parse.cmd_help(text):
            logger.info("Handling command 'help'")
            message_post(self.slack_app.client, channel, self._format.hello())
        else:
            # A default behavior is to error
            logger.info("Unknown command: %s", command["text"])
            message_post(self.slack_app.client, channel, self._format.cmd_error())

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
