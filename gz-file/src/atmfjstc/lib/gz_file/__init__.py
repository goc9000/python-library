"""
This package provides an advanced interface for accessing multi-member GZip files (analogous to TarFile etc.)

With respect to the built-in `gzip.GZipFile` class in Python, this interface offers:

- Multi-member support (i.e. multiple ``.gz`` files concatenated in one, which is allowed by the standard)
- Full extraction of all available metadata (comments, file name, extra field, flags etc)

The main class of interest is `GZFile`. We can open a gzip file like so::

    gz_file = GZFile('path/to/file.gz')

and obtain all the entries as `GZEntry` objects::

    for entry in gz_file:
        print(entry)

to read or extract an entry's data, we can use::

    with gz_file.open(gz_file.entries[1]) as f:
        f.read()

More details are available in the `GZFile` and `GZEntry` docs.
"""

import zlib
import os

from dataclasses import dataclass
from typing import ContextManager, BinaryIO, AnyStr, Union, Optional, Tuple, TypeVar, Type
from os import PathLike
from io import IOBase, BufferedIOBase
from enum import IntFlag, IntEnum
from gzip import GzipFile

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader, BinaryReaderFormatError
from atmfjstc.lib.file_utils.fileobj import FileObjSliceReader


GZIP_MAGIC = b'\x1f\x8b'


class GZFile(ContextManager['GZFile']):
    """
    This class provides access to a GZip archive stored in a file or file object.

    A `GZFile` scans the input file as soon as it is constructed. Afterwards, data about the archive is available in
    the following attributes:

    - `entries`: A tuple of `GZEntry` objects describing each entry in the archive, in the order they occur in the
      file. Most practical GZip archives have only one entry, but more are allowed by the standard.
    - `trailing_zeros`: The number of trailing 0 bytes found after the entries, which is apparently allowed in
      practice.

    The content of an entry can be opened for reading or extraction by passing it to the `open` method.

    A `GZFile` can be either open and closed manually::

        gzf = GZFile("file.gz")
        print(gzf.entries)
        gzf.close()

    or used as a context manager::

        with GZFile("file.gz") as gzf:
            print(gzf.entries)

    This class does not offer functionality for writing GZip archives.
    """

    _fileobj: BinaryIO
    _fileobj_owned: bool = False

    _entries: Tuple['GZEntry'] = ()
    _trailing_zeros: int = 0

    def __init__(self, path_or_fileobj: Union[PathLike, AnyStr, BinaryIO]):
        """
        Opens a GZip archive for reading.

        Args:
            path_or_fileobj: Either a filename, or an open file object containing the archive.

        Raises:
            NotAGZipFileError: If the data does not match the structure of a GZip file
            GZipFileCorruptError: If the file seemed to be a GZip archive, but its structure is corrupt or incorrect

        There are several caveats if a file object is passed:

        - The archive will be read from the current position in the fileobj, to the end. It is not automatically
          rewound!
        - The data in the file object should not be changed during the lifetime of the `GZFile`. It only reads the
          archive once and does not expect any changes.
        - The file object should be kept open for the lifetime of the `GZFile` if we need to read the contents of the
          entries.
        - The `GZFile` will not close the file object itself when the context ends.

        Finally, note that due to the limits of the GZip format, a file must be parsed in its entirety, including the
        compressed data, in order to locate all members and validate them. Opening very large archives will be expensive
        even if all you want to do is read the metadata.
        """

        if isinstance(path_or_fileobj, IOBase):
            if not path_or_fileobj.seekable():
                raise ValueError("File object must be seekable")

            self._fileobj = path_or_fileobj
        else:
            self._fileobj = open(path_or_fileobj, 'rb')
            self._fileobj_owned = True

        self._read_archive()

    @property
    def entries(self) -> Tuple['GZEntry']:
        """
        Metadata about the entries in the archive, in the order they appear.
        """
        return self._entries

    @property
    def trailing_zeros(self) -> int:
        """
        The number of trailing zero bytes after the last entry in the archive.
        """
        return self._trailing_zeros

    def open(self, entry: 'GZEntry') -> BufferedIOBase:
        """
        Opens the content of an entry for perusal and extraction.

        The GZip file must still be open for this to work.

        Args:
            entry: A GZIP file entry, as obtained from the `entries` attribute.

        Returns:
            An open file object, in binary mode. If you need text access, wrap it in a `TextIOWrapper`.

        Warning: do not manipulate entry file objects from multiple threads simultaneously.
        """

        if self._fileobj.closed:
            raise ValueError("Cannot read entries because the underlying file object has been closed")

        if entry not in self._entries:
            raise ValueError("Entry does not belong to this GZip file!")

        return GzipFile(
            fileobj=FileObjSliceReader(self._fileobj, entry.entry_start_offset, entry.total_entry_size),
            mode='rb',
            filename=entry.original_filename or entry.raw_original_filename,
        )

    def close(self):
        """
        Closes the underlying file object.

        Once the file is closed, you can still read the metadata for the entries, but you won't be able to open their
        contents.

        Note that this method closes the file object regardless of whether it was created by `GZFile` or received from
        elsewhere!
        """

        if self._fileobj is not None:
            self._fileobj.close()

    def __enter__(self) -> 'GZFile':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if (not self._fileobj_owned) or (self._fileobj is None) or self._fileobj.closed:
            return

        self._fileobj.close()

    def _read_archive(self):
        reader = BinaryReader(self._fileobj, big_endian=False)

        if not reader.peek_magic(GZIP_MAGIC):
            raise NotAGZipFileError(reader.name())

        entries = []

        while reader.bytes_remaining() > 0:
            if reader.peek(1) == b'\x00':
                while reader.bytes_remaining() > 0:
                    data = reader.read_at_most(1000000)
                    if data.count(b'\x00') < len(data):
                        raise GZipFileCorruptError(reader.name()) from \
                            BadGZipFileError("There is data after the entries, but it is not all zeroes")

                    self._trailing_zeros += len(data)

                break

            entries.append(GZEntry.read_from_binary(reader))

        self._entries = tuple(entries)


