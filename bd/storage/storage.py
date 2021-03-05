__all__ = ['StoragePool', 'MetaItem']

import os
import re
import sys
import logging
import getpass
import json
import datetime

import bd.hooks as bd_hooks

from ._vendor.six import reraise

from .accessor import FileSystemAccessor
from .formatter import FieldFormatter
from .schema import Schema
from .validation import validate_pool_config
from . import utils
from .utils import putils
from .errors import *
from .enums import ItemType

log = logging.getLogger(__name__)


def _json_encoder(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.strftime("%m/%d/%Y %H:%M:%S")
    raise TypeError("Type {} not serializable".format(type(obj)))


class Storage(object):

    def __init__(self, name, accessor, schema, formatter, adapter=None, tag_mask=None):
        self._name = name
        self._accessor = accessor
        self._schema = schema
        self._formatter = formatter
        self._adapter = adapter
        self._tag_mask = utils.parse_mask(tag_mask) if tag_mask else None

    @classmethod
    def create_storage(cls, storage_name, storage_config):
        """Create storage object from provided configuration.

        Args:
            storage_name (str): storage name.
            storage_config (dict): storage configuration.

        Returns:
            Storage: fully setup storage object.

        """
        accessor = cls._create_accessor(storage_config["accessor"])
        formatter = cls._create_formatter(storage_config["fields"])
        schema = cls._create_schema(storage_config["schema"])
        adapter = cls._create_adapter(storage_config.get('adapter'))

        return Storage(
            storage_name,
            accessor,
            schema,
            formatter,
            adapter,
            storage_config.get("tag_mask")
        )

    @classmethod
    def _create_accessor(cls, accessor_config):
        accessor_name = accessor_config.get("name")
        accessor_kwargs = accessor_config.get("kwargs", {})

        if not accessor_name or accessor_name == 'fs':
            return FileSystemAccessor(**accessor_kwargs)

        try:
            return bd_hooks.execute(accessor_name, **accessor_kwargs).one()
        except bd_hooks.HookError:
            reraise(
                AccessorCreationError,
                'Failed to initialize accessor "{}"'.format(accessor_name),
                sys.exc_info()[2]
            )

    @classmethod
    def _create_formatter(cls, fields_config):
        return FieldFormatter(fields_config)

    @classmethod
    def _create_schema(cls, schema_name):
        """Create storage schema from provided configuration.

        Args:
            schema_name (str): storage schema name.

        Returns:
            Schema: storage schema object.

        """

        if 'BD_STORAGE_SCHEMA_PATH' not in os.environ:
            raise SchemaError(
                'No schema search path defined. '
                'Please ensure "BD_STORAGE_SCHEMA_PATH" environment variable is defined.'
            )

        schema_search_paths = os.environ['BD_STORAGE_SCHEMA_PATH'].split(os.pathsep)

        schema_dir = None
        for search_path in schema_search_paths:
            dirname = os.path.join(search_path, schema_name)
            if os.path.exists(dirname):
                schema_dir = dirname
                break

        if not schema_dir:
            raise SchemaError(
                'Unable to find schema with name "{}"'.format(schema_name)
            )

        return Schema(putils.normpath(schema_dir))

    @classmethod
    def _create_adapter(cls, adapter_config):
        if not adapter_config:
            return

        adapter_name = adapter_config.get("name")
        adapter_kwargs = adapter_config.get("kwargs", {})

        if adapter_name:
            try:
                return bd_hooks.execute(adapter_name, **adapter_kwargs).one()
            except bd_hooks.HookError:
                reraise(
                    AdapterCreationError,
                    'Failed to initialize adapter "{}"'.format(adapter_name),
                    sys.exc_info()[2]
                )

    @property
    def name(self):
        return self._name

    @property
    def accessor(self):
        return self._accessor

    @property
    def adapter(self):
        return self._adapter

    @property
    def formatter(self):
        return self._formatter

    def get_item(self, tags):
        if not self.is_matching(tags):
            return

        schema_item = self._schema.get_item(tags)
        if not schema_item:
            return

        return MetaItem(tags, schema_item, self)

    def get_data_from_uid(self, uid):
        max_num_fields = -1
        result_tags = result_fields = None
        for tags, item in self._schema.get_items().items():

            fields = self._formatter.parse(uid, item.template)
            if not fields:
                continue

            num_fields = len(fields)

            if num_fields > max_num_fields:
                result_tags, result_fields = tags, fields
                max_num_fields = num_fields

        if not (result_tags and result_fields):
            return None, None

        if not self.is_matching(result_tags):
            return None, None

        if self._adapter:
            self._adapter.from_current(result_fields)

        return result_tags, result_fields

    def is_matching(self, tags):
        if not self._tag_mask:
            return True

        return utils.match_tags(self._tag_mask, tags)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Storage(name='{}')".format(self._name)


class MetadataEdit(object):

    def __init__(self):
        self._metadata = None

    def get_metadata(self, key):
        if self._metadata:
            return self._metadata.get(key)

    def set_metadata(self, key, value):
        if not self._metadata:
            self._metadata = {key: value}
        else:
            self._metadata[key] = value

    def get_metadata_dict(self):
        return self._metadata

    def set_metadata_dict(self, metadata):
        if metadata is None:
            self._metadata = None
        else:
            self._metadata = metadata.copy()

    def copy_metadata(self, item):
        metadata = item._metadata
        if metadata is None:
            self._metadata = None
        else:
            self._metadata = metadata.copy()


class TagsMixin(object):

    def __init__(self, tags):
        if isinstance(tags, TagsMixin):
            tags = tags.tags
        elif tags and not isinstance(tags, (tuple, list, set, frozenset)):
            raise InputError(
                'Argument "tags" has invalid type "{}"'.format(type(tags).__name__)
            )
        self._tags = list(tags)

    @property
    def tags(self):
        return self._tags

    @property
    def common_tags(self):
        return [tag for tag in self._tags if not tag.startswith('_')]

    @property
    def extra_tags(self):
        return [tag for tag in self._tags if tag.startswith('_')]

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return repr(self._tags)


class TagsEdit(TagsMixin):

    def remove_extra_tags(self):
        self._tags = list(filter(lambda tag: not tag.startswith('_'), self._tags))

    def add_tag(self, tag):
        if tag not in self._tags:
            self._tags.append(tag)
        return self

    def add_tags(self, *tags):
        for tag in tags:
            self.add_tag(tag)
        return self

    def remove_tag(self, tag):
        try:
            self._tags.remove(tag)
        except ValueError:
            pass
        return self

    def remove_tags(self, *tags):
        for tag in tags:
            self.remove_tag(tag)
        return self

    def replace_tag(self, old_tag, new_tag):
        return self.remove_tag(old_tag).add_tag(new_tag)

    def replace_tags(self, **kwargs):
        for old_tag, new_tag in kwargs.items():
            self.replace_tag(old_tag, new_tag)
        return self


class FieldsMixin(object):

    def __init__(self, fields=None):
        if fields:
            if isinstance(fields, FieldsMixin):
                fields = fields.fields
            elif not isinstance(fields, dict):
                raise InputError(
                    'Argument "fields" has invalid type "{}"'.format(type(fields).__name__)
                )
        self._fields = fields.copy() if fields else {}

    @property
    def fields(self):
        return self._fields

    @property
    def common_fields(self):
        return {name: value for name, value in self._fields.items() if not name.startswith('_')}

    @property
    def extra_fields(self):
        return {name: value for name, value in self._fields.items() if name.startswith('_')}

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return repr(self._fields)


class FieldsEdit(FieldsMixin):

    def remove_extra_fields(self):
        self._fields = dict(filter(lambda x: not x[0].startswith('_'), self._fields.items()))
        return self

    def set_field(self, name, value):
        self._fields[name] = value
        return self

    def update_fields(self, fields):
        self._fields.update(fields)
        return self

    def pop_field(self, name):
        return self._fields.pop(name, None)

    def pop_fields(self, names):
        popped_fields = {}
        for name in names:
            value = self._fields.pop(name, None)
            if value:
                popped_fields[name] = value
        return popped_fields


class ChainItemMixin(object):

    def __init__(self):
        self.next_item = None
        self.prev_item = None

    def iter_chain(self, to_next=True):
        item = self
        while item:
            yield item
            item = item.next_item

    def set_next_item(self, item):
        self.next_item = item
        item.prev_item = self

    def set_prev_item(self, item):
        self.prev_item = item
        item.next_item = self

    def get_upstream_item(self):
        upstream_item = self
        while upstream_item.next_item:
            upstream_item = upstream_item.next_item
        return upstream_item

    def get_downstream_item(self):
        downstream_item = self
        while downstream_item.prev_item:
            downstream_item = downstream_item.prev_item
        return downstream_item


class MetaItem(TagsMixin, ChainItemMixin):

    def __init__(self, tags, schema_item, storage):
        TagsMixin.__init__(self, tags)
        ChainItemMixin.__init__(self)
        self._type = schema_item.type
        self._template = schema_item.template
        self._storage = storage
        self._adapter = storage.adapter
        self._accessor = storage.accessor
        self._formatter = storage.formatter

    @property
    def type(self):
        return self._type

    @property
    def template(self):
        return self._template

    @property
    def storage(self):
        return self._storage

    @property
    def adapter(self):
        return self._adapter

    @property
    def accessor(self):
        return self._storage.accessor

    @property
    def formatter(self):
        return self._formatter

    def get_storage_item(self, fields):
        if isinstance(fields, FieldsEdit):
            fields = fields.fields

        target_storage_item = None
        prev_storage_item = None

        if self._type == ItemType.sequence:
            if ItemSequenceFn.PRIMARY_FIELD not in fields:
                fields[ItemSequenceFn.PRIMARY_FIELD] = 1

        elif self._type == ItemType.collection:
            if ItemCollectionFn.PRIMARY_FIELD not in fields:
                fields[ItemCollectionFn.PRIMARY_FIELD] = ''

        downstream_meta_item = self.get_downstream_item()

        for meta_item in downstream_meta_item.iter_chain():

            curr_fields = fields
            if meta_item._adapter:
                curr_fields = meta_item._adapter.to_current(curr_fields.copy())

            uid = meta_item._formatter.format(meta_item.template, **curr_fields)
            if not uid:
                continue

            curr_storage_item = StorageItem(
                uid,
                curr_fields,
                meta_item
            )

            if meta_item is self:
                target_storage_item = curr_storage_item

            if prev_storage_item:
                curr_storage_item.set_prev_item(prev_storage_item)

            prev_storage_item = curr_storage_item

        return target_storage_item

    def build_uid(self, fields):
        if isinstance(fields, FieldsEdit):
            fields = fields.fields

        if self._adapter:
            fields = self._adapter.to_current(fields.copy())

        return self._formatter.format(self._template, **fields)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "MetaItem(tags={}, template='{}', storage='{}')"
        ).format(self._tags, self._template, self.storage.name)


