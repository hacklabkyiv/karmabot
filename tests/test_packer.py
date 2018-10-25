import pytest
from tempfile import NamedTemporaryFile
from karmabot.backup.packer import Packer


TEST_DATA = b'test'

@pytest.fixture
def filename():
    with NamedTemporaryFile(mode='wb', delete=False) as o:
        o.write(TEST_DATA)
        return o.name


def test_pack_unpack(filename):
    encrypted_filename = filename + '.enc'

    packer = Packer(key='test_key')
    packer.pack(filename, encrypted_filename)
    packer.unpack(encrypted_filename, filename)

    with open(filename, 'rb') as f:
        assert(TEST_DATA == f.read())
