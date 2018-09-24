import logging
import time
from collections import namedtuple
from karmabot.parse import Parse
from karmabot.words import Format, Color
from karmabot.auto_digest import AutoDigest


Command = namedtuple('Command', 'name parser executor admin_only')


class Karmabot:
    REQUIRED_MESSAGE_FIELDS = ('user', 'text', 'ts')
    REQUIRED_EVENT_FIELDS = ('type', 'channel')

    def __init__(self, cfg, transport, fmt, manager):
        self._config = cfg
        self._transport = transport
        self._format = fmt
        self._manager = manager

        self._auto_digest = self._configure_auto_digest()
        if self._auto_digest:
            self._auto_digest_cmd = self._auto_digest.digest
        else:
            self._auto_digest_cmd = lambda: None

        self._logger = logging.getLogger('Karmabot')

        self._commands = [
            Command(name='get', parser=Parse.cmd_get, executor=self._manager.get,
                    admin_only=False),
            Command(name='set', parser=Parse.cmd_set, executor=self._manager.set,
                    admin_only=True),
            Command(name='digest', parser=Parse.cmd_digest, executor=self._manager.digest,
                    admin_only=False),
            Command(name='config', parser=Parse.cmd_config, executor=self._cmd_config,
                    admin_only=False),
            Command(name='help', parser=Parse.cmd_help, executor=self._cmd_help,
                    admin_only=False),
        ]

    def listen(self):
        while True:
            events = self._transport.read()
            for event in events:
                self._logger.debug(f'Processing event: {event}')
                if self._handle_event(event):
                    continue
                self._logger.debug(f'Leaving unhandled: {event}')

            self._manager.close_expired_votes()
            self._auto_digest_cmd()

            if not events:
                time.sleep(0.2)

    def _handle_dm_cmd(self, initiator_id, channel, text):
        # Handling only DM messages and skipping own messages
        if not channel.startswith('D') or self._transport.lookup_username(initiator_id) == 'karmabot':
            return False

        for cmd in self._commands:
            args = cmd.parser(text)
            if not args:
                # Command don't match
                continue

            if type(args) is bool:
                args = []
            elif type(args) is not list:
                args = [args]

            if cmd.admin_only and not self._check_admin_permissions(initiator_id):
                # Command matched, but permissions are wrong
                return True

            if cmd.executor(*args, channel=channel):
                self._logger.debug(f'Executed {cmd.name} command')
            else:
                self._logger.error(f'Failed to execute {cmd.name} commnad')
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

            self._logger.info(f'Team joined by user_id={user_id}')
            return True
        elif event_type == 'message':
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
            if not user_id or self._transport.lookup_username(user_id) != 'karmabot':
                return False
            return self._manager.create(initiator_id, channel, text, ts)

        return False

    def _cmd_help(self, channel):
        self._transport.post(channel, self._format.hello())

    def _cmd_config(self, channel):
        tokens = [f'{k}: {v}' for k, v in vars(self._config).items() if k not in ['TRANSPORT', 'SLACK_BOT_TOKEN']]
        self._transport.post(channel, Format.message(Color.INFO, '\n'.join(tokens)))

    def _check_admin_permissions(self, initiator_id):
        return self._transport.lookup_username(initiator_id) in self._config.ADMINS

    def _configure_auto_digest(self):
        if self._config.AUTO_POST_CHANNEL and self._config.AUTO_POST_DAY:
            result = self._transport.client.api_call('channels.list',
                                                     exclude_archived=True,
                                                     exclude_members=True)
            for c in result.get('channels', []):
                if c['name'] == self._config.AUTO_POST_CHANNEL:
                    auto_digest = AutoDigest(self._config.AUTO_POST_DAY, c['id'], self._manager.digest)
                    logging.debug(f'Auto digest for channel={self._config.AUTO_POST_CHANNEL} configured successfully')
                    return auto_digest

        logging.error(f'Failed to configure auto digest for channel={self._config.AUTO_POST_CHANNEL}')
        return None
