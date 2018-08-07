import os
import logging

from .base import Accessor

LOGGER = logging.getLogger(__name__)


class FileSystemAccessor(Accessor):

    name = "filesystem-accessor"

    def __init__(self, root):
        self._root = root.replace('\\', '/')

    @classmethod
    def new(cls, **kwargs):
        root = kwargs.get("root")

        if not root:
            LOGGER.error("Unspecified 'root' argument for '{}'".format(cls.name))
            return

        return cls(root)

    def resolve(self, uid):
        return '/'.join([self._root, uid])

    def is_file(self, uid):
        return os.path.isfile(self.resolve(uid))

    def is_dir(self, uid):
        return os.path.isdir(self.resolve(uid))

    def open(self, uid, mode="rb"):
        return open(self.resolve(uid), mode)

    def make_dir(self, uid):
        os.mkdir(self.resolve(uid))

    def list_dir(self, uid):
        path = self.resolve(uid)
        return map(lambda x: os.path.join(path, x),
                   os.listdir(path))

    def get_filesystem_path(self, uid):
        return self.resolve(uid)

    def exists(self, uid):
        return os.path.exists(self.resolve(uid))