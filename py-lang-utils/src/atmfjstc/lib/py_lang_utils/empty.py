"""
Utilities for working with nulls, empty values etc.
"""

import typing

from typing import Callable, Any, Union
from collections.abc import Mapping, Sequence, Hashable, Iterable

from atmfjstc.lib.py_lang_utils.functions import seems_callback


NullTestCallback = Callable[[Any], bool]
NullsSpec = Union[Hashable, NullTestCallback, typing.Sequence[Hashable]]


def make_null_test(nulls: NullsSpec) -> NullTestCallback:
    """
    Helper that creates a function that tests whether values are null (or 'empty').

    The created callback will decide whether values are null based upon the specification in `nulls`:

    - If `nulls` is None, only None values are considered null
    - If `nulls` is an iterable (list, etc), it will be treated as a sequence of values that are considered null.

      - The items must be `Hashable`
      - Only `Hashable` values will be tested against the items, with two exceptions: if you specify the types `list`
        or `dict` as null values, then non-Hashable `Sequence`'s and `Mapping`'s, respectively, will also be considered
        null.

    - If `nulls` is a function (assumed to be itself a null test), it will be returned as-is
    - If `nulls` is a single Hashable item, it will be treated as the value to be considered null, as per list item #2
      above.
    - Any other specification is invalid.
    """
    if nulls is None:  # Treat this case quickly as it is the default
        return _is_none
    if seems_callback(nulls):
        return nulls
    if isinstance(nulls, Iterable):
        nulls_set = set(nulls)
    elif isinstance(nulls, Hashable):
        nulls_set = {nulls}
    else:
        raise TypeError(f"Invalid nulls specification: {nulls!r}")

    def _test(value):
        if isinstance(value, Hashable):
            return value in nulls_set
        if isinstance(value, Sequence) and (list in nulls_set) and len(value) == 0:
            return True
        if isinstance(value, Mapping) and (dict in nulls_set) and len(value) == 0:
            return True

        return False

    return _test


def _is_none(value: Any) -> bool:
    return value is None
