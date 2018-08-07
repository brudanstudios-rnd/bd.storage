import os
import logging
from fnmatch import fnmatch
from collections import OrderedDict
import tempfile

from .. import config
from .. import hooks
from ..exceptions import *

from .accessor.filesystem import FileSystemAccessor
from .structure.schema import SchemaStructure
from .structure.proxy import ProxyStructure


LOGGER = logging.getLogger(__name__)


class StorageRegistry(object):

    def __init__(self):
        self._structures = {}
        self._accessors = {}

    def add_structure(self, name, structure):
        self._structures[name] = structure

    def add_accessor(self, name, accessor):
        self._accessors[name] = accessor

    def get_structure(self, name):
        return self._structures.get(name)

    def get_accessor(self, name):
        return self._accessors.get(name)


class Storage(object):

    def __init__(self, name, accessor, structure, mask="*", type="local"):
        self._name = name
        self._accessor = accessor
        self._structure = structure
        self._label_patterns = map(lambda x: x.strip(), mask.split())
        self._type = type

    def get_name(self):
        return self._name

    def get_accessor(self):
        return self._accessor

    def get_structure(self):
        return self._structure

    def get_type(self):
        return self._type

    def get_item(self, labels, context):
        if not self.match(labels):
            return

        uid = self._structure.get_uid(labels, context)
        if not uid:
            return

        if not self._accessor.exists(uid):
            return

        return StorageItem(labels, context, uid, self)

    def new_item(self, labels, context):
        if not self.match(labels):
            return

        uid = self._structure.get_uid(labels, context)
        if not uid:
            return

        return StorageItem(labels, context, uid, self)

    def put_item(self, source_item):
        if source_item.get_storage() is self:
            return source_item

        labels, context = source_item.get_labels(), source_item.get_context()

        if not self.match(source_item.get_labels()):
            return

        uid = self._structure.get_uid(labels, context)
        if not uid:
            return

        target_item = StorageItem(labels, context, uid, self)

        if self._accessor.exists(uid):
            return target_item

        self._structure.make_dirs(labels, context)

        with source_item.open("rb") as in_f:
            with target_item.open("wb") as out_f:
                out_f.write(in_f.read())

        return target_item

    def match(self, labels):
        for label in labels:

            for pattern in self._label_patterns:

                if pattern == "*":
                    continue

                if pattern.startswith("^"):
                    pattern = pattern.lstrip('^')
                    match = not fnmatch(label, pattern)
                else:
                    match = fnmatch(label, pattern)

                if not match:
                    return False

        return True

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Storage(name={}, accessor={}, structure={})".format(
            self._name,
            self._accessor.name,
            self._structure.name
        )


class StorageItem(object):

    def __init__(self, labels, context, uid, storage):
        self._labels = labels
        self._context = context
        self._uid = uid
        self._storage = storage
        self._filesystem_path = None

    def get_labels(self):
        return self._labels

    def get_context(self):
        return self._context

    def get_uid(self):
        return self._uid

    def get_storage(self):
        return self._storage

    def get_filesystem_path(self):
        if self._filesystem_path:
           return self._filesystem_path

        path = self._storage.get_accessor().get_filesystem_path(self._uid)

        if not path:
            raise Exception("Unable to retrieve filesystem path for item from remote storage")

        self._filesystem_path = path

        return self._filesystem_path

    def open(self, mode="rb"):
        return self._storage.get_accessor().open(self._uid, mode)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "StorageItem(labels={}, context={}, uid={}, storage={})".format(
            repr(self._labels),
            repr(self._context),
            self._uid,
            self._storage.get_name()
        )


class StoragePool(object):

    def __init__(self):
        self._tmp_storage = None
        self._storages = None

        self.get_storages()

    def get_storages(self):
        if not self._storages:

            self._storages = OrderedDict()

            registry = StorageRegistry()

            registry.add_accessor(FileSystemAccessor.name, FileSystemAccessor)
            registry.add_structure(ProxyStructure.name, ProxyStructure)
            registry.add_structure(SchemaStructure.name, SchemaStructure)

            try:
                hooks.load_hooks()
            except Error as e:
                LOGGER.warning(str(e))
            else:
                hooks.execute("storage.register.structure", registry).all()
                hooks.execute("storage.register.accessor", registry).all()

            tmp_accessor = FileSystemAccessor.new(root=tempfile.gettempdir())
            tmp_structure = ProxyStructure.new(tmp_accessor)
            self._tmp_storage = Storage("_tmp_storage",
                                        tmp_accessor,
                                        tmp_structure)

            cfg_storages = config.get_value("storage")

            for name, cfg_storage in cfg_storages.iteritems():

                accessor_cls = registry.get_accessor(cfg_storage["accessor"]["name"])
                if not accessor_cls:
                    continue

                accessor = accessor_cls.new(**cfg_storage["accessor"].get("kwargs", {}))

                structure_cls = registry.get_structure(cfg_storage["structure"]["name"])
                if not structure_cls:
                    continue

                structure = structure_cls.new(accessor, **cfg_storage["structure"].get("kwargs", {}))

                self._storages[name] = Storage(name,
                                               accessor,
                                               structure,
                                               cfg_storage["mask"],
                                               cfg_storage["type"])

        return self._storages.values()

    def get_matching_storages(self, labels):
        for storage in self.get_storages():

            if not storage.match(labels):
                continue

            yield storage

    def get_item(self, labels, context, replicate=False):
        for storage in self.get_matching_storages(labels):

            item = storage.get_item(labels, context)
            if not item:
                continue

            if not replicate:
                return item

            return self.put_item(item)

    def put_item(self, source_item):
        target_item = None

        for storage in reversed(list(self.get_matching_storages(source_item.get_labels()))):
            target_item = storage.put_item(source_item) or target_item

        return target_item

    def new_item(self, labels, context):
        return self._tmp_storage.new_item(labels, context)