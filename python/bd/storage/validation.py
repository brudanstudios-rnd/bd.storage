import sys

from schema import Schema, And, Or, Use, Optional, Regex, SchemaError

from six import reraise

from .errors import *

schema = Schema(
    {
        "project": And(Use(str), len),
        "storages": [
            {
                "name": And(Use(str), len),
                "schema": And(Use(str), len),
                "fields": {
                    Use(str): {
                        Optional(
                            Or("regex", "format", "type", "label"),
                        ): And(Use(str), len),
                        Optional("choices"): And([str], len),
                    }
                },
                "accessor": {"name": And(Use(str), len), Optional("kwargs"): dict},
                Optional("adapter"): {
                    "name": And(Use(str), len),
                    Optional("kwargs"): dict,
                },
                Optional("tag_mask"): Regex(r"^[\w\s\&\|\^\(\)]*$"),
            }
        ],
    }
)


def validate_pool_config(pool_config):
    try:
        return schema.validate(pool_config)
    except SchemaError as e:
        reraise(StorageError, StorageError(e), sys.exc_info()[2])
