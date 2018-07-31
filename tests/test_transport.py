import pytest
from unittest.mock import MagicMock, call, patch
from collections import Counter
from karmabot.transport import Transport
from .common import *


@pytest.fixture
def transport():
    return Transport(MagicMock())

@pytest.mark.parametrize('username_cache, should_resolve', [
    [{}, True],
    [{TEST_USER: TEST_USERNAME}, False]
])
def test_lookup_username(transport, username_cache, should_resolve):
    transport._username_cache = username_cache
    transport.client.api_call.return_value = {'user': {'name': TEST_USERNAME}}

    username = transport.lookup_username(TEST_USER)
    assert username == TEST_USERNAME
    if should_resolve:
        transport.client.api_call.assert_called_with('users.info', user=TEST_USER)
    else:
        transport.client.api_call.assert_not_called()

def test_reactions_get(transport):
    init_msg_ts = 123.0
    bot_msg_ts = 456.0

    transport.client.api_call.return_value = {'message': MagicMock()}

    r = transport.reactions_get(TEST_CHANNEL, init_msg_ts, bot_msg_ts)
    assert type(r) is Counter

    calls = [call('reactions.get', channel=TEST_CHANNEL, timestamp=ts) for ts in [init_msg_ts, bot_msg_ts]]
    transport.client.api_call.assert_has_calls(calls, any_order=True)

def test_create():
    with patch('slackclient.SlackClient.rtm_connect') as m:
        m.return_value = True
        t = Transport.create(None)
        assert type(t) is Transport
