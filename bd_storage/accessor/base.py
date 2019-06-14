import abc
from .. import utils


class Accessor(object):

    __metaclass__ = abc.ABCMeta

    @utils.abstractclassmethod
    def new(cls, **kwargs):
        pass

    def resolve(self, uid):
        return uid

    @abc.abstractmethod
    def read(self, uid):
        pass

    @abc.abstractmethod
    def write(self, uid, data):
        pass

    @abc.abstractmethod
    def make_dir(self, uid):
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
    def list(self, uid, relative=False):
        pass

    @abc.abstractmethod
    def join(self, *args):
        pass

    @abc.abstractmethod
    def rm(self, uid):
        pass
