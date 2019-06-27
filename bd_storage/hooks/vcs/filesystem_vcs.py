import sys
import logging

this = sys.modules[__name__]
this._log = logging.getLogger(__name__.replace('bd_storage', 'bd'))


class FilesystemVersionControl(object):

    def is_centralized(self):
        return False

    def get_incremented_version(self, labels, fields, schema, accessor):
        latest_version = self.get_latest_version(labels, fields, schema, accessor) or 0
        return latest_version + 1

    def get_latest_version(self, labels, fields, schema, accessor):
        schema_anchor_item = schema.get_anchor_item(labels)

        versioned_schema_item = None

        parent_schema_item = schema_anchor_item
        while parent_schema_item is not None:

            basename = parent_schema_item.basename
            if '{version}' in basename:
                versioned_schema_item = parent_schema_item

            parent_schema_item = parent_schema_item.parent

        if versioned_schema_item is None:
            raise Exception('The item is not supposed to be versioned!')

        parent_schema_item = versioned_schema_item.parent
        common_path = schema.formatter().format(parent_schema_item.template, **fields)

        versioned_names = accessor.list(common_path, relative=True, recursive=False)
        if not versioned_names:
            return

        _fields = fields.copy()

        latest_version = None
        for name in versioned_names:

            parsed_fields = schema.formatter().parse(name, versioned_schema_item.basename)
            if not parsed_fields or 'version' not in parsed_fields:
                continue

            version = parsed_fields['version']
            if version <= latest_version:
                continue

            _fields['version'] = version

            formatted_result = schema.formatter().format(
                versioned_schema_item.basename,
                **_fields
            )

            if formatted_result != name:
                continue

            latest_version = version

        return latest_version


def register(registry):
    registry.add_hook('storage.vcs.init.filesystem-vcs', FilesystemVersionControl)
