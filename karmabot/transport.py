import logging
from collections import Counter
from slackclient import SlackClient
import time


class Transport:
    __slots__ = ['client', '_username_cache', '_channel_name_cache', '_logger']

    def __init__(self, client):
        self.client = client
        self._username_cache = {}
        self._channel_name_cache = {}
        self._logger = logging.getLogger('Transport')

    @staticmethod
    def create(token):
        client = SlackClient(token)
        while not client.rtm_connect(with_team_state=False,
                                     auto_reconnect=True,
                                     timeout=15):
            logging.getLogger('Transport').debug('Cannot connect to the Slack. Reconnecting in 3seconds...')
            time.sleep(3)
        return Transport(client)

    def read(self):
        return self.client.rtm_read()

    def lookup_username(self, user_id):
        user = user_id.strip('<>@')
        username = self._username_cache.get(user)
        if not username:
            userinfo = self.client.api_call('users.info', user=user)
            username = userinfo['user']['name']
            self._username_cache[user] = username
        return username

    def lookup_channel_name(self, channel_id):
        channel_id = channel_id.strip('<>@')
        channel_name = self._channel_name_cache.get(channel_id)
        if not channel_name:
            channel_info = self.client.api_call('channels.info', channel=channel_id)
            channel_name = channel_info['channel']['name']
            self._channel_name_cache[channel_id] = channel_name
        return channel_name

    def reactions_get(self, channel, initial_msg_ts, bot_msg_ts):
        r = Counter()
        for ts in (initial_msg_ts, bot_msg_ts):
            result = self.client.api_call('reactions.get',
                                          channel=channel,
                                          timestamp=ts)
            self._logger.debug(f'Getting reactions: {result}')

            if 'message' not in result:
                return None

            for c in result['message'].get('reactions', []):
                r[c['name']] += c['count']
        return r

    def post(self, channel, msg, ts=''):
        self._logger.debug(f'Sending message: {msg}')
        return self.client.api_call('chat.postMessage',
                                    link_names=1,
                                    as_user=True,
                                    channel=channel,
                                    thread_ts=ts,
                                    **msg)

    def update(self, channel, msg, ts):
        self._logger.debug(f'Sending update: {msg}')
        return self.client.api_call('chat.update',
                                    link_names=1,
                                    as_user=True,
                                    channel=channel,
                                    ts=ts,
                                    **msg)