class UTBase(FieldsEdit):

    PRIMARY_FIELD = None

    def __init__(self, item, fields=None):
        if isinstance(item, StorageItem):
            self._meta_item = item.meta_item
            if not fields:
                fields = item.fields
        else:
            self._meta_item = item
            if not fields:
                raise InputError(
                    'Argument "fields" is mandatory when '
                    'using MetaItem as the first argument.'
                )

        super(UTBase, self).__init__(fields)

    @property
    def meta_item(self):
        return self._meta_item

    def get_storage_item(self, primary_field_value=None):
        fields = self.fields
        if primary_field_value is not None:
            fields = FieldsEdit(fields)
            fields.set_field(self.PRIMARY_FIELD, primary_field_value)
        return self._meta_item.get_storage_item(fields)

    def pull(self, with_metadata=False):
        for member_item in self.get_items(from_upstream=True):
            member_item.pull(with_metadata)

    def push(self, with_metadata=False):
        for member_item in self.get_items(from_upstream=False):
            member_item.push(with_metadata)

    def get_items(self, from_upstream=True):
        pass


class ItemRevisionFn(UTBase):

    PRIMARY_FIELD = '_version_'

    def get_items(self, from_upstream=False):
        fields = FieldsEdit(self.fields)
        fields.set_field(self.PRIMARY_FIELD, 96969696969696)      # adding just to detect it later

        revision_numbers = set()

        meta_item = self._meta_item.get_upstream_item() if from_upstream else self._meta_item

        uid = meta_item.build_uid(fields)
        if not uid:
            return []

        uid_dirname, uid_basename = putils.split(uid)
        uid_basename_pattern = re.escape(uid_basename).replace('96969696969696', '(\d+)')

        try:
            nested_uids = meta_item.accessor.list(uid_dirname, recursive=False)
        except:
            reraise(AccessorError, *sys.exc_info()[1:])

        for uid_basename in sorted(nested_uids):
            match = re.match(uid_basename_pattern, uid_basename)
            if match:
                revision_numbers.add(int(match.group(1)))

        revision_numbers = list(revision_numbers)
        revision_numbers.sort()

        member_items = []

        for revision_number in revision_numbers:

            fields.set_field(self.PRIMARY_FIELD, revision_number)

            member_item = meta_item.get_storage_item(fields)
            if member_item:
                member_items.append(member_item)

        return member_items


