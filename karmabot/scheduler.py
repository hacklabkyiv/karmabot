"""Module that contains utilities related to scheduled jobs.

Notes
-----

1. All the arguments for jobs must be picklable.
2. For security's and flexibility's sake the only argument passed
is a config path. This way we avoid re-creating jobs in case if config
was modified.
"""

import pathlib

import yaml
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from slack_bolt import App

from .config import KarmabotConfig
from .karma_manager import KarmaManager
from .logging import logger
from .slack_utils import (
    channel_exists,
    lookup_username,
    message_update,
    reactions_get,
)
from .words import Format


class KarmabotScheduler:
    def __init__(self, config_path: pathlib.Path):
        with config_path.open("r") as f:
            config_dict = yaml.safe_load(f)
        self._config = KarmabotConfig.model_validate(config_dict)
        self.slack_app = App(token=self._config.slack_bot_token)
        self._scheduler = create_scheduler(self._config.db)
        self._init_monthly_digest(config_path)
        self._init_voting_maintenance(config_path)

    def start(self) -> None:
        self._scheduler.start()

    def _init_monthly_digest(self, config_path: pathlib.Path) -> None:
        if self._config.digest.day <= 0:
            logger.warning("Failed to configure the montly digest: a day is less than 0")
            return
        if self._config.digest.day > 28:
            logger.warning("Failed to configure the montly digest: a day is greater than 28")
        if not channel_exists(self.slack_app.client, self._config.digest.channel):
            logger.warning(
                "Failed to configure the montly digest: channel [%s] not found",
                self._config.digest.channel,
            )
            return
        self._scheduler.add_job(
            monthly_digest_job,
            kwargs=dict(config_path=config_path),
            id="monthly_digest",
            trigger="cron",
            day=self._config.digest.day,
            replace_existing=True,
        )

    def _init_voting_maintenance(self, config_path: pathlib.Path) -> None:
        self._scheduler.add_job(
            voting_maintenance_job,
            kwargs=dict(config_path=config_path),
            id="voting_maintenance",
            trigger="cron",
            minute="*",
            replace_existing=True,
        )


def monthly_digest_job(config_path: pathlib.Path) -> None:
    """Montly digest job entry point."""
    with config_path.open("r") as f:
        config_dict = yaml.safe_load(f)
    config = KarmabotConfig.model_validate(config_dict)
    manager = KarmaManager(config=config)
    manager.digest()


def voting_maintenance_job(config_path: pathlib.Path) -> None:
    """Close expired and delete outdated votings job entry point."""
    with config_path.open("r") as f:
        config_dict = yaml.safe_load(f)
    config = KarmabotConfig.model_validate(config_dict)
    slack_app = App(token=config.slack_bot_token)
    _format = Format(
        lang=config.lang,
        votes_up_emoji=config.karma.upvote_emoji,
        votes_down_emoji=config.karma.downvote_emoji,
        timeout=config.karma.vote_timeout,
    )
    manager = KarmaManager(config=config)
    for voting in manager.get_expired_votings():
        logger.info("Expired voting: %s", voting)
        reactions = reactions_get(
            client=slack_app.client,
            channel=voting.channel,
            initial_msg_ts=voting.message_ts,
            bot_msg_ts=voting.bot_message_ts,
        )
        success = manager.close_voting(voting, reactions)
        username = lookup_username(slack_app.client, voting.target_id)
        result = _format.voting_result(username, voting.karma, success)
        message_update(slack_app.client, voting.channel, result, voting.bot_message_ts)

    manager.remove_old_votings()


def create_scheduler(url: str):
    """Create a scheduler that saves the state in DB."""
    jobstores = {"default": SQLAlchemyJobStore(url=url)}
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
