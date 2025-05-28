import importlib
import importlib.resources
import logging
import pathlib

import click

from .karmabot import Karmabot
from .scheduler import KarmabotScheduler

CONFIG_FILE_NAME = "config.yml"
DEFAULT_CONFIG_PATH = str(pathlib.Path.home() / ".config" / "karmabot" / CONFIG_FILE_NAME)


@click.command(help="karmabot is a Slack bot that manages karma.")
@click.option("-c", "--config", default=DEFAULT_CONFIG_PATH, help="Path to config")
def cli_app(config: str):
    config_path = pathlib.Path(config)
    if not config_path.exists():
        raise click.FileError(config, "Can't locate a config file")
    scheduler = KarmabotScheduler(config_path)
    scheduler.start()
    bot = Karmabot(config_path)
    bot.run()


@click.command(help="Create a default config.")
@click.option("-c", "--config", default=DEFAULT_CONFIG_PATH, help="Path to config")
def cli_init(config: str):
    config_path = pathlib.Path(config)
    if config_path.exists():
        raise click.FileError(config, "The config file already exists")
    data_resource = importlib.resources.files("karmabot.data")
    with importlib.resources.as_file(data_resource) as dir_path:
        default_config_path = dir_path / CONFIG_FILE_NAME
        text = default_config_path.read_text()
    config_path.parent.mkdir(exist_ok=True, parents=True)
    config_path.write_text(text)
    logging.info("Inited with config: %s", text)
