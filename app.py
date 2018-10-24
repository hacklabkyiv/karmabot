from karmabot.config import Config
from karmabot.karma_manager import KarmaManager
from karmabot.transport import Transport
from karmabot.words import Format
from karmabot.karmabot import Karmabot


def get_backup_provider(config):
    if config.BACKUP_DROPBOX:
        from karmabot.backup.dropbox import DropboxBackup
        return DropboxBackup.create(config.BACKUP_DROPBOX, ['karma.db'])

    return None


if __name__ == '__main__':
    config = Config()
    b = get_backup_provider(config)
    t = Transport.create(config.SLACK_BOT_TOKEN)
    f = Format(config.BOT_LANG,
               config.UPVOTE_EMOJI,
               config.DOWNVOTE_EMOJI,
               config.VOTE_TIMEOUT)
    m = KarmaManager(cfg=config, 
                     transport=t, 
                     fmt=f, 
                     backup_provider=b)
    bot = Karmabot(config, 
                   transport=t, 
                   fmt=f, 
                   manager=m)
    bot.listen()