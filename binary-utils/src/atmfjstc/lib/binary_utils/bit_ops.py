"""
A collection of utilities for bit manipulation, similar to those in Bit Twiddling Hacks or Hacker's Delight.

Note that owing to the interpreted nature of Python, these cannot possibly achieve any degree of efficiency. For
processing large amounts of data, it's better to use `numpy` or some other library.

Reference: https://graphics.stanford.edu/~seander/bithacks.html
"""

import math

from typing import List


def get_set_bits(value: int) -> List[int]:
    """
    Returns a list of all set bits in an integer. E.g. for 24, returns [3,4] since 24 = (1 << 3) + (1 << 4)

    The bit indexes are always returned in ascending order.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    if value < 0:
        raise ValueError("Negative values are not supported")

    return [round(math.log2(pow2)) for pow2 in split_powers2(value)]


def split_powers2(value: int) -> List[int]:
    """
    Returns a list of the powers of 2 that make up an integer. E.g. for 24, returns [8, 16], since
    8 + 16 = 2^3 + 2^4 == 24

    The powers are always returned in ascending order.

    Negative values are not supported as this is mainly intended for taking apart values representing masks and flags.
    """
    if value < 0:
        raise ValueError("Negative values are not supported")

    result = []
    while value > 0:
        next_value = value & (value - 1)
        result.append(value - next_value)
        value = next_value

    return result
