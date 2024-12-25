from collections import Counter
from datetime import datetime
from typing import cast
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from karmabot.config import KarmabotConfig
from karmabot.karma_manager import KarmaManager
from karmabot.orm import Karma, Voting
from karmabot.words import Color


def test_get_existing(
    km: KarmaManager, test_user: str, test_channel: str, test_username: str, test_msg: str
):
    km.get(test_user, test_channel)
    transport_mock = cast(MagicMock, km._transport)
    format_mock = cast(MagicMock, km._format)

    transport_mock.lookup_username.assert_called_with(test_user)
    format_mock.report_karma.assert_called_with(test_username, 0)
    transport_mock.post.assert_called_with(test_channel, test_msg)


def test_get_non_existing(
    km: KarmaManager, config: KarmabotConfig, test_msg: str, test_channel: str, test_username: str
):
    km.get("non_existing_user", test_channel)
    transport_mock = cast(MagicMock, km._transport)
    format_mock = cast(MagicMock, km._format)
    transport_mock.lookup_username.assert_called_with("non_existing_user")
    format_mock.report_karma.assert_called_with(test_username, config.karma.initial_value)
    transport_mock.post.assert_called_with(test_channel, test_msg)


def test_set_existing(
    km: KarmaManager, test_user: str, test_channel: str, test_username: str, test_msg: str
):
    karma = 888
    km.set(test_user, karma, test_channel)
    with km._session_maker() as session:
        assert session.query(Karma).filter_by(user_id=test_user).first().karma == karma
    transport_mock = cast(MagicMock, km._transport)
    format_mock = cast(MagicMock, km._format)
    transport_mock.lookup_username.assert_called_with(test_user)
    format_mock.report_karma.assert_called_with(test_username, karma)
    transport_mock.post.assert_called_with(test_channel, test_msg)


def test_set_non_existing(km: KarmaManager, test_channel: str, test_username: str, test_msg: str):
    karma = 888
    km.set("non_existing_user", karma, test_channel)
    with km._session_maker() as session:
        assert session.query(Karma).filter_by(user_id="non_existing_user").first().karma == karma
    transport_mock = cast(MagicMock, km._transport)
    format_mock = cast(MagicMock, km._format)
    transport_mock.lookup_username.assert_called_with("non_existing_user")
    format_mock.report_karma.assert_called_with(test_username, karma)
    transport_mock.post.assert_called_with(test_channel, test_msg)


def test_digest(km: KarmaManager, sample_karma: dict, test_channel: str):
    km.digest()
    calls = [call(u) for u, k in sample_karma.items() if k != 0]
    transport_mock = cast(MagicMock, km._transport)
    format_mock = cast(MagicMock, km._format)
    transport_mock.lookup_username.assert_has_calls(calls=calls, any_order=True)
    format_mock.message.assert_called_with(Color.INFO, ANY)
    transport_mock.post.assert_called_with(test_channel, ANY)


def test_pending_print(
    km: KarmaManager, config: KarmabotConfig, test_user: str, test_channel: str
):
    message_ts = "1.0"
    with km._session_maker() as session:
        session.add(
            Voting(
                message_ts=message_ts,
                bot_message_ts="1.1",
                channel=test_channel,
                target_id=test_user,
                initiator_id=test_user,
                karma=1,
                message_text=f"@bot @{test_user} +",
            )
        )
        session.commit()
    transport_mock = cast(MagicMock, km._transport)
    format_mock = cast(MagicMock, km._format)
    transport_mock.lookup_channel_name.return_value = "general"
    km.pending(test_channel)

    expired_dt = datetime.fromtimestamp(float(message_ts)) + config.karma.vote_timeout
    expired = expired_dt.isoformat()

    expect = "\n".join(
        (
            "*initiator* | *receiver* | *channel* | *karma* | *expired*",
            f"test_user | test_user | general | 1 | {expired}",
        )
    )
    format_mock.message.assert_called_with(Color.INFO, expect)


def test_create(km: KarmaManager, test_channel: str):
    text = "@karmabot @target_id ++"
    ts = 101.0

    with patch("karmabot.parse.Parse.karma_change") as mock_karma_change:
        mock_karma_change.return_value = "karmabot", "target_id", 2
        km.create("init_id", test_channel, text, str(ts))

    with km._session_maker() as session:
        obj = session.query(Voting).first()
    assert float(obj.message_ts) == ts
    assert float(obj.bot_message_ts) == float("123.000000")
    assert obj.channel == test_channel
    assert obj.target_id == "target_id"
    assert obj.initiator_id == "init_id"
    assert obj.karma == 2
    assert obj.message_text == text


@pytest.mark.parametrize(
    "votes, result_karma",
    (
        ({}, 0),
        ({"+1": 1}, 2),
    ),
    ids=("skipped", "up"),
)
def test_close_expired_votes(
    km: KarmaManager,
    votes: dict[str, int],
    result_karma: int,
    config: KarmabotConfig,
    test_user: str,
    test_channel: str,
):
    transport_mock = cast(MagicMock, km._transport)
    transport_mock.reactions_get.return_value = Counter(votes)

    now = datetime.now()
    ts = now.timestamp()
    pending_voting = Voting(
        created=now,
        initiator_id="init_id",
        target_id=test_user,
        channel=test_channel,
        message_ts=ts,
        bot_message_ts=ts,
        message_text=f"@karmabot @{test_user} ++",
        karma=2,
    )
    with km._session_maker() as session:
        session.add(pending_voting)

    now += config.karma.vote_timeout
    km.close_expired_votings()

    with km._session_maker() as session:
        assert session.query(Karma).filter_by(user_id=test_user).first().karma == result_karma
