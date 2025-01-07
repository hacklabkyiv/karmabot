import pytest

from karmabot.config import KarmabotConfig
from karmabot.karma_manager import KarmaManager
from karmabot.orm import Karma, create_session_maker


@pytest.fixture(scope="session")
def sample_karma(test_user: str) -> dict:
    return {test_user: 0, "uid456": -1, "uid789": 101}


@pytest.fixture(scope="session")
def test_user() -> str:
    return "uid123"


@pytest.fixture(scope="session")
def test_username() -> str:
    return "test_user"


@pytest.fixture(scope="session")
def test_channel() -> str:
    return "C123"


@pytest.fixture(scope="session")
def test_msg() -> str:
    return "message"


@pytest.fixture(scope="session")
def config(test_channel: str) -> KarmabotConfig:
    config_dict = {
        "db": "sqlite:///:memory:",
        "karma": {
            "initial_value": 888,
            "upvote_emoji": ["+1"],
            "downvote_emoji": ["-1"],
            "vote_timeout": 0.1,
            "self_karma": False,
            "max_diff": 10,
            "keep_history": 100000,
        },
        "lang": "en",
        "slack_bot_token": "xobx-123",
        "slack_app_token": "xapp-123",
        "admins": ["omni"],
        "digest": {"day": 1, "channel": test_channel},
        "log_level": "debug",
    }
    return KarmabotConfig.model_validate(config_dict)


@pytest.fixture
def new_session_maker(config: KarmabotConfig, sample_karma: dict):
    session_class = create_session_maker(config.db)
    with session_class() as s:
        for u, k in sample_karma.items():
            s.add(Karma(user_id=u, karma=k))
        s.commit()
    return session_class


@pytest.fixture
def km(
    new_session_maker, config: KarmabotConfig, test_username: str, test_msg: str
) -> KarmaManager:
    km = KarmaManager(config)
    km._session_maker = new_session_maker
    return km
