from collections import namedtuple


def iter_dedup(seq, key=None):
    """
    Streams elements from a sequence (list, tuple, stream etc.) with duplicates eliminated (the first element is kept).

    By default, the elements must be hashable. If they are not, or if only some aspect of them must be unique, you can
    use the `key` parameter to supply a lambda function that will be called on each element to provide its hash.
    """
    get_key = key or (lambda x: x)
    seen = set()

    for item in seq:
        key = get_key(item)

        if key not in seen:
            yield item
            seen.add(key)


def dedup(seq, key=None):
    """
    Convenience function. Like `iter_dedup()` but returns a list.

    Note that this differs from simply using `list(set(iterable))` in that it preserves the order of the elements and
    also allows a key= function.
    """
    return list(iter_dedup(seq, key=key))


DuplicateItemInfo = namedtuple('DuplicateItemInfo', [
    'duplicate_item', 'duplicate_item_pos', 'original_item', 'original_item_pos'
])
"""A structure that holds information about a pair of duplicate items in a collection."""


def find_duplicates(seq, key=None):
    """
    Checks whether there are any duplicate elements in a sequence (list, tuple, stream etc.).

    Returns None if the elements are unique, or a DuplicateItemInfo structure with info on the fist pair of duplicates
    found.

    By default, the elements must be hashable. If they are not, or if only some aspect of them must be unique, you can
    use the `key` parameter to supply a lambda function that will be called on each element to provide its hash.

    Warning: if the input is a stream, processing stops at the first encountered duplicate.
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


def check_unique(seq, key=None, item_name='item'):
    """
    Throws an exception if there are any duplicate elements in a sequence (list, tuple, stream etc.).

    Useful as a sanity check routine. Returns the original sequence such that the function may be used in a fluent
    manner, e.g. `items = check_unique(obtain_items())`.

    By default, the elements must be hashable. If they are not, or if only some aspect of them must be unique, you can
    use the `key` parameter to supply a lambda function that will be called on each element to provide its hash.

    Warning: if the input is a stream, processing stops at the first encountered duplicate. The return value will also
    be meaningless.
    """
    dupes = find_duplicates(seq, key=key)

    if dupes is None:
        return seq

    raise DuplicateItemError(f"Duplicate {item_name}: {dupes.duplicate_item}", dupes)
