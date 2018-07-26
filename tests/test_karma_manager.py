import pytest
import time
from collections import namedtuple, Counter
from karmabot.karma_manager import KarmaManager
from karmabot.words import Color
from karmabot.orm import get_scoped_session, Karma, Voting
from unittest.mock import MagicMock, ANY, call, patch
from .common import *


class Config:
    DB_URI = 'sqlite:///:memory:'
    INITIAL_USER_KARMA = 888
    UPVOTE_EMOJI = ['+1']
    DOWNVOTE_EMOJI = []
    VOTE_TIMEOUT = 0.1
    SELF_KARMA = False
    MAX_SHOT = 10


KarmaManagerWrapper = namedtuple('KarmaManagerWrapper', 'fmt, transport, session, km')


def new_session():
    s = get_scoped_session(Config.DB_URI)
    for u, k in SAMPLE_KARMA.items():
        s.add(Karma(user_id=u, karma=k))
    s.commit()
    return s

@pytest.fixture
def data():
    fmt = MagicMock()
    transport = MagicMock()
    transport.lookup_username.return_value = TEST_USERNAME
    transport.post.return_value = {'ts': '123.000000'}
    fmt.report_karma.return_value = TEST_MSG

    km = KarmaManager(Config(), transport, fmt)
    s = new_session()
    km._session = s
    return KarmaManagerWrapper(fmt, transport, s, km)


def test_get_existing(data):
    data.km.get(TEST_USER, TEST_CHANNEL)

    data.transport.lookup_username.assert_called_with(TEST_USER)
    data.fmt.report_karma.assert_called_with(TEST_USERNAME, TEST_KARMA)
    data.transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_get_non_existing(data):
    data.km.get('non_existing_user', TEST_CHANNEL)

    data.transport.lookup_username.assert_called_with('non_existing_user')
    data.fmt.report_karma.assert_called_with(TEST_USERNAME, Config.INITIAL_USER_KARMA)
    data.transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_set_existing(data):
    karma = 888
    data.km.set(TEST_USER, karma, TEST_CHANNEL)
    assert data.session.query(Karma).filter_by(user_id=TEST_USER).first().karma == karma

    data.transport.lookup_username.assert_called_with(TEST_USER)
    data.fmt.report_karma.assert_called_with(TEST_USERNAME, karma)
    data.transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_set_non_existing(data):
    karma = 888
    data.km.set('non_existing_user', karma, TEST_CHANNEL)
    assert data.session.query(Karma).filter_by(user_id='non_existing_user').first().karma == karma

    data.transport.lookup_username.assert_called_with('non_existing_user')
    data.fmt.report_karma.assert_called_with(TEST_USERNAME, karma)
    data.transport.post.assert_called_with(TEST_CHANNEL, TEST_MSG)

def test_digest(data):
    data.km.digest(TEST_CHANNEL)

    calls = [call(u) for u, k in SAMPLE_KARMA.items() if k != 0]

    data.transport.lookup_username.assert_has_calls(calls=calls, any_order=True)
    data.fmt.message.assert_called_with(Color.INFO, ANY)
    data.transport.post.assert_called_with(TEST_CHANNEL, ANY)


def test_create(data):
    text = '@karmabot @user_id ++'
    ts = 101.0

    with patch('karmabot.parse.Parse.karma_change') as mock_karma_change:
        mock_karma_change.return_value = 'karmabot', 'user_id', 2
        data.km.create('init_id', TEST_CHANNEL, text, ts)

    obj = data.session.query(Voting).first()
    assert obj.initial_msg_ts == ts
    assert obj.bot_msg_ts == float('123.000000')
    assert obj.channel == TEST_CHANNEL
    assert obj.user_id == 'user_id'
    assert obj.initiator_id == 'init_id'
    assert obj.karma == 2
    assert obj.text == text


def test_close_expired_votes_skipped(data):
    data.transport.reactions_get.return_value = Counter()

    ts = time.time()
    expected = Voting(initial_msg_ts=ts,
                      bot_msg_ts=ts,
                      channel=TEST_CHANNEL,
                      user_id=TEST_USER,
                      initiator_id='init_id',
                      karma=2,
                      text='@karmabot @user_id ++')
    data.session.add(expected)

    time.sleep(Config.VOTE_TIMEOUT)
    data.km.close_expired_votes()

    assert data.session.query(Karma).filter_by(user_id=TEST_USER).first().karma == TEST_KARMA

def test_close_expired_votes_up(data):
    data.transport.reactions_get.return_value = Counter({'+1': 1})

    ts = time.time()
    expected = Voting(initial_msg_ts=ts,
                      bot_msg_ts=ts,
                      channel=TEST_CHANNEL,
                      user_id=TEST_USER,
                      initiator_id='init_id',
                      karma=2,
                      text='@karmabot @user_id ++')
    data.session.add(expected)

    time.sleep(Config.VOTE_TIMEOUT)
    data.km.close_expired_votes()

    assert data.session.query(Karma).filter_by(user_id=TEST_USER).first().karma == 2
