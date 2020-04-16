"""
Miscellaneous utilities for working with dicts and mappings.
"""


def copy_only_fields(source_dict, fields):
    """
    Creates a copy of a dict with only certain fields preserved.

    Other types of mappings will work too, but they must have a dict-like constructor that accepts an iterable of
    key-value pairs.

    For more advanced processing, consider the `convert_struct` module in the same package.
    """
    return source_dict.__class__((k, v) for k, v in source_dict.items() if k in fields)


def filter_dict_nulls(source_dict, *nulls):
    """
    Creates a copy of a dict with only non-null fields preserved. By default, a field is null if it is None.

    To specify other values that be considered null (e.g. False, 0, etc.), add them as arguments after the dict. Note
    that you will have to re-specify None if you still want it to be a null indicator.

    Other types of mappings will work too, but they must have a dict-like constructor that accepts an iterable of
    key-value pairs.

    For more advanced processing, consider the `convert_struct` module in the same package.
    """
    if len(nulls) == 0:
        nulls = {None}

    return source_dict.__class__((k, v) for k, v in source_dict.items() if v not in nulls)
