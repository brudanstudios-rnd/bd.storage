import os
from bd.logger import get_logger

LOGGER = get_logger()


class Environment(object):

    def __init__(self):
        self._modified = set()

    def getenv(self, name, default=None):
        return os.environ.get(name, default)

    def putenv(self, name, value):
        os.environ[name] = str(value)
        self._modified.add(name)

    def prepend(self, name, value):
        old_value = os.environ.get(name)
        new_value = str(value)

        if not old_value:
            os.environ[name] = new_value
        else:
            old_value_parts = old_value.strip(os.pathsep).split(os.pathsep)
            if new_value not in old_value_parts:
                os.environ[name] = os.pathsep.join([new_value] + old_value_parts)

        self._modified.add(name)

    def append(self, name, value):
        old_value = os.environ.get(name)
        new_value = str(value)

        if not old_value:
            os.environ[name] = new_value
        else:
            old_value_parts = old_value.strip(os.pathsep).split(os.pathsep)
            if new_value not in old_value_parts:
                os.environ[name] = os.pathsep.join(old_value_parts + [new_value])

        self._modified.add(name)

    def __getitem__(self, name):
        return self.getenv(name)

    def __setitem__(self, name, value):
        self.putenv(name, value)
        
    def __contains__(self, name):
        return name in os.environ
    
    def __iter__(self):
        return os.environ.iteritems()

    def to_dict(self, modified=True):
        return {name: value
                for name, value in os.environ.iteritems()
                if name.startswith("BD_") or not modified or name in self._modified}
    
    
ENV = Environment()
