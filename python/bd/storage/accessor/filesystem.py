import os
import logging

from .base import Accessor

LOGGER = logging.getLogger(__name__)


class FileSystemAccessor(Accessor):

    name = "filesystem-accessor"

    def __init__(self, root):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/')

    @classmethod
    def new(cls, **kwargs):
        root = kwargs.get("root")
        return cls(root)

    def resolve(self, uid):
        if not self._root:
            return uid
        return '/'.join([self._root, uid])

    def write(self, uid, data):
        return open(self.resolve(uid), "wb").write(data)

    def read(self, uid):
        return open(self.resolve(uid), "rb").read()

    def make_dir(self, uid):
        os.mkdir(self.resolve(uid))

    def exists(self, uid):
        return os.path.exists(self.resolve(uid))

    def get_filesystem_path(self, uid, mode):
        return self.resolve(uid)