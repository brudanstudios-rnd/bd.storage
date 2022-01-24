import re
import sys
import errno

from six import reraise

from .edits import FieldsEdit
from .errors import InputError, AccessorError
from .core import StorageItem
from .utils import putils
from .enums import ItemTypePrimaryFields


class UTBase(FieldsEdit):

    primary_field = None
    placeholder = ''

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
            fields.set_field(self.primary_field, primary_field_value)
        return self._meta_item.get_storage_item(fields)

    def pull(self, with_metadata=False):
        for member_item in self.get_items(from_upstream=True):
            member_item.pull(with_metadata)

    def push(self, with_metadata=False):
        for member_item in self.get_items(from_upstream=False):
            member_item.push(with_metadata)

    def get_items(self, from_upstream=False):
        fields = FieldsEdit(self.fields)
        fields.set_field(self.primary_field, self.placeholder)      # adding just to detect it later

        meta_item = self._meta_item.get_upstream_item() if from_upstream else self._meta_item

        rpath = meta_item.build_rpath(fields)
        if not rpath:
            return []

        primary_field_values = self._get_primary_field_values(meta_item, rpath)

        member_items = []

        for primary_field_value in primary_field_values:

            fields.set_field(self.primary_field, primary_field_value)

            member_item = meta_item.get_storage_item(fields)
            if member_item:
                member_items.append(member_item)

        return member_items

    def _get_primary_field_values(self, meta_item, rpath):
        raise NotImplementedError()


class UTItemRevision(UTBase):

    primary_field = ItemTypePrimaryFields.REVISION
    placeholder = 96969696969696

    def get_latest(self, from_upstream=False):
        storage_items = self.get_items(from_upstream)
        if storage_items:
            return storage_items[-1]

    def _get_primary_field_values(self, meta_item, rpath):
        primary_field_values = set()

        # rpath parts preceding the versioned part
        root_parts = []
        versioned_part = None

        placeholder_str = str(self.placeholder)

        for i, uid_part in enumerate(rpath.rstrip('/').split('/')):

            if placeholder_str in uid_part:
                versioned_part = uid_part
                break

            root_parts.append(uid_part)

        if versioned_part is None:
            return [1]

        uid_root = putils.join(*root_parts)
        uid_tail_pattern = re.escape(versioned_part).replace(placeholder_str, '(\d+)')

        try:
            uid_tails = meta_item.accessor.list(uid_root, recursive=False)
        except Exception as e:
            if isinstance(e, OSError) and e.errno == errno.ENOENT:
                return []

            reraise(AccessorError, AccessorError(e), sys.exc_info()[2])

        for uid_tail in sorted(uid_tails):
            match = re.match(uid_tail_pattern, uid_tail)
            if match:
                primary_field_values.add(int(match.group(1)))

        primary_field_values = list(primary_field_values)
        primary_field_values.sort()
        return primary_field_values


class UTItemSequence(UTItemRevision):
    primary_field = ItemTypePrimaryFields.SEQUENCE


class UTItemCollection(UTBase):
    primary_field = ItemTypePrimaryFields.COLLECTION

    def _get_primary_field_values(self, meta_item, rpath):
        try:
            relative_suffix_rpaths = meta_item.accessor.list(rpath)
        except Exception as e:
            reraise(AccessorError, AccessorError(e), sys.exc_info()[2])

        primary_field_values = set()
        for relative_suffix_rpath in relative_suffix_rpaths:
            primary_field_values.add(relative_suffix_rpath)

        primary_field_values = list(primary_field_values)
        primary_field_values.sort()
        return primary_field_values
