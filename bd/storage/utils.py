import re
import hashlib


class abstractclassmethod(classmethod):

    __isabstractmethod__ = True

    def __init__(self, callable):
        callable.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(callable)


def create_id(tags, fields):
    return hashlib.md5(
        str(
            tuple(sorted(tags)) + tuple(sorted(fields.items()))
        ).encode('UTF8')
    ).hexdigest()


def remove_extra_fields(fields):
    return dict(filter(lambda x: not x[0].startswith('__'), fields.items()))

def remove_extra_tags(tags):
    return list(filter(lambda tag: not tag.startswith('__'), tags))


def parse_mask(mask):
    return list(
        filter(
            None, 
            re.split(
                r'([\(\)\|\&])', 
                mask.replace(' ', '').replace('||', '|').replace('&&', '&')
            )
        )
    )


def match_tags(mask, tags):
    """Check whether the tags match the provided mask.
    
    Args:
        mask (list[str] or str): parsed or not parsed tag mask.
        tags (list[str]): list of tags to match.

    Returns:
        bool: True if matches, False otherwise.

    """
    if not isinstance(mask, list):
        mask = parse_mask(mask)

    expression = []

    for item in mask:

        if item in '()':
            expression.append(item)
        elif item == '|':
            expression.append('or')
        elif item == '&':
            expression.append('and')
        elif item == '^':
            expression.append('not')
        else:
            if item[0] == '^':
                expression.append(str(item[1:] not in tags))
            else:
                expression.append(str(item in tags))

    try:
        return eval(' '.join(expression), None, None)
    except:
        return False