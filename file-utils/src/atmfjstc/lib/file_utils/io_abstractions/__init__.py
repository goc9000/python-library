"""
Abstractions for uniformizing code for reading, writing and probing binary data originating in a variety of binary data
sources: files, file objects, memory buffers, etc.
"""

from abc import ABCMeta, abstractmethod
from pathlib import PurePath, Path
from typing import BinaryIO, Union, Optional, TypeVar, ContextManager
from functools import singledispatch
from io import IOBase


"""
Friendly data type to be used for specifying an input data source in interfaces, function parameters etc. It covers:

- `PurePath` | `str`: a file on the local filesystem, its location given as either a Path or string
- `bytes`: an in-memory buffer containing the data
- `BinaryIO`: a binary stream, reading data from a file or possibly some other abstraction
- `ResolvedBinaryDataSource`: an already-resolved abstract data source, for advanced situations
"""
BinaryDataSource = Union[PurePath, str, bytes, BinaryIO, 'ResolvedBinaryDataSource']

"""
Friendly data type to be used for specifying an output data destination in interfaces, function parameters etc. It
covers:

- `PurePath` | `str`: a new file on the local filesystem, its location given as either a Path or string
- `bytearray`: a buffer for saving data in memory
- `BinaryIO`: a binary stream, writing data to a file or possibly some other abstraction
- `ResolvedBinaryDataDestination`: an already-resolved abstract data destination, for advanced situations
"""
BinaryDataDestination = Union[PurePath, str, bytearray, BinaryIO, 'ResolvedBinaryDataDestination']


Self = TypeVar('Self', bound='ResolvedBinaryDataInterfaceCommon')


class ResolvedBinaryDataInterfaceCommon(metaclass=ABCMeta):
    @property
    @abstractmethod
    def filename(self) -> Optional[str]:
        """
        The name of the file behind the abstraction, which may be used in some cases for e.g. type detection.
        In-memory or abstract data sources do not have a filename by default, but a "virtual" one may be set by the
        caller.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def location_on_filesystem(self) -> Optional[Path]:
        """
        The location of the data on the current filesystem, if applicable. In-memory or virtual data sources obviously
        do not have this. It may be used for e.g. reopening the same data in some external utility like e.g. `unrar`.
        """
        raise NotImplementedError

    @abstractmethod
    def christen(self: Self, name: str) -> Self:
        """
        Returns a copy of this data interface, with a virtual filename set by the caller. It will override any
        original filename for filesystem-based sources.
        """
        raise NotImplementedError


class ResolvedBinaryDataSource(ResolvedBinaryDataInterfaceCommon):
    """
    Canonical interface for specifying an input data source, for use internally and in advanced situations.
    """

    @abstractmethod
    def exists(self) -> bool:
        """
        For filesystem-based sources, checks whether the input file actually exists (by design, data sources may point
        to a file that does not yet exist at the time of their initialization). In-memory sources, etc. are always
        considered to exist.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def is_seekable(self) -> bool:
        """
        Checks if the underlying data source is seekable. Most data sources are, except for when a non-seekable stream
        is used as a base (e.g. originating from some one-use-only abstraction).

        If the data source is not seekable, the stream provided by `open_data()` will not be seekable and the data
        can only be read once.
        """
        raise NotImplementedError

    @abstractmethod
    def size(self) -> Optional[int]:
        """
        The size of the data, if available. For file or memory-based sources, it is known, but not necessarily so for
        streams. For unseekable streams, the size is unknowable. Seekable streams will be assessed by seeking to their
        end, which may be expensive.
        """
        raise NotImplementedError

    @abstractmethod
    def open_data(self) -> ContextManager[BinaryIO]:
        """
        Returns a stream that can be used for reading the data. The stream is provided via a context manager protocol,
        so `with` should be used. When the context manager goes out of scope, the stream will be closed, unless the
        source is based on a stream to begin with, in which case the caller retains full control.
        """
        raise NotImplementedError


class ResolvedBinaryDataDestination(ResolvedBinaryDataInterfaceCommon):
    """
    Canonical interface for specifying an input data source, for use internally and in advanced situations.
    """

    @abstractmethod
    def occupied(self) -> bool:
        """
        For filesystem-based sources, checks whether another file or directory already exists in the place the
        destination points to (thus potentially requiring overwrite logic). Other kinds of sources are considered to
        always be free.
        """
        raise NotImplementedError

    @abstractmethod
    def open_data(self, append: bool = False) -> ContextManager[BinaryIO]:
        """
        Returns a stream that can be used for writing the data. The stream is provided via a context manager protocol,
        so `with` should be used. When the context manager goes out of scope, the stream will be closed, unless the
        source is based on a stream to begin with, in which case the caller retains full control.
        """
        raise NotImplementedError


@singledispatch
def resolve_data_source(source: BinaryDataSource) -> ResolvedBinaryDataSource:
    raise TypeError(f"Cannot resolve binary data source of type {source.__class__.__name__}")


@resolve_data_source.register
def _(source: PurePath) -> ResolvedBinaryDataSource:
    from .impl.source import FilesystemBinaryDataSource

    return FilesystemBinaryDataSource(Path(source))


@resolve_data_source.register
def _(source: str) -> ResolvedBinaryDataSource:
    from .impl.source import FilesystemBinaryDataSource

    return FilesystemBinaryDataSource(Path(source))


@resolve_data_source.register
def _(source: bytes) -> ResolvedBinaryDataSource:
    from .impl.source import MemoryBinaryDataSource

    return MemoryBinaryDataSource(source)


@resolve_data_source.register
def _(source: IOBase) -> ResolvedBinaryDataSource:
    from .impl.source import StreamBinaryDataSource

    return StreamBinaryDataSource(source)


@resolve_data_source.register
def _(source: ResolvedBinaryDataSource) -> ResolvedBinaryDataSource:
    return source


@singledispatch
def resolve_data_destination(dest: BinaryDataDestination) -> ResolvedBinaryDataDestination:
    raise TypeError(f"Cannot resolve binary data destination of type {dest.__class__.__name__}")


@resolve_data_destination.register
def _(dest: PurePath) -> ResolvedBinaryDataDestination:
    from .impl.dest import FilesystemBinaryDataDestination

    return FilesystemBinaryDataDestination(Path(dest))


@resolve_data_destination.register
def _(dest: str) -> ResolvedBinaryDataDestination:
    from .impl.dest import FilesystemBinaryDataDestination

    return FilesystemBinaryDataDestination(Path(dest))


@resolve_data_destination.register
def _(dest: bytearray) -> ResolvedBinaryDataDestination:
    from .impl.dest import MemoryBinaryDataDestination

    return MemoryBinaryDataDestination(dest)


@resolve_data_destination.register
def _(dest: IOBase) -> ResolvedBinaryDataDestination:
    from .impl.dest import StreamBinaryDataDestination

    return StreamBinaryDataDestination(dest)


@resolve_data_destination.register
def _(dest: ResolvedBinaryDataDestination) -> ResolvedBinaryDataDestination:
    return dest
