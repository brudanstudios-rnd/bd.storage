from .errors import InputError


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


class ChainItemMixin(object):

    def __init__(self):
        self.next_item = None
        self.prev_item = None

    def iter_chain(self, upstream=True):
        item = self if upstream else self.get_upstream_item()
        while item:
            yield item
            item = item.next_item if upstream else item.prev_item

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

    def add_upstream_item(self, item):
        upstream_item = self.get_upstream_item()
        upstream_item.set_next_item(item.get_downstream_item())

    def add_downstream_item(self, item):
        downstream_item = self.get_downstream_item()
        item.get_upstream_item().set_next_item(downstream_item)