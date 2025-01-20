from datetime import datetime, timedelta, timezone

import pytest

from karmabot.config import KarmabotConfig
from karmabot.karma_manager import KarmaManager
from karmabot.orm import Voting


@pytest.mark.usefixtures("seed_sample_karma")
def test_get_existing(km: KarmaManager, sample_karma: dict[str, int]):
    for user_id, karma in sample_karma.items():
        real_karma = km.get(user_id)
        assert real_karma == karma, f"{user_id} has {real_karma} karma but {karma} expected"


@pytest.mark.usefixtures("seed_sample_karma")
def test_get_non_existing(km: KarmaManager):
    assert km.get("non_existing_user") == 0


@pytest.mark.usefixtures("seed_sample_karma")
def test_set_existing(km: KarmaManager, test_user: str):
    karma = 888
    km.set(test_user, karma)
    assert km.get(test_user) == karma


@pytest.mark.usefixtures("seed_sample_karma")
def test_set_non_existing(km: KarmaManager):
    karma = 888
    user_id = "non_existing_user"
    km.set(user_id, karma)
    assert km.get(user_id) == karma


@pytest.mark.usefixtures("seed_sample_karma")
def test_digest(km: KarmaManager, sample_karma: dict[str, int]):
    digest = km.digest()
    assert len(digest) == sum(1 for v in sample_karma.values() if v != 0)
    for karma_record in digest:
        assert karma_record.karma == sample_karma.get(karma_record.user_id)


@pytest.mark.usefixtures("cleanup_voting_table")
def test_pending_print(km: KarmaManager, test_user: str, test_channel: str):
    message_ts = datetime.fromtimestamp(1.0, tz=timezone.utc)
    bot_message_ts = message_ts + timedelta(seconds=1)
    with km._session_maker.begin() as session:
        session.add(
            Voting(
                message_ts=message_ts,
                bot_message_ts=bot_message_ts,
                channel=test_channel,
                target_id=test_user,
                initiator_id=test_user,
                karma=1,
                message_text=f"@karmabot @{test_user} +",
            )
        )
    pending = km.pending()
    assert len(pending) == 1
    assert pending[0].message_ts == message_ts
    assert pending[0].bot_message_ts == bot_message_ts


@pytest.mark.usefixtures("cleanup_voting_table")
def test_create(km: KarmaManager, test_channel: str):
    initiator_id = "init_id"
    target_id = "target_id"
    text = "@karmabot @target_id ++"
    ts = "101.0"
    bot_message_ts = "102.0"
    km.create(
        initiator_id=initiator_id,
        target_id=target_id,
        channel=test_channel,
        text=text,
        ts=ts,
        bot_message_ts=bot_message_ts,
        karma=2,
    )

    with km._session_maker() as session:
        obj = session.query(Voting).first()
    assert obj.initiator_id == initiator_id
    assert obj.target_id == target_id
    assert obj.channel == test_channel
    assert obj.message_text == text
    assert str(obj.message_ts.timestamp()) == ts
    assert str(obj.bot_message_ts.timestamp()) == bot_message_ts
    assert obj.karma == 2


@pytest.mark.usefixtures("cleanup_voting_table")
@pytest.mark.parametrize(
    "votes, result_karma",
    (
        ({}, 0),
        ({"+1": 1}, 2),
    ),
    ids=("skipped", "up"),
)
def test_get_expired_votings(
    km: KarmaManager,
    votes: dict[str, int],
    result_karma: int,
    config: KarmabotConfig,
    test_user: str,
    test_channel: str,
):
    message_ts = datetime.now(tz=timezone.utc) - config.karma.vote_timeout * 2
    bot_message_ts = message_ts + config.karma.vote_timeout
    with km._session_maker.begin() as session:
        session.add(
            Voting(
                message_ts=message_ts,
                bot_message_ts=bot_message_ts,
                channel=test_channel,
                target_id=test_user,
                initiator_id=test_user,
                karma=1,
                message_text=f"@karmabot @{test_user} +",
            )
        )
        session.add(
            Voting(
                closed=True,
                message_ts=message_ts,
                bot_message_ts=bot_message_ts,
                channel=test_channel,
                target_id=test_user,
                initiator_id=test_user,
                karma=1,
                message_text=f"@karmabot @{test_user} +",
            )
        )
    expired = km.get_expired_votings()
    assert len(expired) == 1
    assert expired[0].message_ts == message_ts


def test_close_voting():
    pass


def test_remove_old_votings():
    pass
