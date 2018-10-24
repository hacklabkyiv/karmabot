from abc import ABC, abstractmethod


class BaseBackup(ABC):
    __slots__ = ['_filenames']

    def __init__(self, filenames):
        self._filenames = filenames

    @abstractmethod
    def backup(self, filename):
        pass

    @abstractmethod
    def restore(self, filename, rev=None):
        pass
