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
    def open(self, uid):
        pass

    @abc.abstractmethod
    def make_dir(self, uid):
        pass

    @abc.abstractmethod
    def exists(self, uid):
        pass

    @abc.abstractmethod
    def rm(self, uid):
        pass
