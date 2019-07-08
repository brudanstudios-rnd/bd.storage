import os
import sys
import logging

this = sys.modules[__name__]
this._root_logger = logging.getLogger('bd')


def get_logger(name):
    if name.startswith('bd_storage.'):
        name = name.replace('bd_storage.', 'bd.storage.')
        return logging.getLogger(name)

    return this._root_logger.getChild(name)
