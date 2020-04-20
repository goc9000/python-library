"""
Utilities for working with nulls, empty values etc.
"""

from collections.abc import Mapping, Sequence, Hashable


def make_null_test(nulls):
    """
    Helper that creates a function that tests whether its value is null, according to the following rules:

    - If ``nulls`` is None, only None values are considered null
    - Otherwise, ``nulls`` must be a sequence of values that are considered null. The items must be Hashable, and only
      Hashable values will be tested, with two exceptions:
    - You can specify an empty list() or an empty dict() as null values. In this case, non-Hashable Sequences and
      Mappings, respectively, will also be considered null.
    """
    if nulls is None:
        return _is_none

    nulls_set = set()
    empty_seqs_are_null = False
    empty_maps_are_null = False

    for null in nulls:
        if isinstance(null, Hashable):
            nulls_set.add(null)
        elif isinstance(null, list):
            if len(null) > 0:
                raise TypeError("lists passed as nulls must be empty")
            empty_seqs_are_null = True
        elif isinstance(null, dict):
            if len(null) > 0:
                raise TypeError("dicts passed as nulls must be empty")
            empty_maps_are_null = True
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
