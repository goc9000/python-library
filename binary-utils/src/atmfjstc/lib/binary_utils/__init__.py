"""
Utilities for parsing binary and bit-level data.

This package can come in useful if you need to parse binary format files (e.g. ZIP archives) or operating system data
in binary format.

Note that owing to the interpreted nature of Python, these utilities are intrinsically very inefficient. They are meant
to handle files with hundreds or thousands of records at most. For larger data sets, it is best to consider using
modules written in C or some other systems programming language.
"""


__version__ = '1.2.2'