class GZEntryFlags(IntFlag):
    IS_TEXT = 1
    HAS_HEADER_CRC = 2
    HAS_EXTRA = 4
    HAS_NAME = 8
    HAS_COMMENT = 16

    RESERVED_MASK = 224


class GZCompressionMethod(IntEnum):
    DEFLATE = 8


class GZDeflateCompressionFlags(IntFlag):
    MAXIMUM = 2
    FAST = 4


class GZHostOS(IntEnum):
    FAT = 0
    AMIGA = 1
    VMS = 2
    UNIX = 3
    VM_CMS = 4
    ATARI_TOS = 5
    HPFS = 6
    MACINTOSH = 7
    Z_SYSTEM = 8
    CPM = 9
    TOPS20 = 10
    NTFS = 11
    QDOS = 12
    ACORN_RISCOS = 13
    UNKNOWN = 255


@dataclass(frozen=True)
class GZEntry:
    """
    An object containing the full metadata for an entry in a GZip archive.

    Note that objects of this type are just inert data containers. They can be copied from their originating `GZFile`
    object and are unaffected by its closure.

    Attributes:
        flags: A `GZEntryFlags` enum containing the flags set for this entry. The only one of potential use is
            `IS_TEXT`, which marks whether the content is likely a text file. The other flags just control parsing and
            are automatically used by the entry decoder.
        compression_method: A `GZCompressionMethod` enum specifying the compression method used for the entry, or
            an int, if it is not recognized. In practice, virtually all existing GZip files use DEFLATE.
        compression_flags: A compression-method dependent enum specifying flags specific to that compression method,
            or an int, if the compression method is unrecognized. In practice, this will nearly always be a
            `GZDeflateCompressionFlags` indicating whether fast vs maximum compression was used.
        compressed_length: The size of the compressed data, in bytes.
        uncompressed_length: The size of the uncompressed data, in bytes
        uncompressed_crc32: The CRC-32 hash of the uncompressed data
        entry_start_offset: The offset, in bytes, at which this entry occurs in the containing GZip file
        data_start_offset: The offset, in bytes, at which the data for this entry occurs in the containing GZip file
        host_os: [Optional] A `GZHostOS` enum specifying the operating system under which archival was performed, or
            an int if it is unrecognized.
        unix_timestamp: [Optional] A UNIX timestamp for the entry, usually representing the file last modification time.
        raw_extra_field: [Optional] A bytes object representing the content of the EXTRA field for this entry. This
            seems to have never been widely used.
        original_filename: [Optional] The original filename for this entry, as a string. It is only a suggestion, as in
            practice GZip archives are single-file and the caller can just strip the ``.gz`` extension from the archive.
        raw_original_filename: [Optional] The original filename, as a byte string, if for some reason it could not be
            interpreted as valid LATIN-1 characters.
        comment: [Optional] A comment for this entry, as a string.
        raw_comment: [Optional] The entry comment, as a byte string, if for some reason it could not be interpreted as
            valid LATIN-1 characters.
    """

    flags: GZEntryFlags

    compression_method: Union[GZCompressionMethod, int]
    compression_flags: Union[GZDeflateCompressionFlags, int]
    compressed_length: int
    uncompressed_length: int
    uncompressed_crc32: int

    entry_start_offset: int
    data_start_offset: int

    host_os: Optional[Union[GZHostOS, int]] = None

    unix_timestamp: Optional[int] = None

    raw_extra_field: Optional[bytes] = None

    original_filename: Optional[str] = None
    raw_original_filename: Optional[bytes] = None

    comment: Optional[str] = None
    raw_comment: Optional[bytes] = None

    @property
    def total_entry_size(self) -> int:
        return self.data_start_offset - self.entry_start_offset + self.compressed_length + 8

    @staticmethod
    def read_from_binary(reader: BinaryReader) -> 'GZEntry':
        entry_start_offset = reader.tell()

        raw_extra_field = None
        raw_filename = None
        raw_comment = None

        try:
            reader.expect_magic(GZIP_MAGIC, 'GZip magic')
            compression_method, flags, timestamp, compress_flags, host_os = \
                reader.read_struct('BBIBB', 'GZip entry header')

            if compression_method != GZCompressionMethod.DEFLATE:
                raise NotImplementedError(
                    f"Fount a GZ entry with compression method {compression_method}. Only Deflate entries are "
                    f"supported (don't know how to parse past other types)"
                )

            if flags & GZEntryFlags.RESERVED_MASK:
                raise NotImplementedError(
                    f"Found a GZ entry with flags: {flags:08b}. As per the spec, cannot parse the entry when reserved "
                    f"bits are set, as they may indicate the presence of extra members we don't know how to parse."
                )

            if flags & GZEntryFlags.HAS_EXTRA:
                raw_extra_field = reader.read_length_prefixed_bytes('extra field', length_bytes=2)
            if flags & GZEntryFlags.HAS_NAME:
                raw_filename = reader.read_null_terminated_bytes('entry original name')
            if flags & GZEntryFlags.HAS_COMMENT:
                raw_comment = reader.read_null_terminated_bytes('entry comment')
            if flags & GZEntryFlags.HAS_HEADER_CRC:
                reader.skip_bytes(2)  # Can't be arsed to check the header CRC, if there are errors we'll know soon

            data_start_offset = reader.tell()
            uncompressed_length = 0
            crc32 = zlib.crc32(b'')

            BUF_SIZE = 64000000

            decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

            compressed_data = b''

            while not decompressor.eof:
                if len(compressed_data) == 0:
                    compressed_data = reader.read_at_most(BUF_SIZE)
                    if len(compressed_data) == 0:
                        raise BadGZipFileError("File ends in the middle of a compressed block")

                decompressed_data = decompressor.decompress(compressed_data, BUF_SIZE)

                uncompressed_length += len(decompressed_data)
                crc32 = zlib.crc32(decompressed_data, crc32)

                compressed_data = decompressor.unconsumed_tail

            reader.seek(-len(decompressor.unused_data), os.SEEK_CUR)

            declared_crc32, declared_size = reader.read_struct('II', 'GZip entry footer')

            crc32 &= 0xffffffff
            if crc32 != declared_crc32:
                raise BadGZipFileError(
                    f"Entry CRC failed (declared: 0x{declared_crc32:08x}, actual: 0x{crc32:08x})"
                )

            if declared_size != uncompressed_length & 0xffffffff:
                raise BadGZipFileError(
                    f"Entry size does not match the declared size in the lowest 32 bits (declared: {declared_size}), "
                    f"actual: {uncompressed_length})"
                )
        except BadGZipFileError as e:
            raise GZipFileCorruptError(reader.name()) from e
        except BinaryReaderFormatError as e:
            raise GZipFileCorruptError(reader.name()) from e

        original_filename, raw_filename = _try_decode(raw_filename)
        comment, raw_comment = _try_decode(raw_comment)

        if compression_method == GZCompressionMethod.DEFLATE:
            compress_flags = GZDeflateCompressionFlags(compress_flags)

        return GZEntry(
            flags=GZEntryFlags(flags),
            compression_method=_as_enum(compression_method, GZCompressionMethod),
            compression_flags=compress_flags,
            compressed_length=reader.tell() - data_start_offset - 8,
            uncompressed_length=uncompressed_length,
            uncompressed_crc32=declared_crc32,
            entry_start_offset=entry_start_offset,
            data_start_offset=data_start_offset,
            host_os=_as_enum(host_os, GZHostOS) if host_os != 255 else None,
            unix_timestamp=timestamp if timestamp != 0 else None,
            raw_extra_field=raw_extra_field,
            original_filename=original_filename,
            raw_original_filename=raw_filename,
            comment=comment,
            raw_comment=raw_comment,
        )


def _try_decode(raw_str: Optional[bytes]) -> Tuple[Optional[str], Optional[bytes]]:
    if raw_str is None:
        return None, None

    try:
        return raw_str.decode('latin-1'), None
    except Exception:
        return None, raw_str


T = TypeVar('T')


def _as_enum(raw_value: int, enum: Type[T]) -> Union[T, int]:
    try:
        return enum(raw_value)
    except Exception:
        return raw_value


class BadGZipFileError(Exception):
    pass


class NotAGZipFileError(BadGZipFileError):
    def __init__(self, file_name: Optional[str]):
        quoted_name = f" '{file_name}'" if file_name is not None else ''
        super().__init__(f"File{quoted_name} is not a GZip file")


class GZipFileCorruptError(BadGZipFileError):
    def __init__(self, file_name: Optional[str]):
        quoted_name = f" '{file_name}'" if file_name is not None else ''
        super().__init__(f"GZip file{quoted_name} is corrupt or malformed")

