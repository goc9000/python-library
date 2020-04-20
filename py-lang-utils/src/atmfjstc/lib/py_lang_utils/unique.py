from typing import Optional, TypeVar, Callable, Iterable, Hashable, List

from collections import namedtuple


T = TypeVar('T')

KeyFunc = Callable[[T], Hashable]


def iter_dedup(seq: Iterable[T], key: Optional[KeyFunc] = None) -> Iterable[T]:
    """
    Remove duplicates from a sequence (list, tuple, stream etc.) of elements.

    Args:
        seq: An iterable of elements to deduplicate. They must either be hashable, or `key` must be provided.
        key: A function that, applied to each element, provides a hashable representation of its aspect that must be
            unique.

    Returns:
        A stream of deduplicated elements, in their original order. Only the first item is kept out of all its
        duplicates.
    """

    get_key = key or (lambda x: x)
    seen = set()

    for item in seq:
        key = get_key(item)

        if key not in seen:
            yield item
            seen.add(key)


def dedup(seq: Iterable[T], key: Optional[KeyFunc] = None) -> List[T]:
    """
    Convenience function. Like `iter_dedup` but returns a list.

    Note that this differs from simply using ``list(set(iterable))`` in that it preserves the order of the elements and
    also allows a key= function.
    """
    return list(iter_dedup(seq, key=key))


DuplicateItemInfo = namedtuple('DuplicateItemInfo', [
    'duplicate_item', 'duplicate_item_pos', 'original_item', 'original_item_pos'
])
"""A structure that holds information about a pair of duplicate items in a collection."""


def find_duplicates(seq: Iterable[T], key: Optional[KeyFunc] = None) -> Optional[DuplicateItemInfo]:
    """
    Checks whether there are any duplicate elements in a sequence (list, tuple, stream etc.).

    Args:
        seq: An iterable of elements to check. They must either be hashable, or `key` must be provided.
        key: A function that, applied to each element, provides a hashable representation of its aspect that must be
            unique.

    Returns:
        None if the elements are unique, or a `DuplicateItemInfo` structure with info on the fist pair of duplicates
        found.

    Note: if the input is a stream, reading stops at the first encountered duplicate.
    """

    get_key = key or (lambda x: x)
    seen = dict()

    for index, item in enumerate(seq):
        key = get_key(item)

        if key in seen:
            return DuplicateItemInfo(
                duplicate_item=item,
                duplicate_item_pos=index,
                original_item=seen[key][0],
                original_item_pos=seen[key][1]
            )

        seen[key] = (item, index)

    return None


class DuplicateItemError(ValueError):
    dupe_info = None

    def __init__(self, text, dupe_info):
        super().__init__(text)
        self.dupe_info = dupe_info


def check_unique(seq: Iterable[T], key: Optional[KeyFunc] = None, item_name: str = 'item') -> Iterable[T]:
    """
    Verifies there are no duplicate elements in a sequence (list, tuple, stream etc.).

    Useful as a sanity check routine.

    Args:
        seq: An iterable of elements to check. They must either be hashable, or `key` must be provided.
        key: A function that, applied to each element, provides a hashable representation of its aspect that must be
            unique.
        item_name: A descriptive name for the kind of elements in the sequence, as it will appear in the thrown
            exception (e.g. 'Duplicate XXX')

    Returns:
        The original sequence, such that the function may be used in a fluent manner, e.g.
        ``items = check_unique(obtain_items())``. Meaningless if the input is a stream.

    Raises:
        DuplicateItemError: If duplicates were found.
    """

    dupes = find_duplicates(seq, key=key)

    if dupes is None:
        return seq

    raise DuplicateItemError(f"Duplicate {item_name}: {dupes.duplicate_item}", dupes)
