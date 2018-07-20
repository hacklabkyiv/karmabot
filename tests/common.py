import pytest


@pytest.fixture(scope='module')
def sample_karma():
    return {
        'uid123': 0,
        'uid456': -1,
        'uid789': 101
    }


TEST_USER = list(sample_karma().keys())[0]
TEST_KARMA = sample_karma()[list(sample_karma().keys())[0]]
TEST_USERNAME = 'test_user'
TEST_CHANNEL = 'test_channel'
TEST_MSG = 'message'
