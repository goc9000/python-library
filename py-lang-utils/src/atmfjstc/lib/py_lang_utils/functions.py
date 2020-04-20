"""
Utilities for working with functions.
"""

from typing import Any


def seems_callback(value: Any) -> bool:
    """
    Checks whether a value looks like a callback.

    This function cannot possibly be very accurate without resorting to expensive inspect calls. What it does is check
    whether the value is a 'function' or 'method' (so as to distinguish it from other callables like classes). It is
    meant for distinguishing callback arguments (e.g. predicates) from non-functional ones.
    """
    return value.__class__.__name__ in ['function', 'method']
