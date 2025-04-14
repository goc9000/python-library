"""
Utilities for working with file objects.
"""

from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from typing import IO, Optional, BinaryIO, Iterator, Union
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


class ByteArrayIO(SeekableBase, RawIOBase):
    """
    File object that allows writing to a `bytearray`.

    This is somewhat similar to a `BytesIO`, but with some key differences:

    - `BytesIO` writes to a private buffer whose contents need to be explicitly retrieved after writes are done. This
      abstraction works with a buffer provided by the caller, which is updated in real time as writes are performed.
    - The contents of the `BytesIO` buffer are lost when it is closed. This file object can be closed at any time
      with no effect on the contents of the provided buffer.

    The semantics of the read/write/seek operations are similar to those for a real file opened in random access
    read+write mode. In particular, one can seek at any position within the array as well as past it. Writes to an
    existing position will overwrite the content of the array at that position; writes past the end of the array will
    extend it.
    """

    _buffer: bytearray

    def __init__(self, buffer: bytearray):
        self._buffer = buffer
        self._position = len(buffer)

    def _end_position(self) -> int:
        return len(self._buffer)

    def readable(self) -> bool:
        return True

    def readall(self) -> bytes:
        data = bytes(self._buffer[min(self._position, len(self._buffer)):])

        self._position = len(self._buffer)

        return data

    def readinto(self, buffer: bytearray) -> int:
        total_read = min(max(0, len(self._buffer) - self._position), len(buffer))

        if total_read == 0:
            return 0

        buffer[0:total_read] = self._buffer[self._position:self._position + total_read]

        self._position += total_read

        return total_read

    def writable(self) -> bool:
        return True

    def truncate(self, size: Optional[int] = None) -> int:
        if size is None:
            size = self._position

        if size < len(self._buffer):
            self._buffer[size:] = b''
        elif size > len(self._buffer):
            self._buffer.extend(b'\x00' * (size - len(self._buffer)))

        return size

    def write(self, data: Union[bytes, bytearray]) -> int:
        if len(self._buffer) < self._position:
            self.truncate()

        if len(data) > 0:
            self._buffer[self._position:self._position + len(data)] = data

        self._position += len(data)

        return len(data)


class FakeSeekableReader(BufferedIOBase):
    """
    Adapter that wraps around a non-seekable file object (e.g. stdin) and provides some level of "fake" seekability,
    useful mainly for advanced "peeking" capabilitites. Specifically, one will be able to "rewind" only within
    `buffer_size` bytes of the last byte read.
    """

    _fileobj: BinaryIO

    _buffer_size: int
    _buffer: bytearray

    _position: int
    _real_position: int

    def __init__(self, fileobj: BinaryIO, buffer_size: int):
        self._fileobj = fileobj

        self._buffer_size = buffer_size
        self._buffer = bytearray()

        self._position = 0
        self._real_position = 0

    def readable(self) -> bool:
        return True

    def read(self, size: Optional[int] = -1) -> bytes:
        infy_size = (size is None) or (size < 0)

        data = bytearray()

        while (len(data) < size) or infy_size:
            chunk = self.read1(-1 if infy_size else (size - len(data)))

            data.extend(chunk)

            if len(chunk) == 0:
                break

        return bytes(data)

    def read1(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("Cannot seek in closed fileobj")

        infy_size = (size is None) or (size < 0)

        to_read_from_buf = self._real_position - self._position
        if not infy_size:
            to_read_from_buf = min(size, to_read_from_buf)

        if to_read_from_buf == 0:
            return self._read_real(size)

        buf_offset = len(self._buffer) + self._position - self._real_position
        buf_chunk = bytes(self._buffer[buf_offset:buf_offset + to_read_from_buf])

        self._position += len(buf_chunk)

        to_read_real = -1 if infy_size else (size - to_read_from_buf)

        if to_read_real == 0:
            return buf_chunk

        return buf_chunk + self._read_real(to_read_real)

    def _read_real(self, size: int = -1) -> bytes:
        data = self._fileobj.read(size)
        self._position += len(data)
        self._real_position += len(data)

        keep_offset = max(0, len(self._buffer) + len(data) - self._buffer_size)
        incoming_offset = max(0, len(data) - self._buffer_size)

        self._buffer[0:keep_offset] = b''
        self._buffer.extend(data[incoming_offset:])

        return data

    def _advance_real(self, size: int = -1):
        total_advanced = 0
        chunk_size = 1_000_000

        while True:
            to_read = chunk_size if (size == -1) else min(size - total_advanced, chunk_size)

            data = self._read_real(to_read)
            if len(data) == 0:
                break

            total_advanced += len(data)
            self._real_position += len(data)

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = SEEK_SET) -> int:
        if self.closed:
            raise ValueError("Cannot seek in closed fileobj")

        if whence == SEEK_SET:
            new_position = offset
        elif whence == SEEK_CUR:
            new_position = self._position + offset
        elif whence == SEEK_END:
            self._advance_real(-1)

            new_position = self._real_position + offset
        else:
            raise ValueError("whence should be os.SEEK_{SET|CUR|END}")

        new_position = max(0, new_position)

        if new_position <= self._real_position:
            if new_position < (self._real_position - self._buffer_size):
                raise ValueError(f"Cannot seek more than {self._buffer_size} bytes into the past")

            self._position = new_position

            return new_position

        self._advance_real(self._real_position - new_position)

        self._position = self._real_position

        return self._position

    def tell(self) -> int:
        return self._position
