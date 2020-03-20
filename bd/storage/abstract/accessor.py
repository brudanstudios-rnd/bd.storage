import abc


class Accessor(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, root):
        self._root = root
        if self._root:
            self._root = root.replace('\\', '/') + '/'
            
    def root(self):
        return self._root

    def resolve(self, uid):
        return uid

    def convert_filename_to_uid(self, filename):
        if filename.startswith(self._root):
            return filename[len(self._root):]
            
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
    def exists(self, uid):
        pass

    @abc.abstractmethod
    def list(self, uid, relative=False, recursive=True):
        pass

    @abc.abstractmethod
    def rm(self, uid):
        pass

    @abc.abstractmethod
    def get_filename(self, uid):
        pass