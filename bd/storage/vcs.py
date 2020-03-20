import sys
import logging

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class FileSystemVCS(object):

    def __init__(self, schema, accessor):
        self._schema = schema
        self._accessor = accessor

    def iter_versions(self, tags, fields):
        versioned_schema_item = self._get_versioned_schema_item(tags)

        parent_schema_item = versioned_schema_item.parent
        common_path = self._schema.formatter().format(parent_schema_item.template, **fields)

        versioned_names = self._accessor.list(common_path, relative=True, recursive=False)

        if versioned_names:

            _fields = fields.copy()

            for name in sorted(versioned_names, reverse=True):

                parsed_fields = self._schema.formatter().parse(name, versioned_schema_item.basename)
                if not parsed_fields or 'version' not in parsed_fields:
                    continue

                version = parsed_fields['version']

                _fields['version'] = version

                formatted_result = self._schema.formatter().format(
                    versioned_schema_item.basename,
                    **_fields
                )

                if formatted_result != name:
                    continue

                yield version

    def _get_versioned_schema_item(self, tags):
        schema_anchor_item = self._schema.get_anchor_item(tags)

        versioned_schema_item = None

        parent_schema_item = schema_anchor_item

        version_format = '{version}'

        while parent_schema_item is not None:

            basename = parent_schema_item.basename
            if version_format in basename:
                versioned_schema_item = parent_schema_item

            parent_schema_item = parent_schema_item.parent

        if versioned_schema_item is None:
            raise Exception('The item is not supposed to be versioned!')

        return versioned_schema_item

