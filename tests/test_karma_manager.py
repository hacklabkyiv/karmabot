import pytest
import time
from collections import namedtuple, Counter
from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock, ANY, call, patch

from karmabot.karma_manager import KarmaManager
from karmabot.words import Color
from karmabot.orm import get_scoped_session, Karma, Voting
from .common import *


CONFIG = {
    'db': {
        'type': 'sqlite',
        'name': ':memory:',
    },
    'karma': {
        'initial_value': 888,
        'upvote_emoji': ['+1'],
        'downvote_emoji': ['-1'],
        'vote_timeout': 0.1,
        'self_karma': False,
        'max_shot': 10,
        'keep_history': 100000,
    }
}


@pytest.fixture
def new_session():
    s = get_scoped_session(CONFIG['db'])
    for u, k in SAMPLE_KARMA.items():
        s.add(Karma(user_id=u, karma=k))
    s.commit()
    return s


@pytest.fixture
def transport():
    transport = MagicMock()
    transport.lookup_username.return_value = TEST_USERNAME
    transport.post.return_value = {'ts': '123.000000'}
    return transport


@pytest.fixture
def fmt():
    fmt = MagicMock()
    fmt.report_karma.return_value = TEST_MSG
    return fmt


@pytest.fixture
def km(transport, fmt, new_session):
    km = KarmaManager(CONFIG['karma'], CONFIG['db'], transport, fmt, MagicMock())
    km._session = new_session
    return km


def test_get_existing(km):
    km.get(TEST_USER, TEST_CHANNEL)

    km._transport.lookup_username.assert_called_with(TEST_USER)
    km._format.report_karma.assert_called_with(TEST_USERNAME, TEST_KARMA)
    km._transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_get_non_existing(km):
    km.get('non_existing_user', TEST_CHANNEL)

    km._transport.lookup_username.assert_called_with('non_existing_user')
    km._format.report_karma.assert_called_with(
        TEST_USERNAME, CONFIG['karma']['initial_value'])
    km._transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_set_existing(km):
    karma = 888
    km.set(TEST_USER, karma, TEST_CHANNEL)
    assert km._session.query(Karma).filter_by(user_id=TEST_USER).first().karma == karma

    km._transport.lookup_username.assert_called_with(TEST_USER)
    km._format.report_karma.assert_called_with(TEST_USERNAME, karma)
    km._transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_set_non_existing(km):
    karma = 888
    km.set('non_existing_user', karma, TEST_CHANNEL)
    assert km._session.query(Karma).filter_by(user_id='non_existing_user').first().karma == karma

    km._transport.lookup_username.assert_called_with('non_existing_user')
    km._format.report_karma.assert_called_with(TEST_USERNAME, karma)
    km._transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_digest(km):
    km.digest(TEST_CHANNEL)

    calls = [call(u) for u, k in SAMPLE_KARMA.items() if k != 0]

    km._transport.lookup_username.assert_has_calls(calls=calls, any_order=True)
    km._format.message.assert_called_with(Color.INFO, ANY)
    km._transport.post.assert_called_with(TEST_CHANNEL, ANY)

def test_pending_print(km):
    message_ts = '1.0'
    km._session.add(Voting(message_ts=message_ts,
                           bot_message_ts='1.1',
                           channel=TEST_CHANNEL,
                           target_id=TEST_USER,
                           initiator_id=TEST_USER,
                           karma=1,
                           message_text=f'@bot @{TEST_USER} +'))
    km._session.commit()

    km._transport.lookup_channel_name.return_value = 'general'
    km.pending(TEST_CHANNEL)

    expired = datetime.fromtimestamp(float(message_ts)) + timedelta(
        seconds=CONFIG['karma']['vote_timeout'])
    expired = expired.isoformat()

    expect = '\n'.join(('*initiator* | *receiver* | *channel* | *karma* | *expired*',
                        f'test_user | test_user | general | 1 | {expired}'))
    km._format.message.assert_called_with(Color.INFO, expect)

def test_create(km):
    text = '@karmabot @target_id ++'
    ts = 101.0

    with patch('karmabot.parse.Parse.karma_change') as mock_karma_change:
        mock_karma_change.return_value = 'karmabot', 'target_id', 2
        km.create('init_id', TEST_CHANNEL, text, ts)

    obj = km._session.query(Voting).first()
    assert float(obj.message_ts) == ts
    assert float(obj.bot_message_ts) == float('123.000000')
    assert obj.channel == TEST_CHANNEL
    assert obj.target_id == 'target_id'
    assert obj.initiator_id == 'init_id'
    assert obj.karma == 2
    assert obj.message_text == text

@pytest.mark.parametrize('votes, result_karma', (
    ({}, TEST_KARMA),
    ({'+1': 1}, 2),
), ids=('skipped', 'up'))
def test_close_expired_votes(km, votes, result_karma):
    km._transport.reactions_get.return_value = Counter(votes)

    now = datetime.now()
    ts = now.timestamp()
    expected = Voting(created=now,
                      initiator_id='init_id',
                      target_id=TEST_USER,
                      channel=TEST_CHANNEL,
                      message_ts=ts,
                      bot_message_ts=ts,
                      message_text='@karmabot @target_id ++',
                      karma=2)
    km._session.add(expected)

    now += timedelta(seconds=CONFIG['karma']['vote_timeout'])
    km.close_expired_votings(now)

    assert km._session.query(Karma).filter_by(user_id=TEST_USER).first().karma == result_karma
