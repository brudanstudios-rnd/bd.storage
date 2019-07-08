import abc


class VCS(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def is_centralized(self):
        pass

    @abc.abstractmethod
    def get_incremented_version(self, labels, fields, schema, accessor):
        pass

    @abc.abstractmethod
    def get_latest_version(self, labels, fields, schema, accessor):
        pass
