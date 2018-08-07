import logging
import uuid

from .base import Structure

LOGGER = logging.getLogger(__name__)


class ProxyStructure(Structure):

    name = "proxy-structure"

    def __init__(self, accessor):
        self._accessor = accessor

    @classmethod
    def new(cls, accessor, **kwargs):
        return cls(accessor)

    def get_uid(self, labels, context):
        return str(uuid.uuid4())

    def make_dirs(self, labels, context):
        pass