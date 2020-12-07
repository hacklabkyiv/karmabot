import logging
import time
from collections import namedtuple
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from slack import RTMClient

from karmabot.parse import Parse
from karmabot.words import Format, Color
from karmabot.karma_manager import KarmaManager
from karmabot.transport import Transport


Command = namedtuple('Command', 'name parser executor admin_only')


def _get_auto_digest_config(cfg, transport):
    if not all(k in cfg for k in ('channel', 'day')):
        logging.error('Failed to configure auto digest')
        return None

    channel = cfg['channel']
    result = transport.client.api_call('channels.list', exclude_archived=True,
                                       exclude_members=True)
    for c in result.get('channels', []):
        if c['name'] == channel:
            return {'channel': c['id'], 'day': cfg['day']}
    return {}


def _make_scheduler():
    jobstores = {'default': SQLAlchemyJobStore(tablename='karmabot_scheduler')}
    executors = {'default': ProcessPoolExecutor()}
    job_defaults = {
        'coalesce': True,  # run only once if turns out we need to run > 1 time
        'max_instances': 1  # max number of job of one type running simultaneously
    }
    scheduler = BackgroundScheduler(jobstores=jobstores,
                                    executors=executors,
                                    job_defaults=job_defaults)
    return scheduler


class Karmabot:
    REQUIRED_MESSAGE_FIELDS = ('user', 'text', 'ts', 'type', 'channel')

    def __init__(self, cfg):
        self._config = cfg

        bot_config = self._config['bot']
        karma_config = self._config['karma']
        db_config = self._config['db']

        self._admins = bot_config['admins']

        self._transport = Transport(bot_config['slack_token'])
        self._format = Format(bot_config['lang'],
                              karma_config['upvote_emoji'],
                              karma_config['downvote_emoji'],
                              karma_config['vote_timeout'])

        digest_cfg = _get_auto_digest_config(cfg.get('auto_post'))
        self._manager = KarmaManager(karma_config=karma_config,
                                     digest_channel=digest_cfg.get('channel'),
                                     db_config=db_config,
                                     transport=self._transport,
                                     fmt=self._format)

        if digest_cfg:
            self._auto_digest = _make_scheduler()
            self._auto_digest.add_job(
                self._manager.digest,
                id='auto_digest',
                trigger='cron',
                minute=digest_cfg.get('day')
            )
            self._auto_digest.start()

        self._logger = logging.getLogger('Karmabot')

        self._commands = [
            Command(name='get', parser=Parse.cmd_get,
                    executor=self._manager.get, admin_only=False),
            Command(name='set', parser=Parse.cmd_set,
                    executor=self._manager.set, admin_only=True),
            Command(name='digest', parser=Parse.cmd_digest,
                    executor=self._manager.digest, admin_only=False),
            Command(name='config', parser=Parse.cmd_config,
                    executor=self._cmd_config, admin_only=False),
            Command(name='help', parser=Parse.cmd_help,
                    executor=self._cmd_help, admin_only=False),
        ]

        self._slack_reader = RTMClient(token=bot_config['slack_token'])
        self._slack_reader.start()

    def listen(self):
        while True:
            now = time.time()
            self._manager.close_expired_votings(now)
            self._manager.remove_old_votings()

            if not self._transport.events:
                time.sleep(0.1)

    def _handle_dm_cmd(self, initiator_id, channel, text):
        # Handling only DM messages and skipping own messages
        if not channel.startswith('D') or self._is_me(initiator_id):
            return False

        for cmd in self._commands:
            args = cmd.parser(text)
            if not args:
                # Command don't match
                continue

            if isinstance(args, bool):
                args = []
            elif not isinstance(args, list):
                args = [args]

            if cmd.admin_only and not self._is_admin(initiator_id):
                # Command matched, but permissions are wrong
                return True

            if cmd.executor(*args, channel=channel):
                self._logger.debug('Executed %s command', cmd.name)
            else:
                self._logger.error('Failed to execute %s commnad', cmd.name)
            return True

        self._transport.post(channel, self._format.cmd_error())
        return False

    @RTMClient.run_on(event='team_join')
    def _handle_team_join(self, **payload):
        event = payload['data']
        self._logger.debug('Processing event: %s', event)
        user_id = event['user']['id']
        new_dm = self._transport.client.api_call('im.open', user=user_id)
        self._transport.post(new_dm['channel']['id'], self._format.hello())

        self._logger.info('Team joined by user_id=%s', user_id)
        return True

    @RTMClient.run_on(event='message')
    def _handle_message(self, **payload):
        event = payload['data']
        self._logger.debug('Processing event: %s', event)

        if not all(r in event for r in self.REQUIRED_MESSAGE_FIELDS):
            self._logger.debug('Not enough fields for: %s', event)
            return False

        initiator_id = event['user']
        channel = event['channel']
        text = event['text']
        ts = event['ts']

        if self._handle_dm_cmd(initiator_id, channel, text):
            return True

        # Don't handle requests from private channels (aka groups)
        if channel.startswith('G'):
            self._logger.debug('Skip message in group %s', channel)
            return False

        # Handle only messages with `@karmabot` at the beginning
        user_id = Parse.user_mention(text)
        if not user_id or not self._is_me(user_id):
            self._logger.debug('Skip message not for bot: %s', text)
            return False
        return self._manager.create(initiator_id, channel, text, ts)

    def _cmd_help(self, channel):
        self._transport.post(channel, self._format.hello())

    def _cmd_config(self, channel):
        tokens = [
            f'{k}: {v}' for k, v in self._config.items()
            if k not in ['transport', 'slack_bot_token']
        ]
        self._transport.post(channel, Format.message(Color.INFO, '\n'.join(tokens)))

    def _is_admin(self, initiator_id):
        return self._transport.lookup_username(initiator_id) in self._admins

    def _is_me(self, initiator_id):
        return self._transport.lookup_username(initiator_id) == 'karmabot'
