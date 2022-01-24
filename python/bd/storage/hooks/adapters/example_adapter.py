import logging

from bd.storage.adapter import BaseAdapter

log = logging.getLogger(__name__)


class ExampleAdapter(BaseAdapter):

    def __init__(self):
        super(ExampleAdapter, self).__init__()

    def output(self, identifier):
        return identifier

    def input(self, identifier):
        return identifier

    def update_current(self, identifier):
        return identifier


def register(registry):
    # registry.add_hook('example-adapter', ExampleAdapter)
    pass
