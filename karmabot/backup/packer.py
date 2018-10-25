import os
import random
import struct
import lzma
import base64
from cryptography.fernet import Fernet


class Packer:
    """
    packer/unpacker with LZMA compression and AES in CBC mode with a 128-bit key encryption
    """

    __slots__ = ['_key', '_chunk_size']

    def __init__(self, key: str, chunksize: int = 64*1024):
        """
        :param key: an encryption key. will be shrinked to 32 bytes
        :param chunksize: a size of chunk
        """
        self._key = ['0'] * 32
        for c in range(min(32, len(key))):
            self._key[c] = key[c]
        self._key = base64.urlsafe_b64encode(''.join(self._key).encode('utf-8'))

        self._chunk_size = chunksize

    def pack(self, filename, output_filename):
        """
        pack a file with @filename
        """
        with open(filename, 'rb') as f:
            with open(output_filename, 'wb') as e:
                encryptor = Fernet(self._key)

                buffer = bytes()
                data = f.read(self._chunk_size)
                while data:
                    buffer += lzma.compress(data)
                    if len(buffer) > self._chunk_size:
                        compressed_data = buffer[:self._chunk_size]
                        buffer = buffer[self._chunk_size:]

                        e.write(encryptor.encrypt(compressed_data))
                    data = f.read(self._chunk_size)

                if buffer:
                    e.write(encryptor.encrypt(buffer))

    def unpack(self, filename, output_filename):
        with open(filename, 'rb') as e:
            with open(output_filename, 'wb') as f:
                decryptor = Fernet(self._key)

                buffer = bytes()
                data = e.read(self._chunk_size)
                while data:
                    buffer += decryptor.decrypt(data)
                    if len(buffer) > self._chunk_size:
                        decrypted_data = buffer[:self._chunk_size]
                        buffer = buffer[self._chunk_size:]

                        f.write(lzma.decompress(decrypted_data))
                    data = e.read(self._chunk_size)

                if buffer:
                    f.write(lzma.decompress(buffer))
