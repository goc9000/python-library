"""
A collection of utilities for working with files in general (no specific format or OS).
"""

from typing import AnyStr, Union
from os import PathLike


__version__ = '1.3.2'


PathType = Union[PathLike, AnyStr]
