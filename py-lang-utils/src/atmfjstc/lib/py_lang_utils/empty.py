"""
Utilities for working with nulls, empty values etc.
"""

from collections.abc import Mapping, Sequence, Hashable


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

    nulls_set = set()
    empty_seqs_are_null = False
    empty_maps_are_null = False

    for null in nulls:
        if null is list:
            empty_seqs_are_null = True
        elif null is dict:
            empty_maps_are_null = True
        elif isinstance(null, Hashable):
            nulls_set.add(null)
        else:
            raise TypeError(f"Invalid null value (not hashable): {null!r}")

    def _test(value):
        if isinstance(value, Hashable):
            return value in nulls_set
        if isinstance(value, Sequence) and empty_seqs_are_null and len(value) == 0:
            return True
        if isinstance(value, Mapping) and empty_maps_are_null and len(value) == 0:
            return True

        return False

    return _test


def _is_none(value):
    return value is None
