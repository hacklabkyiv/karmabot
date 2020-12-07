import logging
from collections import Counter
from slack import WebClient


class Transport:
    __slots__ = ['client', '_username_cache', '_channel_name_cache', '_logger']

    def __init__(self, token):
        self.client = WebClient(token=token)

        self._username_cache = {}
        self._channel_name_cache = {}
        self._logger = logging.getLogger('Transport')

    def lookup_username(self, user_id):
        user = user_id.strip('<>@')
        username = self._username_cache.get(user)
        if not username:
            userinfo = self.client.users_info(user=user)
            username = userinfo['user']['profile']['display_name']
            self._username_cache[user] = username
        return username

    def lookup_channel_name(self, channel_id):
        channel_id = channel_id.strip('<>@')
        channel_name = self._channel_name_cache.get(channel_id)
        if not channel_name:
            channel_info = self.client.channels_info(channel=channel_id)
            channel_name = channel_info['channel']['name']
            self._channel_name_cache[channel_id] = channel_name
        return channel_name

    def reactions_get(self, channel, initial_msg_ts, bot_msg_ts):
        r = Counter()
        for ts in (initial_msg_ts, bot_msg_ts):
            result = self.client.reactions_get(channel=channel, timestamp=ts)
            self._logger.debug(f'Getting reactions: {result}')

            if 'message' not in result:
                return None

            for c in result['message'].get('reactions', []):
                r[c['name']] += c['count']
        return r

    def post(self, channel, msg, ts=''):
        self._logger.debug(f'Sending message to {channel}: {msg}')
        return self.client.chat_postMessage(channel=channel, link_names=True,
                                            as_user=True, thread_ts=ts, **msg)

    def update(self, channel, msg, ts):
        self._logger.debug(f'Sending update to {channel}: {msg}')
        return self.client.chat_update(channel=channel, link_names=True,
                                       as_user=True, ts=ts, **msg)
