from .mixins import TagsMixin, FieldsMixin


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


class TagsEdit(TagsMixin):
    def remove_extra_tags(self):
        self._tags = list(filter(lambda tag: not tag.startswith("_"), self._tags))
        return self

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

    def remove_all_tags(self):
        self._tags = []
        return self


class FieldsEdit(FieldsMixin):
    def remove_extra_fields(self):
        self._fields = dict(
            filter(lambda x: not x[0].startswith("_"), self._fields.items())
        )
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

    def remove_all_fields(self):
        self._fields = {}
        return self
