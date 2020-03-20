import abc


class Translator(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def translate(self, fields):
        return fields
