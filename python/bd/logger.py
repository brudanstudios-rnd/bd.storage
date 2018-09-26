import os
import sys
import logging


ROOT_LOGGER = logging.getLogger("bd")
ROOT_LOGGER.setLevel(logging.INFO)


class SingleLevelFilter(logging.Filter):
    def __init__(self, level, reject):
        self._level = level
        self._reject = reject

    def filter(self, record):
        if self._reject:
            return record.levelno != self._level
        else:
            return record.levelno == self._level


is_setup = False


def setup_logging(logger, format=None, datefmt='%d-%m %H:%M'):
    if not format:
        format = '[ %(levelname)-10s ] %(asctime)s - %(name)s - %(message)s'

    formatter = logging.Formatter(
        format,
        datefmt=datefmt
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(SingleLevelFilter(logging.INFO, False))
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.addFilter(SingleLevelFilter(logging.INFO, True))
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)


def get_logger(name):

    global is_setup

    if not is_setup:
        setup_logging(ROOT_LOGGER)
        is_setup = True

    if name.startswith("bd."):
        return logging.getLogger(name)

    return ROOT_LOGGER.getChild(name)