class ItemSequenceFn(UTBase):

    PRIMARY_FIELD = '_index_'

    def get_items(self, from_upstream=True):
        fields = FieldsEdit(self.fields)
        fields.set_field(self.PRIMARY_FIELD, 96969696969696)      # adding just to detect it later

        indexes = set()

        meta_item = self._meta_item.get_upstream_item() if from_upstream else self._meta_item
        uid = meta_item.build_uid(fields)
        if not uid:
            return []

        uid_dirname, uid_basename = putils.split(uid)
        uid_basename_pattern = re.escape(uid_basename).replace('96969696969696', '(\d+)')

        try:
            nested_uids = meta_item.accessor.list(uid_dirname, recursive=False)
        except:
            reraise(AccessorError, *sys.exc_info()[1:])

        for uid_basename in sorted(nested_uids):
            match = re.match(uid_basename_pattern, uid_basename)
            if match:
                indexes.add(int(match.group(1)))

        indexes = list(indexes)
        indexes.sort()

        member_items = []
        for index in indexes:

            fields.set_field(self.PRIMARY_FIELD, index)

            member_item = meta_item.get_storage_item(fields)
            if member_item:
                member_items.append(member_item)

        return member_items


class ItemCollectionFn(UTBase):

    PRIMARY_FIELD = '_suffix_'

    def get_items(self, from_upstream=True):
        fields = FieldsEdit(self.fields)
        fields.set_field(self.PRIMARY_FIELD, '')      # adding just to detect it later

        meta_item = self._meta_item.get_upstream_item() if from_upstream else self._meta_item

        uid = meta_item.build_uid(fields)
        if not uid:
            return []

        try:
            relative_suffix_uids = meta_item.accessor.list(uid)
        except:
            reraise(AccessorError, *sys.exc_info()[1:])

        suffixes = set()
        for relative_suffix_uid in relative_suffix_uids:
            suffixes.add(relative_suffix_uid)

        member_items = []
        for suffix in suffixes:

            fields.set_field(self.PRIMARY_FIELD, suffix)

            member_item = meta_item.get_storage_item(fields)
            if member_item:
                member_items.append(member_item)

        return member_items


