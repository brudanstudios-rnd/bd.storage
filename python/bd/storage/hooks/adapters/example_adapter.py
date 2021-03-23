import logging

from bd.storage.adapter import BaseAdapter

log = logging.getLogger(__name__)


class ExampleAdapter(BaseAdapter):

    def __init__(self):
        super(ExampleAdapter, self).__init__()

    def to_current(self, fields):
        return fields

    def from_current(self, fields):
        return fields


def register(registry):
    # registry.add_hook('example-adapter', ExampleAdapter)
    pass
