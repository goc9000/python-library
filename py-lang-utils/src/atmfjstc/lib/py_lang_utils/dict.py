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
