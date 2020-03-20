import re
import string
import logging

from ._vendor.parse import parse

log = logging.getLogger(__name__)

_formatter = string.Formatter()
_type_conversions = {
    'int': int,
    'float': float,
    'str': str
}


class FieldFormatter(object):

    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    def __init__(self, field_formatting_config):
        self._parser_spec_mapping = {}
        self._format_spec_mapping = {}
        self._type_spec_mapping = {}

        self._custom_type_parsers = {}

        for field_name, field_data in field_formatting_config.items():
            
            if 'regex' in field_data:

                custom_type = '_{}_'.format(field_name)
                if custom_type not in self._custom_type_parsers:
                    func = lambda x: x
                    func.pattern = field_data['regex']

                    self._custom_type_parsers[custom_type] = func

                self._parser_spec_mapping[field_name] = '{{{}:{}}}'.format(field_name, custom_type)

            if 'format' in field_data:
                self._format_spec_mapping[field_name] = '{{{}:{}}}'.format(
                    field_name, field_data['format']
                )

            if 'type' in field_data:
                self._type_spec_mapping[field_name] = field_data['type']

    def parse(self, input_str, format_str):
        try:
            typed_format = _formatter.format(
                format_str, 
                **self._parser_spec_mapping
            )
        except KeyError as e:
            pass

        else:
            result = parse(typed_format, input_str, self._custom_type_parsers, case_sensitive=True)
            if not result:
                return

            fields = result.named

            self._ensure_typed(fields)

            return fields

    def format(self, format_str, **fields):
        self._ensure_typed(fields)

        typed_format = _formatter.vformat(
            format_str, (), self.SafeDict(**self._format_spec_mapping)
        )

        try:
            return _formatter.format(typed_format, **fields)
        except KeyError as e:
            log.error('Formatting failed due to missing field: {}'.format(str(e)))

    def _ensure_typed(self, fields):
        for field, value in fields.items():

            type_conversion = self._type_spec_mapping.get(field)
            if not type_conversion or type_conversion not in _type_conversions:
                continue

            fields[field] = _type_conversions[type_conversion](value)