class StorageItem(TagsMixin, FieldsMixin, MetadataEdit, ChainItemMixin):

    def __init__(self, uid, fields, meta_item):
        TagsMixin.__init__(self, meta_item.tags)
        FieldsMixin.__init__(self, fields)
        MetadataEdit.__init__(self)
        ChainItemMixin.__init__(self)
        self._uid = uid
        self._meta_item = meta_item

    @property
    def uid(self):
        return self._uid

    @property
    def type(self):
        return self._meta_item.type

    @property
    def storage(self):
        return self._meta_item.storage

    @property
    def accessor(self):
        return self._meta_item.accessor

    @property
    def meta_item(self):
        return self._meta_item

    def exists(self, check_upstream=False):
        try:
            exists = False
            if self.accessor.exists(self._uid):
                exists = True
            elif check_upstream:
                if self.next_item:
                    exists = self.next_item.exists(check_upstream)
            return exists
        except:
            reraise(
                AccessorError,
                'Failed to check if item "{}" exists. {}'.format(self, sys.exc_info()[1]),
                sys.exc_info()[2]
            )

    def get_filesystem_path(self):
        return self.accessor.get_filesystem_path(self._uid)

    def read(self, current_item_only=False, upstream=True, with_metadata=False):

        def _read_self():
            try:
                data = self.accessor.read(self._uid)
            except:
                reraise(
                    AccessorError,
                    'Failed to read item "{}". '
                    '{}'.format(self, sys.exc_info()[1]),
                    sys.exc_info()[2]
                )

            if data is not None:
                log.debug('Read data from item "{}"'.format(self))

            if with_metadata:
                # if .txt or .meta file is found parse it
                # and use the data as metadata
                self.set_metadata_dict(self._load_metadata())

            return data

        def _read_next():
            if self.next_item:
                data = self.next_item.read(upstream=upstream, with_metadata=with_metadata)

                if with_metadata:
                    # copy metadata from next item to current
                    self.copy_metadata(self.next_item)

                return data

        if current_item_only:
            return _read_self()

        if upstream:
            data = _read_self()
            if data is None:
                data = _read_next()
            return data
        else:
            data = _read_next()
            if data is None:
                data = _read_self()
            return data

    def _dump_metadata(self):
        aux_data = {
            'date': datetime.datetime.now(),
            'user': getpass.getuser(),
            'tags': self.tags,
            'fields': self.fields
        }

        if self._metadata:
            metadata = utils.remove_extra_fields(self._metadata)
            if metadata:
                aux_data.update(metadata)

        try:
            json_data = json.dumps(aux_data, indent=2, default=_json_encoder)
        except TypeError as e:
            raise MetadataSerializationError(e)

        try:
            self.accessor.write(self._uid + '.meta', json_data)
        except:
            reraise(
                AccessorError,
                'Failed to write metadata for item "{}". '
                '{}'.format(self, sys.exc_info()[1]),
                sys.exc_info()[2]
            )

    def _load_metadata(self):
        data = {}

        metadata_uid = self._uid + '.meta'
        if not self.accessor.exists(metadata_uid):
            metadata_uid = self._uid + '.txt'
            if not self.accessor.exists(metadata_uid):
                return

        content = self.accessor.read(metadata_uid)

        if metadata_uid.endswith('.meta'):
            data = json.loads(content)
            data["date"] = datetime.datetime.strptime(data['date'], "%m/%d/%Y %H:%M:%S")
            data.pop('tags', None)
            data.pop('fields', None)
        else:
            active_section = None
            for line in content.splitlines():
                line = line.strip()

                if not len(line):
                    continue

                try:
                    title, text = line.split(":", 1)
                except ValueError:
                    data[active_section] = '\n'.join([data[active_section], line])
                    continue

                if text:
                    text = text.strip()

                if title == "date":
                    data["date"] = datetime.datetime.strptime(text, "%m/%d/%Y %H:%M:%S")
                    active_section = "date"
                elif title == "user":
                    data["user"] = text
                    active_section = "user"
                elif title == "note":
                    data["comment"] = text
                    active_section = "comment"
                else:
                    data[title] = text
                    active_section = title
        return data

    def write(self, data, current_item_only=False, upstream=True, with_metadata=False):

        def _write_self():

            if self.exists():
                return

            log.debug(
                'Writing to item "{}" ...'.format(self)
            )

            try:
                self.accessor.write(self._uid, data)
            except:
                reraise(
                    AccessorError,
                    'Failed to write to item "{}". '
                    '{}'.format(self, sys.exc_info()[1]),
                    sys.exc_info()[2]
                )

            if with_metadata:
                self._dump_metadata()

            log.debug('Done')

        def _write_next():
            if not self.next_item:
                return

            if with_metadata:
                self.next_item.copy_metadata(self)

            self.next_item.write(data, upstream=upstream, with_metadata=with_metadata)

        if current_item_only:
            return _write_self()

        if upstream:
            _write_self()
            _write_next()
        else:
            _write_next()
            _write_self()

    def pull(self, with_metadata=False):
        downstream_item = self.get_downstream_item()
        if not downstream_item or downstream_item.exists():
            return

        data = self.read(upstream=False, with_metadata=with_metadata)
        if data is None:
            raise ItemLoadingError('There is no data available for item: {}'.format(self))

        downstream_item.write(data, with_metadata=with_metadata)
        return data

    def push(self, with_metadata=False):
        data = self.read(with_metadata=with_metadata)
        if data is None:
            raise ItemLoadingError('There is no data available for item: {}'.format(self))

        self.write(data, with_metadata=with_metadata)
        return data

    def make_directories(self):
        try:
            self.accessor.make_dir(self._uid, True)
        except:
            reraise(
                AccessorError,
                'Failed to make directories for item "{}". {}'.format(self, sys.exc_info()[1]),
                sys.exc_info()[2]
            )

    def remove(self, propagate=True):
        log.debug('Removing item "{}"'.format(self))
        try:
            self.accessor.rm(self._uid)
        except:
            reraise(
                AccessorError,
                'Failed to remove item "{}". {}'.format(self, sys.exc_info()[1]),
                sys.exc_info()[2]
            )
        if propagate and self.next_item:
            self.next_item.remove(propagate)
        log.debug('Done')

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return (
            "StorageItem(tags={}, fields={}, "
            "uid='{}', storage='{}')"
        ).format(
            repr(self._tags),
            repr(self._fields),
            self._uid,
            self.storage.name
        )


