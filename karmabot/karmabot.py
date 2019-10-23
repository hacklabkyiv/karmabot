import logging
import time
from collections import namedtuple
from karmabot.parse import Parse
from karmabot.words import Format, Color
from karmabot.auto_digest import AutoDigest
from karmabot.karma_manager import KarmaManager
from karmabot.transport import Transport


Command = namedtuple('Command', 'name parser executor admin_only')


def _configure_auto_digest(cfg, transport, manager):
    if not all(k in cfg for k in ('channel', 'day')):
        logging.error('Failed to configure auto digest')
        return None

    result = transport.client.api_call('channels.list', exclude_archived=True,
                                       exclude_members=True)
    channel = cfg['channel']
    for c in result.get('channels', []):
        if c['name'] == channel:
            auto_digest = AutoDigest(cfg['day'], c['id'], manager.digest)
            logging.debug('Auto digest for channel=%s configured successfully',
                          channel)
            return auto_digest
    return None


class Karmabot:
    REQUIRED_MESSAGE_FIELDS = ('user', 'text', 'ts')
    REQUIRED_EVENT_FIELDS = ('type', 'channel')

    def __init__(self, cfg, backup_provider):
        self._config = cfg

        bot_config = self._config['bot']
        karma_config = self._config['karma']
        db_config = self._config['db']

        self._admins = bot_config['admins']

        self._transport = Transport.create(bot_config['slack_token'])
        self._format = Format(bot_config['lang'],
                              karma_config['upvote_emoji'],
                              karma_config['downvote_emoji'],
                              karma_config['vote_timeout'])
        self._manager = KarmaManager(karma_config=karma_config,
                                     db_config=db_config,
                                     transport=self._transport,
                                     fmt=self._format,
                                     backup_provider=backup_provider)

        self._auto_digest = _configure_auto_digest(cfg.get('auto_post'),
                                                   self._transport,
                                                   self._manager)
        self._auto_digest_cmd = getattr(self._auto_digest, 'digest', lambda: None)

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

    def listen(self):
        while True:
            events = self._transport.read()
            for event in events:
                self._logger.debug('Processing event: %s', event)
                if self._handle_event(event):
                    continue
                self._logger.debug('Leaving unhandled: %s', event)

            self._manager.close_expired_votes()
            self._auto_digest_cmd()

            if not events:
                time.sleep(0.2)

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

    def _handle_event(self, event):
        if not all(r in event for r in self.REQUIRED_EVENT_FIELDS):
            return False

        event_type = event['type']
        if event_type == 'team_join':
            user_id = event['user']['id']
            new_dm = self._transport.client.api_call('im.open', user=user_id)
            self._transport.post(new_dm['channel']['id'], self._format.hello())

            self._logger.info('Team joined by user_id=%s', user_id)
            return True

        if event_type == 'message':
            if not all(f in event for f in self.REQUIRED_MESSAGE_FIELDS):
                return False

            initiator_id = event['user']
            channel = event['channel']
            text = event['text']
            ts = event['ts']

            if self._handle_dm_cmd(initiator_id, channel, text):
                return True

            # Don't handle requests from private channels (aka groups)
            if channel.startswith('G'):
                return False

            # Handle only messages with `@karmabot` at the beginning
            user_id = Parse.user_mention(text)
            if not user_id or not self._is_me(user_id):
                return False
            return self._manager.create(initiator_id, channel, text, ts)

        return False

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
