class BaseAdapter(object):

    def to_current(self, fields):
        raise NotImplementedError()

    def from_current(self, fields):
        raise NotImplementedError()
