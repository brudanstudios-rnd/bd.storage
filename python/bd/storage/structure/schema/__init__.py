import logging

from ..base import Structure
from .schema import Schema

LOGGER = logging.getLogger(__name__)


class SchemaStructure(Structure):

    name = "schema-structure"

    def __init__(self, accessor, schema_name):
        self._schema = Schema.new(schema_name, accessor=accessor)

    @classmethod
    def new(cls, accessor, **kwargs):
        schema_name = kwargs.get("schema")

        if not schema_name:
            LOGGER.error("Unspecified 'schema' argument for 'schema-structure'")
            return

        return cls(accessor, schema_name)

    def get_uid(self, labels, context):
        return self._schema.get_anchor_path(labels, context)

    def make_dirs(self, labels, context):
        return self._schema.create_dir_structure(labels, context)