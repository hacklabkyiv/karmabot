import os
import random
import struct
import lzma
from Crypto.Cipher import AES


class Packer:
    """
    packer/unpacker with LZMA compression and AES [CBC mode] encryption
    """
    def __init__(self, key: str, chunksize: int = 64*1024):
        """
        :param key: an encryption key. will be shrinked to 32 bytes
        :param chunksize: a size of chunk
        """
        self._key = ['0'] * 32
        for c in range(min(32, len(key))):
            self._key[c] = key[c]
        self._key = ''.join(self._key)

        self._chunk_size = chunksize

    def pack(self, filename, output_filename):
        """
        pack a file with @filename
        """
        with open(filename, 'rb') as f:
            with open(output_filename, 'wb') as e:
                iv = bytes(random.randint(0, 0xFF) for i in range(16))
                encryptor = AES.new(self._key, AES.MODE_CBC, iv)

                e.write(iv)
                # reserve the space for a size record
                e.write(struct.pack('<Q', 0))

                compressed_file_size = 0
                buffer = bytes()

                data = f.read(self._chunk_size)
                while data:
                    buffer += lzma.compress(data)
                    if len(buffer) > self._chunk_size:
                        compressed_data = buffer[:self._chunk_size]
                        buffer = buffer[self._chunk_size:]

                        compressed_file_size += self._chunk_size
                        e.write(encryptor.encrypt(compressed_data))
                    data = f.read(self._chunk_size)

                oversize = len(buffer) % 16
                if buffer:
                    # don't include trailing zeros
                    compressed_file_size += len(buffer)

                    if oversize:
                        buffer += b'0' * (16 - oversize)
                    e.write(encryptor.encrypt(buffer))

                if compressed_file_size:
                    e.seek(16, 0)
                    e.write(struct.pack('<Q', compressed_file_size))
                    e.seek(0, 2)

    def unpack(self, filename, output_filename):
        with open(filename, 'rb') as e:
            with open(output_filename, 'wb') as f:
                iv = e.read(16)
                decryptor = AES.new(self._key, AES.MODE_CBC, iv)

                compressed_file_size = struct.unpack('<Q', e.read(struct.calcsize('Q')))[0]
                buffer = bytes()

                data = e.read(self._chunk_size)
                while data:
                    buffer += decryptor.decrypt(data)
                    if len(buffer) > self._chunk_size:
                        decrypted_data = buffer[:self._chunk_size]
                        buffer = buffer[self._chunk_size:]

                        compressed_file_size -= self._chunk_size
                        f.write(lzma.decompress(decrypted_data))
                    
                    data = e.read(self._chunk_size)

                if buffer:
                    assert len(buffer) <= self._chunk_size
                    buffer = buffer[:compressed_file_size]
                    f.write(lzma.decompress(buffer))
