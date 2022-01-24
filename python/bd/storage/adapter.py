class BaseAdapter(object):

    def output(self, identifier):
        raise NotImplementedError()

    def input(self, identifier):
        raise NotImplementedError()

    def update_current(self, identifier):
        return identifier
