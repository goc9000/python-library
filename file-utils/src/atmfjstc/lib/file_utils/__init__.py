"""
A collection of utilities for working with files in general (no specific format or OS).
"""

from typing import AnyStr, Union
from os import PathLike


__version__ = '2.5.0'


PathType = Union[PathLike, AnyStr]
