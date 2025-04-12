"""
Utilities for working with file objects.
"""

from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from typing import IO, Optional, BinaryIO, Iterator
from os import SEEK_SET, SEEK_CUR, SEEK_END
from io import BufferedIOBase, IOBase, TextIOBase, RawIOBase

from atmfjstc.lib.error_utils import ignore_errors


@contextmanager
def preserve_fileobj_pos(fileobj: IO) -> Iterator[int]:
    """
    Context manager for ensuring a fileobj's position is restored to where it was, once the context closes.

    The fileobj must obviously be seekable.

    Example use::

        with preserve_fileobj_pos(f):
            f.read(100)

        # f's position is now restored

    Args:
        fileobj: The file object to preserve the position of. Can be either byte- or text- based.

    Returns:
        The context manager returns the original position of the fileobj (since it has to read it anyway)
    """

    original_pos = fileobj.tell()

    try:
        yield original_pos
    finally:
        with ignore_errors():
            fileobj.seek(original_pos, SEEK_SET)


def get_fileobj_size(fileobj: IO, whence: str = 'start') -> int:
    """
    Gets the size of a fileobj by using its `seek` and `tell` functions.

    The fileobj must obviously be seekable. Its position is restored when the function returns.

    Args:
        fileobj: The file object to get the size of. Can be either byte- or text- based.
        whence: Specify 'start' to count from the start of the fileobj, regardless of its current position. Specify
            'current' to count from the stream's current position.

    Returns:
        The size of the fileobj, in bytes (or characters, for a text fileobj).
    """

    if whence not in ['start', 'current']:
        raise ValueError(f"'whence' must be 'start' or 'current', is {whence!r}")

    with preserve_fileobj_pos(fileobj) as original_pos:
        end_pos = fileobj.seek(0, SEEK_END)
        return end_pos - (0 if whence == 'start' else original_pos)


class SeekableBase(RawIOBase, metaclass=ABCMeta):
    _position: int = 0

    @abstractmethod
    def _end_position(self) -> int:
        raise NotImplementedError

    @property
    def _allow_seek_past_end(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = SEEK_SET) -> int:
        if self.closed:
            raise ValueError("Cannot seek in closed fileobj")

        if whence == SEEK_SET:
            self._position = offset
        elif whence == SEEK_CUR:
            self._position += offset
        elif whence == SEEK_END:
            self._position = self._end_position() + offset
        else:
            raise ValueError("whence should be os.SEEK_{SET|CUR|END}")

        self._position = max(0, self._position)

        if not self._allow_seek_past_end:
            self._position = min(self._position, self._end_position())

        return self._position

    def tell(self) -> int:
        return self._position


class FileObjSliceReader(SeekableBase, BufferedIOBase):
    """
    This class provides a virtual file object that reads within a slice ("window") of another file object's data.
    """

    _fileobj: BinaryIO

    _window_base: int
    _window_size: int

    def __init__(self, fileobj: BinaryIO, window_base: int, window_size: int):
        """
        Constructor.

        Args:
            fileobj: The underlying file object. It must be seekable.
            window_base: The start offset of the slice within the parent file object's data.
            window_size: The length of the slice within the parent file object's data.

        Caveats:

        - While the slice file object is active, it will perform seeks and reads on the master file object. It is not
          a problem if the master file object is also read/seek-ed by other entities, just as long as it's not happening
          while a function of the slice fileobj is active (e.g. in another thread).
        - Closing the master file object renders the slice object unusable.
        - Closing the slice file object has no effect on the master.
        """
        if not isinstance(fileobj, IOBase):
            raise TypeError(f"Input to {self.__class__.__name__} must be a file object")
        if isinstance(fileobj, TextIOBase):
            raise TypeError(f"Input file object must be binary, not text")
        if not fileobj.seekable():
            raise TypeError(f"Input file object must be seekable")

        total_size = get_fileobj_size(fileobj)

        if (window_base < 0) or (window_base > total_size):
            raise ValueError(f"Window base must be between 0 and total file size {total_size}, is {window_base}")
        if window_size < 0:
            raise ValueError("Window size must be non-negative")
        if window_base + window_size > total_size:
            raise ValueError(f"Window extends past end of file")

        self._fileobj = fileobj
        self._window_base = window_base
        self._window_size = window_size

    def _end_position(self) -> int:
        return self._window_size

    @property
    def _allow_seek_past_end(self) -> bool:
        return False

    def readable(self) -> bool:
        return True

    def read(self, size: Optional[int] = -1) -> bytes:
        size = self._prepare_read(size)

        data = bytearray()

        while len(data) < size:
            chunk = self._fileobj.read(size - len(data))
            data.extend(chunk)
            self._position += len(chunk)

            if len(chunk) == 0:
                break

        return bytes(data)

    def read1(self, size: int = -1) -> bytes:
        size = self._prepare_read(size)

        data = self._fileobj.read(size)

        self._position += len(data)

        return data

    def _prepare_read(self, size: Optional[int]) -> int:
        if self.closed:
            raise ValueError("Cannot read from closed fileobj")

        if (size is None) or (size < 0):
            size = self._window_size - self._position

        size = min(size, self._window_size - self._position)

        self._fileobj.seek(self._window_base + self._position)

        return size
