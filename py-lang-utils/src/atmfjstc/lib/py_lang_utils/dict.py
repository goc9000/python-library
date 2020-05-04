"""
Miscellaneous utilities for working with dicts and mappings.
"""

import typing
from typing import TypeVar

from collections.abc import Mapping

from atmfjstc.lib.py_lang_utils.empty import make_null_test, NullsSpec


K = TypeVar('K')
V = TypeVar('V')


def copy_only_fields(source_dict: typing.Mapping[K, V], fields: typing.Collection[K]) -> typing.Mapping[K, V]:
    """
    Creates a copy of a dict or mapping with only certain fields preserved.

    Args:
        source_dict: A dict, or a mapping that has a dict-like constructor that accepts an iterable of key-value pairs.
        fields: A list/set/etc. of the fields to keep

    Returns:
        A (shallow) copy of the mapping with the filtered fields. It will be of the same class as the input mapping.

    For more advanced processing, consider the `convert_struct` module in the same package.
    """

    return source_dict.__class__((k, v) for k, v in source_dict.items() if k in fields)


def filter_dict_nulls(source_dict: typing.Mapping[K, V], nulls: NullsSpec = None) -> typing.Mapping[K, V]:
    """
    Creates a copy of a dict or mapping with only non-null fields preserved. By default, a field is null if it is None.

    Args:
        source_dict: A dict, or a mapping that has a dict-like constructor that accepts an iterable of key-value pairs.
        nulls: A specification of which values should be considered null. See `make_null_test` for details.

    Returns:
        A (shallow) copy of the mapping with the filtered fields. It will be of the same class as the input mapping.

    For more advanced processing, consider the `convert_struct` module in the same package.
    """

    null_test = make_null_test(nulls)

    return source_dict.__class__((k, v) for k, v in source_dict.items() if not null_test(v))


def dict_no_nulls(*args, nulls_: NullsSpec = None, **kwargs) -> dict:
    """
    Drop-in replacement for the `dict` constructor that filters out null values. By default, null means None.

    Args:
        *args: Same as for `dict`: nothing, an iterable of key-value pairs, or a mapping to copy items from
        nulls_: A specification of which values should be considered null. See `make_null_test` for details.
        **kwargs: Same as for `dict`: more key-value pairs to add to the dict.

    Returns:
        The constructed dict.
    """

    null_test = make_null_test(nulls_)

    # Reproduce the logic of the dict constructor
    if len(args) == 0:
        pairs = []
    elif len(args) == 1:
        pairs = args[0].items() if isinstance(args[0], Mapping) else args[0]
    else:
        raise TypeError(f"dict_no_nones expected at most 1 arguments, got {len(args)}")

    return dict(
        ((key, value) for key, value in pairs if not null_test(value)),
        **{key: value for key, value in kwargs.items() if not null_test(value)}
    )
