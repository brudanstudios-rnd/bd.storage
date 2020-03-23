import os
import sys
import re
import logging
import posixpath as pp

from .._vendor import metayaml

this = sys.modules[__name__]
this._log = logging.getLogger(__name__)


class SchemaItem(object):

    _cached_items = {}

    @classmethod
    def create(cls, path):
        schema_item = cls._cached_items.get(path)
        if schema_item is None:
            schema_item = cls(path)
            cls._cached_items[path] = schema_item
        return schema_item

    @classmethod
    def clear(cls):
        cls._cached_items.clear()

    def __init__(self, path):
        self._path = path

        self._children = []

        self._cached_template = None
        self._cached_config = None

        self._parent = self._cached_items.get(
            os.path.dirname(self._path)
        )

        if self and self._parent is not None:
            self._parent.add_child(self)

    def add_child(self, item):
        self._children.append(item)

    def get_config(self, key, default=None):
        if self._cached_config is None:

            self._cached_config = {}

            cfg_path = self._path
            if not self._path.endswith('.yml'):
                cfg_path = self._path + '.yml'

            if os.path.exists(cfg_path):
                self._cached_config = metayaml.read(
                    cfg_path,
                    defaults={'env': os.getenv}
                )

        if not self._cached_config:
            return default

        return self._cached_config.get(key, default)

    def _get_basename(self):
        basename = os.path.basename(self._path)

        config_template = self.get_config('template')
        if config_template:
            basename = re.subn(r'[\:\!]\w+}', '}', config_template)[0]

        return basename

    @property
    def template(self):
        if self._cached_template is not None:
            return self._cached_template

        basename = self._get_basename()
        parent_item = self._parent

        # if it's the root of the schema
        if parent_item is None:
            self._cached_template = basename
        else:
            parent_template = parent_item.template
            self._cached_template = pp.join(parent_template, basename)

        return self._cached_template

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.template)

    def __repr__(self):
        return str(self)


class SchemaDir(SchemaItem):
    pass


class SchemaAnchor(SchemaItem):

    def _get_basename(self):
        return self.get_config('template', '')
