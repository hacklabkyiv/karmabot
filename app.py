import yaml
import logging
from pprint import pformat

from karmabot.karmabot import Karmabot


def get_backup_provider(config):
    if config.BACKUP_DROPBOX:
        from karmabot.backup.dropbox import DropboxBackup
        return DropboxBackup.create(config.BACKUP_DROPBOX, ['karma.db'])

    return None


if __name__ == '__main__':
    config = yaml.safe_load(open('config.yml', 'r'))
    logging_config = yaml.safe_load(open('logging.yml', 'r'))
    logging_config['root']['level'] = config['log_level']
    logging.config.dictConfig(logging_config)

    logging.debug('Config: {}'.format(pformat(config)))

    b = get_backup_provider(config)
    bot = Karmabot(config, backup_provider=b)
    bot.listen()
