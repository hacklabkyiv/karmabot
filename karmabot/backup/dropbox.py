import os
import logging
from karmabot.backup import BaseBackup
import dropbox
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError
from packer import Packer


class DropboxBackup(BaseBackup):
    __slots__ = ['_logger', '_packer', '_client']

    def __init__(self, client, filenames, key):
        super().__init__(filenames)
        self._logger = logging.getLogger('DropboxBackup')
        self._packer = Packer(key)
        self._client = client

        for f in self._filenames:
            if not os.path.exists(f):
                self.restore(f)

    def __call__(self):
        for f in self._filenames:
            self.backup(f)

    @staticmethod
    def create(token, filenames):
        client = dropbox.Dropbox(token)
        try:
            # Check that the access token is valid
            client.users_get_current_account()
        except AuthError:
            return None

        return DropboxBackup(client, filenames, token)

    def backup(self, filename):
        encrypted_filename = filename + '.enc'
        self._packer.pack(filename, encrypted_filename)

        result = True
        with open(encrypted_filename, 'rb') as f:
            # We use WriteMode=overwrite to make sure that the settings in the file
            # are changed on upload
            self._logger.debug(f'Uploading {encrypted_filename} to Dropbox...')
            try:
                self._client.files_upload(f.read(), filename, mode=WriteMode('overwrite'))
            except ApiError as err:
                # This checks for the specific error where a user doesn't have
                # enough Dropbox space quota to upload this file
                if (err.error.is_path() and
                        err.error.get_path().reason.is_insufficient_space()):
                    self._logger.error('ERROR: Cannot back up; insufficient space.')
                elif err.user_message_text:
                    self._logger.error(err.user_message_text)
                else:
                    self._logger.error(err)
                result = False

        return result

    def restore(self, filename, rev=None):
        encrypted_filename = filename + '.enc'

        # Restore the file on Dropbox to a certain revision
        self._logger.debug(f'Restoring {encrypted_filename} to revision {rev}')
        self._client.files_restore(encrypted_filename, rev)

        # Download the specific revision of the file at BACKUPPATH to LOCALFILE
        self._logger.debug(f'Downloading {encrypted_filename}')
        # self._client.files_download_to_file(LOCALFILE, BACKUPPATH, rev)
        self._client.files_download_to_file(encrypted_filename, encrypted_filename, rev)

        self._packer.unpack(encrypted_filename, filename)
        return True
