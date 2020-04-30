"""
Utilities for working with objects that expose data fields.
"""

from typing import Dict, Any

from atmfjstc.lib.py_lang_utils.token import Token


NO_DEFAULT = Token(str_='NO_DEFAULT', repr_='NO_DEFAULT')


def get_obj_likely_data_fields_with_defaults(obj: object, include_properties=True) -> Dict[str, Any]:
    """
    Heuristically gets a list of all the likely public data fields in an arbitrary object, with their apparent defaults.

    To reiterate, the function is heuristic. There is no standard way for marking which fields in an arbitrary class
    are intended to represent public data. Among its many limitations, this function will be confused by data fields
    which store functions, and it also cannot read defaults set in the constructor.

    Args:
        obj: The object to analyze
        include_properties: If True, properties are considered data fields and included in the result (although it is
            of course impossible to know their "default" value)

    Returns:
        A dict of field names mapped to their apparent defaults (or the token NO_DEFAULT if one could not be
        ascertained). The fields "defined" in the object's ancestor classes will appear first.
    """

    # Phase 1
    fields = dict()

    for cls in reversed(obj.__class__.__mro__):
        for field in getattr(cls, '__annotations__', dict()).keys():
            if field not in fields:
                fields[field] = NO_DEFAULT

        fields.update(cls.__dict__)

    for field in obj.__dict__.keys():
        if field not in fields:
            fields[field] = NO_DEFAULT

    def _is_data_field(field):
        if field.startswith('_'):
            return False

        default = fields[field]
        if default is NO_DEFAULT:
            return True

        if isinstance(default, property) and include_properties:
            return True

        if hasattr(default, '__get__'):
            return False  # All other descriptors (methods etc) are trashed

        return True

    def _adjust_default(default):
        return NO_DEFAULT if isinstance(default, property) else default

    return {field: _adjust_default(default) for field, default in fields.items() if _is_data_field(field)}
