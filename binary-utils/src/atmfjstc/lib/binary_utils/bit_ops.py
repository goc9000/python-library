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
    """
    value = abs(value)

    result = []
    while value > 0:
        next_value = value & (value - 1)
        result.append(round(math.log2(value - next_value)))
        value = next_value

    return result
