import os
from typing import Optional, Dict, BinaryIO, Iterator
from contextlib import contextmanager
from pathlib import Path

from ...fileobj import ByteArrayIO

from .. import ResolvedBinaryDataDestination

from .common import FilesystemBasedBinaryDataInterfaceBase, ResolvedBinaryDataInterfaceBase


class FilesystemBinaryDataDestination(FilesystemBasedBinaryDataInterfaceBase, ResolvedBinaryDataDestination):
    def occupied(self) -> bool:
        return self._path.exists()

    @contextmanager
    def open_data(self, append: bool = False) -> Iterator[BinaryIO]:
        with self._path.open('r+b' if append else 'w+b') as fobj:
            if append:
                fobj.seek(0, os.SEEK_END)

            yield fobj


class VirtualBinaryDataDestinationBase(ResolvedBinaryDataInterfaceBase, ResolvedBinaryDataDestination):
    # Defaults for virtual destinations
    @property
    def occupied(self) -> bool:
        return False


class MemoryBinaryDataDestination(VirtualBinaryDataDestinationBase):
    _buffer: bytearray

    def __init__(self, buffer: bytearray, filename_override: Optional[str] = None):
        super().__init__(filename_override=filename_override)

        self._buffer = buffer

    @contextmanager
    def open_data(self, append: bool = False) -> Iterator[BinaryIO]:
        if not append:
            self._buffer.clear()

        yield ByteArrayIO(self._buffer)

    def _constructor_args(self) -> Dict:
        return dict(**super()._constructor_args(), buffer=self._buffer)


class StreamBinaryDataDestination(VirtualBinaryDataDestinationBase):
    _stream: BinaryIO

    def __init__(self, stream: BinaryIO, filename_override: Optional[str] = None):
        super().__init__(filename_override=filename_override)

        if not stream.writable():
            raise ValueError("Stream must be writable")

        self._stream = stream

    @property
    def location_on_filesystem(self) -> Optional[Path]:
        path = getattr(self._stream, 'name', None)

        return Path(path) if path else None

    @property
    def _natural_filename(self) -> Optional[str]:
        return self.location_on_filesystem.name if self.location_on_filesystem else None

    @contextmanager
    def open_data(self, append: bool = False) -> Iterator[BinaryIO]:
        if (not append) and self._stream.seekable():
            self._stream.seek(0, os.SEEK_SET)
            self._stream.truncate(0)

        yield self._stream

    def _constructor_args(self) -> Dict:
        return dict(**super()._constructor_args(), stream=self._stream)
