class StorageError(Exception):
    pass


class StorageNotFoundError(StorageError):
    pass


class ItemError(StorageError):
    pass


class ItemNotFoundError(ItemError):
    pass


class ItemLoadingError(ItemError):
    pass


class InputError(StorageError):
    pass


class MetadataSerializationError(StorageError):
    pass


class ProjectNameNotFound(StorageError):
    pass


class FormatterError(StorageError):
    pass


class FormattingError(FormatterError):
    pass


class ParsingError(FormatterError):
    pass


class NotSequenceItemError(StorageError):
    pass


class SchemaError(StorageError):
    pass


class SchemaConfigError(SchemaError):
    pass


class AccessorError(StorageError):
    pass


class AccessorCreationError(AccessorError):
    pass


class AdapterError(StorageError):
    pass


class AdapterCreationError(AdapterError):
    pass
