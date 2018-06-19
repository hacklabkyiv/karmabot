import logging
from slackclient import SlackClient
from parse import Format
from words import Color


class Transport:
    def __init__(self, config):
        self._client = SlackClient(config.SLACK_BOT_TOKEN)
        if not self._client.rtm_connect(with_team_state=False,
                                        auto_reconnect=True,
                                        timeout=15):
            raise RuntimeError('Cannot connect to the Slack')

        self._config = config
        self._username_cache = {}

    def read(self):
        return self._client.rtm_read()

    def send_hello(self, user_id=None, channel=None):
        if not (user_id or channel):
            logging.fatal('Can\'t say hello into nowhere')
            return

        if user_id and channel is None:
            new_dm = self._client.api_call('im.open', user=user_id)
            channel = new_dm['channel']['id']
            msg = Format.hello_user(self.lookup_username(user_id))
        else:
            msg = Format.hello_channel()

        logging.debug(f'Sending hello: {msg}')
        self._post(channel, msg)

    def send_help(self, channel):
        logging.debug('Sending help')
        return self.send_hello(channel=channel)

    def send_error(self, msg, channel, ts=None):
        logging.debug(f'Sending error: {msg}')
        return self._post(channel, msg, ts=ts)

    def create_voting(self, karma_change):
        username = self.lookup_username(karma_change.user_id)
        msg = Format.new_voting(username,
                                karma_change.karma,
                                self._config.UPVOTE_EMOJI,
                                self._config.DOWNVOTE_EMOJI,
                                self._config.VOTE_TIMEOUT)

        logging.debug(f'Sending message: {msg}')
        return self._post(karma_change.channel, msg, ts=karma_change.initial_msg_ts)

    def close_voting(self, karma_change, success):
        username = self.lookup_username(karma_change.user_id)
        msg = Format.voting_result(username, karma_change.karma, success)

        logging.debug(f'Sending update: {msg}')
        return self._update(karma_change.channel, karma_change.bot_msg_ts, msg)

    def get_reactions(self, channel, initial_msg_ts, bot_msg_ts):
        i = self._client.api_call('reactions.get', channel=channel, timestamp=initial_msg_ts)
        logging.debug(f'initial_msg: {i}')
        if 'message' in i and i['message']:
            initial_msg = i['message']
        else:
            initial_msg = None

        b = self._client.api_call('reactions.get', channel=channel, timestamp=bot_msg_ts)
        logging.debug(f'bot_msg: {b}')
        if 'message' in b and b['message']:
            bot_msg = b['message']
        else:
            bot_msg = None

        return initial_msg, bot_msg

    def report_karma(self, user_id, karma, channel):
        username = self.lookup_username(user_id)
        msg = Format.report_karma(username, karma)

        logging.debug(f'Sending message: {msg}')
        return self._post(channel, msg)

    def lookup_username(self, userid):
        user = userid.strip('<>@')
        username = self._username_cache.get(user)
        if not username:
            userinfo = self._client.api_call('users.info', user=user)
            username = userinfo['user']['name']
            self._username_cache[user] = username
        return username

    def _post(self, channel, message, ts=''):
        return self._client.api_call('chat.postMessage',
                                     link_names=1,
                                     as_user=True,
                                     channel=channel,
                                     username='karmabot',
                                     icon_emoji=self._config.BOT_EMOJI,
                                     thread_ts=ts,
                                     **message)

    def _update(self, channel, ts, message):
        return self._client.api_call('chat.update',
                                     link_names=1,
                                     as_user=True,
                                     channel=channel,
                                     username='karmabot',
                                     icon_emoji=self._config.BOT_EMOJI,
                                     ts=ts,
                                     **message)
