import logging
import time
from parse import Parse, Format
from config import Config
import words
from karma_manager import KarmaManager


class Karmabot:
    REQUIRED_MESSAGE_FIELDS = ('user', 'text', 'ts')
    REQUIRED_EVENT_FIELDS = ('type', 'channel')

    def __init__(self, cfg):
        self._config = cfg
        self._manager = KarmaManager(self._config)
        self._logger = logging.getLogger('Karmabot')

    def listen(self):
        while True:
            events = self._config.TRANSPORT.read()
            for event in events:
                self._logger.debug(f'Processing event: {event}')
                if self._handle_event(event):
                    continue
                self._logger.debug(f'Leaving unhandled: {event}')

            self._manager.close_expired_votes()

            if not events:
                time.sleep(0.2)

    def _handle_dm_cmd(self, initiator_id, channel, text):
        if text.startswith('set'):
            if self._check_admin_permissions(initiator_id):
                if not self._cmd_set_user_karma(text, channel):
                    self._logger.fatal(f'Could not handle SET command: {text}')
            return True

        if text.startswith('get'):
            if not self._cmd_get_user_karma(text, channel):
                self._logger.fatal(f'Could not handle GET command: {text}')
            return True

        if text.startswith('config') or text.startswith('cfg'):
            if self._check_admin_permissions(initiator_id):
                self._cmd_config(channel)
            return True

        if text.startswith('help'):
            self._cmd_help(channel)
            return True

        return False

    def _handle_event(self, event):
        if not all(r in event for r in self.REQUIRED_EVENT_FIELDS):
            return False

        event_type = event['type']
        if event_type == 'team_join':
            user_id = event['user']['id']
            new_dm = self._config.TRANSPORT.client.api_call('im.open', user=user_id)
            self._config.TRANSPORT.post(new_dm['channel']['id'], Format.hello())

            self._logger.info(f'Team joined by user_id={user_id}')
            return True
        elif event_type == 'channel_joined' or event_type == 'group_joined':
            channel = event['channel']['id']
            self._config.TRANSPORT.post(channel, Format.hello())

            self._logger.info(f'Karmabot joined a channel={channel}')
            return True
        elif event_type == 'message':
            if not all(f in event for f in self.REQUIRED_MESSAGE_FIELDS):
                return False

            initiator_id = event['user']
            channel = event['channel']
            text = event['text']
            ts = float(event['ts'])

            if channel.startswith('D') and self._handle_dm_cmd(initiator_id, channel, text):
                return True

            # Handle only messages with `@karmabot` at the beginning
            user_id = Parse.user_mention(text)
            if not user_id or self._config.TRANSPORT.lookup_username(user_id) != 'karmabot':
                return False
            return self._manager.create(initiator_id, channel, text, ts)

        return False

    def _cmd_get_user_karma(self, text, channel):
        user_id, error = Parse.cmd_get(text)
        if error:
            self._config.TRANSPORT.post(error, channel)
            return False
        return self._manager.get(user_id, channel)

    def _cmd_set_user_karma(self, text, channel):
        result, error = Parse.cmd_set(text)
        if error:
            self._config.TRANSPORT.post(error, channel)
            return False

        user_id, karma = result
        return self._manager.set(user_id, karma)

    def _cmd_help(self, channel):
        self._config.TRANSPORT.post(channel, Format.hello())

    def _cmd_config(self, channel):
        tokens = [f'{k}: {v}' for k, v in vars(self._config).items() if k not in ['TRANSPORT', 'SLACK_BOT_TOKEN']]
        self._config.TRANSPORT.post(channel, Format.message(words.Color.INFO, '\n'.join(tokens)))

    def _check_admin_permissions(self, initiator_id):
        return self._config.TRANSPORT.lookup_username(initiator_id) in self._config.ADMINS


if __name__ == '__main__':
    config = Config()
    words.init(config.BOT_LANG)
    bot = Karmabot(config)
    bot.listen()
