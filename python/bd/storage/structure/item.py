import sys
import re
import logging

import yaml
from six import reraise

from ..utils import putils
from ..errors import *
from ..enums import ItemType

log = logging.getLogger(__name__)


class BaseSchemaItem(object):

    _cache = {}

    @classmethod
    def create(cls, schema_id, path):
        cached_items = cls._cache.get(schema_id)
        if cached_items is None:
            cached_items = {}
            cls._cache[schema_id] = cached_items

        schema_item = cached_items.get(path)
        if schema_item is None:
            schema_item = cls(schema_id, path)
            cached_items[path] = schema_item
        return schema_item

    @classmethod
    def clear(cls, schema_id=None):
        if schema_id:
            cached_items = cls._cache.get(schema_id)
            if cached_items:
                cached_items.clear()
        else:
            cls._cache.clear()

    def __init__(self, schema_id, path):
        self._schema_id = schema_id
        self._path = path

        self._children = []

        self._cached_template = None
        self._cached_config = None

        self._parent = self._cache[schema_id].get(
            putils.dirname(self._path)
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

            if putils.exists(cfg_path):
                try:
                    with open(cfg_path, 'r') as f:
                        self._cached_config = yaml.safe_load(f)
                except:
                    reraise(
                        SchemaConfigError,
                        SchemaConfigError('Failed to parse schema config file: {}. {}'.format(
                            cfg_path, sys.exc_info()[1])
                        ),
                        sys.exc_info()[2]
                    )

        if not self._cached_config:
            return default

        return self._cached_config.get(key, default)

    def _get_basename(self):
        basename = putils.basename(self._path)

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
            self._cached_template = putils.join(parent_template, basename)

        return self._cached_template

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.template)

    def __repr__(self):
        return str(self)


class SchemaDir(BaseSchemaItem):
    pass


class SchemaAnchor(BaseSchemaItem):

    def __init__(self, schema_id, path):
        super(SchemaAnchor, self).__init__(schema_id, path)
        self.tags = self.get_config('tags')
        self.type = self.get_config('type', ItemType.FILE)

    def _get_basename(self):
        return self.get_config('template', '')

