"""
Utilities for decoding OS and filesystem-specific data enums and binary structures.

This is not intended to be a substitute for the Python `os` package. Rather, we focus on individual enums, structures
and tidbits that are not fully covered or decoded by the former. There is also a stronger focus on "forensics" as in
being able to analyze the data of any operating system while running any other, e.g. we do not need to have any
Windows stuff installed to be able to analyze Windows data.
"""


__version__ = '0.3.0'
