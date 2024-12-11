import logging
import logging.config
from pprint import pformat

import yaml

from karmabot.karmabot import Karmabot


def main():
    config = yaml.safe_load(open("config.yml"))
    logging.debug("Config: %s", pformat(config))

    bot = Karmabot(config)
    bot.listen()


if __name__ == "__main__":
    main()
