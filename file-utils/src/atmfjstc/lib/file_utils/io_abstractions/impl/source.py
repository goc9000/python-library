from typing import Optional, Dict, BinaryIO, Iterator
from contextlib import contextmanager
from pathlib import Path
from io import BytesIO

from ...fileobj import get_fileobj_size, preserve_fileobj_pos

from .. import ResolvedBinaryDataSource

from .common import ResolvedBinaryDataInterfaceBase, FilesystemBasedBinaryDataInterfaceBase


class FilesystemBinaryDataSource(FilesystemBasedBinaryDataInterfaceBase, ResolvedBinaryDataSource):
    def exists(self) -> bool:
        return self._path.exists()

    @property
    def is_seekable(self) -> bool:
        return True

    def size(self) -> Optional[int]:
        return self._path.stat().st_size

    @contextmanager
    def open_data(self) -> Iterator[BinaryIO]:
        with self._path.open('rb') as fobj:
            yield fobj


class VirtualBinaryDataSourceBase(ResolvedBinaryDataInterfaceBase, ResolvedBinaryDataSource):
    # Defaults for virtual sources
    @property
    def is_seekable(self) -> bool:
        return True

    def exists(self) -> bool:
        return True


class MemoryBinaryDataSource(VirtualBinaryDataSourceBase):
    _buffer: bytes

    def __init__(self, buffer: bytes, filename_override: Optional[str] = None):
        super().__init__(filename_override=filename_override)

        self._buffer = buffer

    def size(self) -> Optional[int]:
        return len(self._buffer)

    @contextmanager
    def open_data(self) -> Iterator[BinaryIO]:
        with BytesIO(self._buffer) as fobj:
            yield fobj

    def _constructor_args(self) -> Dict:
        return dict(**super()._constructor_args(), buffer=self._buffer)


class StreamBinaryDataSource(VirtualBinaryDataSourceBase):
    _stream: BinaryIO
    _auto_rewind: bool

    def __init__(self, stream: BinaryIO, filename_override: Optional[str] = None, auto_rewind: bool = True):
        super().__init__(filename_override=filename_override)

        self._stream = stream
        self._auto_rewind = auto_rewind

    @property
    def is_seekable(self) -> bool:
        return hasattr(self._stream, 'seek') and hasattr(self._stream, 'tell')

    @property
    def location_on_filesystem(self) -> Optional[Path]:
        path = getattr(self._stream, 'name', None)

        return Path(path) if path else None

    @property
    def _natural_filename(self) -> Optional[str]:
        return self.location_on_filesystem.name if self.location_on_filesystem else None

    def size(self) -> Optional[int]:
        """
        Note that by design, even for seekable streams, size() will report the amount of data remaining to the end,
        not necessarily the size of the entire data. This is in keeping with the behavior of `open_data()`, which will
        return a stream over the data from the stream's current position, without automatically rewinding it.
        """
        return get_fileobj_size(self._stream, 'current') if self.is_seekable else None

    @contextmanager
    def open_data(self) -> Iterator[BinaryIO]:
        """
        By design, `open_data()` will return a stream over the data from the stream's current position, not from the
        beginning. It will also rewind the stream back to its current position when the context ends, such that all
        calls to `open_data()` return the same data.
        """
        if (not self._auto_rewind) or (not self.is_seekable):
            yield self._stream
            return

        with preserve_fileobj_pos(self._stream):
            yield self._stream

    def _constructor_args(self) -> Dict:
        return dict(**super()._constructor_args(), stream=self._stream, auto_rewind=self._auto_rewind)
