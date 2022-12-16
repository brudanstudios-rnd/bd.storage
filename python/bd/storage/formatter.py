import sys
import string
import logging
import threading

from six import reraise

from ._vendor import parse
from ._vendor.cachetools import cachedmethod, LRUCache

from .errors import *

log = logging.getLogger(__name__)

parse.log.setLevel(logging.ERROR)

_formatter = string.Formatter()
_type_conversions = {"int": int, "float": float, "str": str}


def _dummy_func(x):
    return x


class FieldFormatter(object):
    class SafeDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    def __init__(self, field_formatting_config):
        self._parser_spec_mapping = {}
        self._format_spec_mapping = {}
        self._type_spec_mapping = {}
        self._defaults_spec_mapping = {}

        self._custom_type_parsers = {}
        self._cache = LRUCache(maxsize=5000)

        self._ensure_extra_fields(field_formatting_config)

        for field_name, field_data in field_formatting_config.items():

            if "regex" in field_data:

                custom_type = "_{}_".format(field_name)
                if custom_type not in self._custom_type_parsers:
                    func = lambda x: x
                    func.pattern = field_data["regex"]

                    self._custom_type_parsers[custom_type] = func

                self._parser_spec_mapping[field_name] = "{{{}:{}}}".format(
                    field_name, custom_type
                )

            if "format" in field_data:
                self._format_spec_mapping[field_name] = "{{{}:{}}}".format(
                    field_name, field_data["format"]
                )

            if "type" in field_data:
                self._type_spec_mapping[field_name] = field_data["type"]

    @cachedmethod(lambda self: self._cache, lock=threading.RLock)
    def parse(self, input_str, format_str):

        try:
            typed_format = _formatter.format(format_str, **self._parser_spec_mapping)
        except KeyError as e:
            pass
        except Exception as e:
            reraise(ParsingError, ParsingError(e), sys.exc_info()[2])
        else:
            result = parse.parse(
                typed_format, input_str, self._custom_type_parsers, case_sensitive=True
            )
            if not result:
                return

            fields = result.named

            self._ensure_typed(fields)

            return fields

    def format(self, template, **fields):
        self._ensure_typed(fields)

        typed_format = _formatter.vformat(
            template, (), self.SafeDict(**self._format_spec_mapping)
        )

        try:
            return _formatter.format(typed_format, **fields)
        except KeyError as e:
            raise FormattingError(
                'Unable to format template "{}" due to '
                "missing field: {}".format(template, str(e))
            )
        except Exception as e:
            reraise(FormattingError, FormattingError(e), sys.exc_info()[2])

    def _ensure_extra_fields(self, field_formatting_config):
        if "_index_" not in field_formatting_config:
            field_formatting_config["_index_"] = {
                "regex": r"\d{4}",
                "type": "int",
                "format": "04d",
            }
        if "_version_" not in field_formatting_config:
            field_formatting_config["_version_"] = {
                "regex": r"\d{3}",
                "type": "int",
                "format": "03d",
            }
        if "_suffix_" not in field_formatting_config:
            field_formatting_config["_suffix_"] = {"regex": r"[\.\-\w\d/\\]+"}

    def _ensure_typed(self, fields):
        for field, value in fields.items():

            type_conversion = self._type_spec_mapping.get(field)
            if not type_conversion or type_conversion not in _type_conversions:
                continue

            fields[field] = _type_conversions[type_conversion](value)
