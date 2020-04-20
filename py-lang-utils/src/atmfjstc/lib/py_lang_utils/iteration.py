"""
General purpose utilities for help with iteration.
"""

from typing import Iterable, Tuple, TypeVar


T = TypeVar('T')


def iter_with_first_last(seq: Iterable[T]) -> Iterable[Tuple[T, bool, bool]]:
    """
    Iterates over a sequence (list, tuple, generator etc) and adds to each value an indication of whether it is the
    first or last in the sequence.

    Example::

        for item, is_first, is_last in iter_with_first_last(range(10)):
            ...

    Note that the usage pattern is similar to `enumerate`. Sequences of any length can be handled, even infinite.
    """

    for (item, is_first), is_last in iter_with_last(iter_with_first(seq)):
        yield item, is_first, is_last


def iter_with_first(seq: Iterable[T]) -> Iterable[Tuple[T, bool]]:
    """
    Iterates over a sequence (list, tuple, generator etc) and adds to each value an indication of whether it is the
    first in the sequence.

    Example::

        for item, is_first in iter_with_first(range(10)):
            ...

    Note that the usage pattern is similar to `enumerate`. Sequences of any length can be handled, even infinite.
    """
    is_first = True

    for item in seq:
        yield item, is_first
        is_first = False


def iter_with_last(seq: Iterable[T]) -> Iterable[Tuple[T, bool]]:
    """
    Iterates over a sequence (list, tuple, generator etc) and adds to each value an indication of whether it is the
    last in the sequence.

    Example::

        for item, is_last in iter_with_last(range(10)):
            ...

    Note that the usage pattern is similar to `enumerate`. Sequences of any length can be handled, even infinite.
    """
    buffer = None
    buffer_used = False

    for item in seq:
        if buffer_used:
            yield buffer, False

        buffer = item
        buffer_used = True

    if buffer_used:
        yield buffer, True
