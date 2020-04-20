"""
Utilities for working with nulls, empty values etc.
"""

from collections.abc import Mapping, Sequence, Hashable, Iterable


def make_null_test(nulls):
    """
    Helper that creates a function that tests whether values are null (or 'empty').

    The created callback will decide whether values are null based upon the specification in `nulls`:

    - If `nulls` is None, only None values are considered null
    - If `nulls` is an iterable (list, etc), it will be treated as a sequence of values that are considered null.

      - The items must be `Hashable`
      - Only `Hashable` values will be tested against the items, with two exceptions: if you specify the types `list`
        or `dict` as null values, then non-Hashable `Sequence`'s and `Mapping`'s, respectively, will also be considered
        null.
    """
    if nulls is None:
        return _is_none

    if not isinstance(nulls, Iterable):
        raise TypeError("Expecting an iterable of values to be considered null")

    nulls_set = set(nulls)

    def _test(value):
        if isinstance(value, Hashable):
            return value in nulls_set
        if isinstance(value, Sequence) and (list in nulls_set) and len(value) == 0:
            return True
        if isinstance(value, Mapping) and (dict in nulls_set) and len(value) == 0:
            return True

        return False

    return _test


def _is_none(value):
    return value is None
