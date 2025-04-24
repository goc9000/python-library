"""
Utilities for decoding archive format-specific data enums and binary structures.

This is not intended to be a collection of complete archive parsers like `zipfile`, `rarfile` etc. Rather, we focus
on individual enums, structures and tidbits that are not fully covered or decoded by the former. The utilities herein
can also form a base for building alternative ZIP, RAR etc. parsers of our own.
"""


__version__ = '0.12.0'
