"""
Miscellaneous utilities for working with dicts and mappings.
"""

from collections.abc import Mapping

from atmfjstc.lib.py_lang_utils.empty import make_null_test


def copy_only_fields(source_dict, fields):
    """
    Creates a copy of a dict with only certain fields preserved.

    Other types of mappings will work too, but they must have a dict-like constructor that accepts an iterable of
    key-value pairs.

    For more advanced processing, consider the `convert_struct` module in the same package.
    """
    return source_dict.__class__((k, v) for k, v in source_dict.items() if k in fields)


def filter_dict_nulls(source_dict, nulls=None):
    """
    Creates a copy of a dict with only non-null fields preserved. By default, a field is null if it is None.

    To specify other values that should be considered null (e.g. False, 0, etc.), put them in a sequence and pass it
    via the ``nulls=`` parameter. Note that you will have to re-specify None if you still want it to be a null
    indicator. As an extra, you can specify an empty dict or an empty list as null values to filter out any empty
    Mapppings or Sequences (even if they are not hashable). Finally, you can also pass a function in the ``nulls=``
    parameter that should return True for null values.

    Other types of mappings will work too, but they must have a dict-like constructor that accepts an iterable of
    key-value pairs.

    For more advanced processing, consider the `convert_struct` module in the same package.
    """
    null_test = make_null_test(nulls)

    return source_dict.__class__((k, v) for k, v in source_dict.items() if not null_test(v))
