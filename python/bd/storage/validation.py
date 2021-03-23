import sys

from schema import Schema, And, Or, Use, Optional, Regex, SchemaError

from six import reraise

from .errors import *

schema = Schema([
    {
        'name': And(Use(str), len),
        'schema': And(Use(str), len),
        'fields': {
            Use(str): {
                Optional(Or('regex', 'format', 'type'), ): And(Use(str), len)
            }
        },
        'accessor': {
            'name': And(Use(str), len),
            Optional('kwargs'): dict
        },
        Optional('adapter'): {
            'name': And(Use(str), len),
            Optional('kwargs'): dict
        },
        Optional('tag_mask'): Regex('^[\w\s\&\|\^\(\)]*$')
    }
])


def validate_pool_config(pool_config):
    try:
        return schema.validate(pool_config)
    except SchemaError:
        reraise(StorageError, *sys.exc_info()[1:])
