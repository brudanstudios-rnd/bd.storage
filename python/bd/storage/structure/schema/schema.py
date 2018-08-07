import os
import logging

import pathlib2

import bd.config as config

from . import constants as c

from .item import \
    SchemaItem, \
    SchemaDir, \
    SchemaAnchor, \
    SchemaFile


LOGGER = logging.getLogger(__name__)


class Schema(object):

    def __init__(self, schema_dir, accessor):
        self._schema_dir = schema_dir
        self._anchor_items = {}
        self._accessor = accessor
        self._load()

    @classmethod
    def new(cls, schema_name, accessor):
        proj_config_dir = pathlib2.Path(config.get_value("proj_config_dir"))

        schema_dir = proj_config_dir / "schemas" / schema_name

        if not schema_dir.exists():
            LOGGER.error("Schema directory "
                         " '{}' doesn't exist".format(schema_dir))
            return

        if accessor is None:
            LOGGER.error("Unspecified Accessor object")
            return

        return cls(schema_dir, accessor)

    def _load(self):
        str_schema_dir = str(self._schema_dir.resolve())

        for current_dir, nested_dirs, filenames in os.walk(str_schema_dir):

            current_dir = pathlib2.Path(current_dir)
            if current_dir == self._schema_dir:
                continue

            SchemaDir.new(current_dir)

            for filename in filenames:

                match = c.TMPL_FILENAME_REGEX.match(filename)

                if not match:
                    if not filename.endswith(".yml"):
                        SchemaFile.new(current_dir / filename)
                    continue

                labels = match.group(1).split(':')
                self._anchor_items[frozenset(labels)] = SchemaAnchor.new(current_dir / filename)

    def _get_anchor_item(self, labels):
        return self._anchor_items.get(frozenset(labels))

    def get_anchor_path(self, labels, context):
        schema_item = self._get_anchor_item(labels)
        if schema_item:
            return schema_item.resolve(context)

    def _build_item(self, item, context):

        target_path = item.resolve(context)

        if not target_path:
            return False

        if self._accessor.exists(target_path):
            return True

        parent_item = item \
            if isinstance(item, SchemaDir) \
            else item.parent

        parent_items = []
        while parent_item is not None:
            parent_items.append(parent_item)
            parent_item = parent_item.parent

        for parent_item in reversed(parent_items):

            target_dir_path = parent_item.resolve(context)

            if not target_dir_path:
                return False

            if not self._accessor.exists(target_dir_path):
                try:
                    self._accessor.make_dir(target_dir_path)
                except Exception as e:
                    return False

        if isinstance(item, SchemaFile):
            try:

                with item.path.open("rb") as in_file:
                    with self._accessor.open(target_path, "wb") as out_file:
                        out_file.write(in_file.read())
            except Exception as e:
                return False

        return True

    def _build_triggered_items(self, lables, context):
        for schema_item in SchemaItem.items():
            if schema_item.is_triggered(lables):
                self._build_item(schema_item, context)

    def create_dir_structure(self, labels, context):
        schema_item = self._get_anchor_item(labels)
        if schema_item is None or self._build_item(schema_item, context):
            self._build_triggered_items(labels, context)

