import pathlib

import yaml
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from .config import KarmabotConfig
from .karma_manager import KarmaManager
from .transport import Transport
from .words import Format


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
    transport = Transport(config)
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
    transport = Transport(config)
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
