"""
A collection of utilities for bit manipulation, similar to those in Bit Twiddling Hacks or Hacker's Delight.

Note that owing to the interpreted nature of Python, these cannot possibly achieve any degree of efficiency. For
processing large amounts of data, it's better to use `numpy` or some other library.

Reference: https://graphics.stanford.edu/~seander/bithacks.html
"""

import math

from typing import List, Iterable


def get_set_bits(value: int) -> List[int]:
    """
    Returns a list of all set bits in an integer. E.g. for 24, returns [3,4] since 24 = (1 << 3) + (1 << 4)

    The bit indexes are always returned in ascending order.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    return list(iter_set_bits(value))


def iter_set_bits(value: int) -> Iterable[int]:
    """
    Iterates through all set bits in an integer. E.g. for 24, yields 3 and then 4, since 24 = (1 << 3) + (1 << 4)

    The bit indexes are always returned in ascending order.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    if value < 0:
        raise ValueError("Negative values are not supported")

    yield from (round(math.log2(pow2)) for pow2 in iter_powers2(value))


def split_powers2(value: int) -> List[int]:
    """
    Returns a list of the powers of 2 that make up an integer. E.g. for 24, returns [8, 16], since
    8 + 16 = 2^3 + 2^4 == 24

    The powers are always returned in ascending order.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    return list(iter_powers2(value))


def iter_powers2(value: int) -> Iterable[int]:
    """
    Iterates through the powers of 2 that make up an integer. E.g. for 24, yields 8 and then 16, since
    8 + 16 = 2^3 + 2^4 == 24

    The powers are always returned in ascending order.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    if value < 0:
        raise ValueError("Negative values are not supported")

    while value > 0:
        next_value = value & (value - 1)
        yield value - next_value
        value = next_value


_INT_BIT_COUNT_AVAILABLE = hasattr(0, 'bit_count')


def count_bits(value: int) -> int:
    """
    Returns the number of set bits in an integer. E.g. for 24, returns 2 since 24 = (1 << 3) + (1 << 4)

    This operation is also called a "population count".

    Starting with Python 3.10, one can use the (undoubtedly much faster) int.bit_count() function. This implementation
    is still useful when dealing with older Pythons.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    if value < 0:
        raise ValueError("Negative values are not supported")

    if _INT_BIT_COUNT_AVAILABLE:
        return value.bit_count()

    # There are all sorts of possible accelerations for this but we're not gonna bother as this is just a stopgap
    result = 0

    while value > 0:
        next_value = value & (value - 1)
        result += 1
        value = next_value

    return result


def is_power_of_2(value: int) -> bool:
    """
    Checks if a value is a power of 2.

    Negative values are not supported.
    """
    if value < 0:
        raise ValueError("Negative values are not supported")

    return (value > 0) and (value & (value - 1) == 0)
