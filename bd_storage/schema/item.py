import os
import sys

import metayaml

from . import constants as c
from ..logger import get_logger

this = sys.modules[__name__]
this._log = get_logger(__name__)


class SchemaItem(object):

    _cached_items = {}

    def __init__(self, path):
        self._path = path

        self._children = []

        self._template = None
        self._config = None

        self._triggers = None

        if self and self.parent is not None:
            self.parent.children.append(self)

    @classmethod
    def create(cls, path):
        schema_item = cls._cached_items.get(path)
        if schema_item is None:
            schema_item = cls(path)
            cls._cached_items[path] = schema_item
        return schema_item

    @property
    def path(self):
        return self._path

    @property
    def parent(self):
        return self._cached_items.get(self._path.parent)

    @property
    def children(self):
        return self._children

    @property
    def config(self):
        if self._config is None:

            self._config = {}

            cfg_path = self._path
            if self._path.suffix != '.yml':
                cfg_path = self._path.with_suffix('.yml')

            if cfg_path.exists():
                self._config = metayaml.read(
                    str(cfg_path.resolve()),
                    defaults={'env': os.getenv}
                )

        return self._config

    @property
    def triggers(self):
        if self._triggers:
            return self._triggers

        self._triggers = self.config.get('triggers', [])

        if self.parent is not None:

            self._triggers.extend([
                trigger
                for trigger in self.parent.triggers
                if trigger.get('propagate', False)
            ])

        return self._triggers

    def is_triggered(self, labels, fields):
        if not self.triggers:
            return False

        for trigger in self.triggers:

            expr = trigger.get('expression')
            if not expr:
                continue

            try:
                if eval(expr, globals(), locals()):
                    return True
            except:
                pass

        return False

    @property
    def basename(self):
        basename = self._path.name
        if self.config:
            basename = self.config.get('format', basename)
        return basename

    @property
    def template(self):
        if self._template is not None:
            return self._template

        basename = self.basename
        parent_item = self.parent

        # if it's the root of the schema
        if parent_item is None:
            self._template = basename
        else:
            parent_template = parent_item.template
            self._template = '/'.join([parent_template, basename])

        return self._template

    @classmethod
    def items(cls):
        return cls._cached_items.values()

    @classmethod
    def clear(cls):
        cls._cached_items.clear()

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.template)

    def __repr__(self):
        return str(self)

    def __cmp__(self, other):
        self_keys = set(c.template_key_regex.findall(self.template))
        other_keys = set(c.template_key_regex.findall(other.template))
        return (lambda a, b: (a > b)-(a < b))(len(self_keys), len(other_keys))


class SchemaDir(SchemaItem):
    pass


class SchemaFile(SchemaItem):
    pass


class SchemaAnchor(SchemaItem):

    @property
    def basename(self):
        return self.config.get('format', '')
