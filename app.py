import yaml
import logging
import logging.config
from pprint import pformat

from karmabot.karmabot import Karmabot


def main():
    config = yaml.safe_load(open('config.yml', 'r'))
    logging_config = yaml.safe_load(open('logging.yml', 'r'))
    logging_config['root']['level'] = config['log_level']
    logging.config.dictConfig(logging_config)

    logging.debug('Config: {}'.format(pformat(config)))

    bot = Karmabot(config)
    bot.listen()


if __name__ == '__main__':
    main()
