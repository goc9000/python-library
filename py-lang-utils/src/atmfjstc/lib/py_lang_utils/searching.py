from typing import Iterable, TypeVar, Optional, Callable

from collections.abc import Sequence


T = TypeVar('T')


def index_where(seq: Iterable[T], callback: Callable[[T], bool]) -> Optional[int]:
    """
    Returns the first index in a sequence (list, tuple, stream etc) for which a callback applied to its element holds
    true. If the callback never holds true for any item in the sequence, returns None.

    This is somewhat similar to `list.index()` but searches for a condition, not a specific value.

    Note that the function also works on streams, including infinite ones. If the condition never holds true, it may
    cause an infinite loop.
    """
    for index, item in enumerate(seq):
        if callback(item):
            return index

    return None


def last_index_where(seq: Iterable[T], callback: Callable[[T], bool]) -> Optional[int]:
    """
    Returns the last index in a sequence (list, tuple, stream etc) for which a callback applied to its element holds
    true. If the callback never holds true for any item in the sequence, returns None.

    Note that the function also works on streams. However, an infinite stream will result in an infinite loop!
    """
    # Optimized version for vector-likes
    if isinstance(seq, Sequence):
        for index in range(len(seq) - 1, -1, -1):
            if callback(seq[index]):
                return index

        return None

    last_index = None

    for index, item in enumerate(seq):
        if callback(item):
            last_index = index

    return last_index
