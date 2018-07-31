from karmabot.config import Config
from karmabot.karma_manager import KarmaManager
from karmabot.transport import Transport
from karmabot.words import Format
from karmabot.karmabot import Karmabot


if __name__ == '__main__':
    config = Config()
    t = Transport.create(config.SLACK_BOT_TOKEN)
    f = Format(config.BOT_LANG)
    m = KarmaManager(cfg=config, transport=t, fmt=f)
    bot = Karmabot(config, transport=t, fmt=f, manager=m)
    bot.listen()