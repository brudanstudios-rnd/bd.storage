import abc
from .. import utils


class Structure(object):

    @utils.abstractclassmethod
    def new(cls, accessor, **kwargs):
        pass

    @abc.abstractmethod
    def get_uid(self, labels, context):
        pass

    @abc.abstractmethod
    def make_dirs(self, labels, context):
        pass