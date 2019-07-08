import abc


class Accessor(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, root):
        self._root = root

    def root(self):
        return self._root

    def resolve(self, uid):
        return uid

    @abc.abstractmethod
    def read(self, uid):
        pass

    @abc.abstractmethod
    def write(self, uid, data):
        pass

    @abc.abstractmethod
    def make_dir(self, uid, recursive=False):
        pass

    @abc.abstractmethod
    def is_dir(self, uid):
        pass

    @abc.abstractmethod
    def is_file(self, uid):
        pass

    @abc.abstractmethod
    def exists(self, uid):
        pass

    @abc.abstractmethod
    def list(self, uid, relative=False, recursive=True):
        pass

    @abc.abstractmethod
    def join(self, *args):
        pass

    @abc.abstractmethod
    def rm(self, uid):
        pass
