def index_where(seq, callback):
    """
    Returns the first index in a sequence (list, tuple, stream etc) for which a callback applied to its element holds
    true. If the callback never holds true for any item in the sequence, returns None.

    This is somewhat similar to list.index() but searches for a condition, not a specific value.

    Note that the function also works on streams, including infinite ones. If the condition never holds true, it may
    cause an infinite loop.
    """
    for index, item in enumerate(seq):
        if callback(item):
            return index

    return None
