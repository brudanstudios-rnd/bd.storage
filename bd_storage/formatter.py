import string

from parse import parse


class StringFormatter(object):

    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    def __init__(self, field_formatting_config):
        self._parser_spec_mapping = {}
        self._format_spec_mapping = {}

        self._custom_type_parsers = {}

        for field_name, field_data in field_formatting_config.items():

            if 'regex' in field_data:

                custom_type = '_{}_'.format(field_name)
                if custom_type not in self._custom_type_parsers:
                    func = lambda x: x
                    func.pattern = field_data['regex']

                    self._custom_type_parsers[custom_type] = func

                self._parser_spec_mapping[field_name] = '{{{}:{}}}'.format(field_name, custom_type)

            if 'length' in field_data:
                self._format_spec_mapping[field_name] = '{{{}:>0{}}}'.format(
                    field_name, field_data['length']
                )

            if 'format' in field_data:
                self._format_spec_mapping[field_name] = '{{{}:{}}}'.format(
                    field_name, field_data['format']
                )

    def parse(self, input_str, format_str):
        try:
            typed_format = format_str.format(**dict(self._parser_spec_mapping, **self._format_spec_mapping))
        except KeyError as e:
            pass
        else:
            result = parse(typed_format, input_str, self._custom_type_parsers)
            if not result:
                return

            fields = result.named

            if 'version' in fields:
                fields['version'] = int(fields['version'])

            return fields

    def format(self, format_str, **kwargs):
        typed_format = string.Formatter().vformat(
            format_str, (), self.SafeDict(**self._format_spec_mapping)
        )
        return typed_format.format(**kwargs)