class StoragePool(object):

    def __init__(self, project, pool_config):
        self._project = project
        self._pool_config = validate_pool_config(pool_config)
        self._init_storages()

    def _init_storages(self):
        """Initialize storages from provided configuration.

        Returns:
            list: Cached list of Storage objects.

        """
        self._storages = []

        self._load_hooks()

        for storage_config in self._pool_config:

            storage_name = storage_config['name']

            try:
                storage = Storage.create_storage(storage_name, storage_config)
            except:
                reraise(
                    StorageError,
                    'Failed to create storage "{}". {}'.format(storage_name, sys.exc_info()[1]),
                    sys.exc_info()[2]
                )

            self._storages.append(storage)

    def _load_hooks(self):
        """Load hooks stored under current package."""
        bd_hooks.load([putils.join(putils.dirname(__file__), 'hooks')])

    def extract_data_from_filename(self, filename):
        filename = putils.normpath(filename)

        try:
            uid = filename[filename.index('/{}/'.format(self._project)) + 1:]
        except ValueError:
            raise ProjectNameNotFound(
                'Project name \'{}\' not found in path \'{}\''.format(self._project, filename)
            )

        for storage in self._storages:

            tags, fields = storage.get_data_from_uid(uid)
            if not (tags and fields):
                continue

            return tags, fields

    def get_item(self, tags):
        if isinstance(tags, TagsMixin):
            tags = tags.tags
        elif tags and not isinstance(tags, (tuple, list, set, frozenset)):
            raise InputError(
                'Argument "tags" has invalid type "{}"'.format(type(tags).__name__)
            )

        item = prev_item = None

        for storage in self._storages:

            meta_item = storage.get_item(tags)
            if not meta_item:
                continue

            if item is None:
                item = meta_item
            else:
                meta_item.set_prev_item(prev_item)

            prev_item = meta_item

        return item
