import os
import sys
import logging
import inspect

LOGGER = logging.getLogger("bd")


class SingleLevelFilter(logging.Filter):
    def __init__(self, level, reject):
        self._level = level
        self._reject = reject

    def filter(self, record):
        if self._reject:
            return record.levelno != self._level
        else:
            return record.levelno == self._level


formatter = logging.Formatter(
    '[ %(levelname)-10s ] %(asctime)s - %(name)s - %(message)s',
    datefmt='%d-%m %H:%M'
)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.addFilter(SingleLevelFilter(logging.INFO, False))
LOGGER.addHandler(stdout_handler)

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.addFilter(SingleLevelFilter(logging.INFO, True))
LOGGER.addHandler(stderr_handler)

stdout_handler.setFormatter(formatter)
stderr_handler.setFormatter(formatter)

LOGGER.setLevel(logging.INFO)


def get_logger(name=None):
    if not name:
        source = inspect.stack()[1]
        mod = inspect.getmodule(source[0])
        name = mod.__name__

    if not name.startswith("bd."):
        name = "bd." + name

    return logging.getLogger(name)


