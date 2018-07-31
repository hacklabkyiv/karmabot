import os
import logging


class Config:
    def __init__(self):
        self.BOT_LANG = os.environ.get('BOT_LANG', default='en')
        self.DB_URI = os.environ.get('DB_URI', default='sqlite:///karma.db')
        self.SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')

        self.INITIAL_USER_KARMA = int(os.environ.get('INITIAL_USER_KARMA', default=0))
        self.MAX_SHOT = int(os.environ.get('MAX_SHOT', default=5))
        self.VOTE_TIMEOUT = float(os.environ.get('VOTE_TIMEOUT', default=3 * 60 * 60))  # seconds
        self.UPVOTE_EMOJI = os.environ.get('UPVOTE_EMOJI', default='+1,partyparrot,thumbsup,thumbsup_all')\
                                      .replace(',', ' ').split()
        self.DOWNVOTE_EMOJI = os.environ.get('DOWNVOTE_EMOJI', default='-1,thumbsdown').replace(',', ' ').split()
        self.SELF_KARMA = os.environ.get('SELF_KARMA', default='false').lower() in ['true', '1', 'y', 'yes']
        self.ADMINS = os.environ.get('ADMINS').replace(',', ' ').split()

        self.AUTO_POST_CHANNEL = os.environ.get('AUTO_POST_CHANNEL', default='').strip('@# ')
        self.AUTO_POST_DAY = int(os.environ.get('AUTO_POST_DAY', default=1))

        self.LOG_LEVEL = logging.getLevelName(os.environ.get('LOG_LEVEL', default='INFO').upper())

        logging.basicConfig(format='%(asctime)s %(name)s [%(levelname)s] %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=self.LOG_LEVEL)
        logging.getLogger('Config').debug(vars(self))
