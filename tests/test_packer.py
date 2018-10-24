import pytest
from tempfile import NamedTemporaryFile
from karmabot.backup.packer import Packer


TEST_DATA = b'test'


def test_pack_unpack(filename):
    encrypted_filename = filename + '.enc'

    packer = Packer(key='test_key')
    packer.pack(filename, encrypted_filename)
    packer.unpack(encrypted_filename, filename)

    with open(filename, 'rb') as f:
        assert(TEST_DATA == f.read())
