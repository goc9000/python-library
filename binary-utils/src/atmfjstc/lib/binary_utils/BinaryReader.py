"""
This module contains the `BinaryReader` class, a wrapper for binary I/O streams that offers functions for extracting
binary-encoded data such as ints, strings, structures etc.
"""

import struct

from typing import Union, BinaryIO, Optional
from io import BytesIO, IOBase, TextIOBase
from os import SEEK_SET, SEEK_END


class BinaryReader:
    """
    This class wraps a binary I/O file object and offers functions for extracting binary-encoded ints, strings,
    structures etc.
    """

    _fileobj: BinaryIO
    _big_endian: bool

    _position: int
    _cached_total_size: Optional[int] = None

    def __init__(self, data_or_fileobj: Union[bytes, BinaryIO], big_endian: bool):
        self._fileobj = _parse_main_input_arg(data_or_fileobj)
        self._big_endian = big_endian

        self._position = self._fileobj.tell() if self._fileobj.seekable() else 0

    def seekable(self) -> bool:
        return self._fileobj.seekable()

    def _require_seekable(self):
        if not self.seekable():
            raise ValueError("This operation can only be performed on seekable readers")

    def seek(self, offset: int, whence: type(SEEK_SET)) -> 'BinaryReader':
        self._require_seekable()

        self._fileobj.seek(offset, whence)
        self._position = self._fileobj.tell()

        return self

    def tell(self) -> int:
        return self._position

    def total_size(self) -> int:
        self._require_seekable()

        if self._cached_total_size is None:
            original_position = self._fileobj.tell()
            self._fileobj.seek(0, SEEK_END)
            self._cached_total_size = self._fileobj.tell()
            self._fileobj.seek(original_position, SEEK_SET)

        return self._cached_total_size

    def bytes_remaining(self) -> int:
        self._require_seekable()

        return self.total_size() - self._position

    def read_amount(self, n_bytes: int, meaning: Optional[str] = None) -> bytes:
        """
        Reads exactly `n_bytes` from the underlying stream.

        Args:
            n_bytes: The amount of bytes to read.
            meaning: An indication as to the meaning of the data being read (e.g. "user ID"). It is used in the text
                of any exceptions that may be thrown.

        Returns:
            The data, as a `bytes` object `n_bytes` in length.

        Raises:
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got the
                full `n_bytes`.
        """

        if n_bytes == 0:
            return b''

        original_pos = self._position

        data = self._fileobj.read(n_bytes)
        self._position += len(data)

        if len(data) == 0:
            raise BinaryReaderMissingDataError(self._position, n_bytes, meaning)
        if len(data) < n_bytes:
            raise BinaryReaderReadPastEndError(original_pos, n_bytes, len(data), meaning)

        return data

    def maybe_read_amount(self, n_bytes: int, meaning: Optional[str] = None) -> Optional[bytes]:
        """
        Like `read_amount`, but returns None if there is no more data to be read.

        Note that an exception is still thrown if there is *some* data available short of the required amount.
        """
        try:
            return self.read_amount(n_bytes, meaning)
        except BinaryReaderMissingDataError:
            return None

    def expect_magic(self, magic: bytes, meaning: Optional[str] = None):
        """
        Verifies that a specific bytes sequence ("magic") follows in the underlying stream.

        This is often used to validate that a file is of the correct type.

        Args:
            magic: A `bytes` object containing the expected sequence
            meaning: An indication as to the meaning of the data being read (e.g. "ZIP signature"). It is used in the
                text of any exceptions that may be thrown.

        Raises:
            BinaryReaderWrongMagicError: If the read sequence does not match the expected one.
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got the
                full length of the magic.
        """

        meaning = meaning or "magic"

        data = self.read_amount(len(magic), meaning)

        if data != magic:
            raise BinaryReaderWrongMagicError(self._position - len(magic), magic, data, meaning)

    def maybe_expect_magic(self, magic: bytes, meaning: Optional[str] = None) -> bool:
        """
        Like `expect_magic`, but returns None if there is no more data to be read.

        Note that other exceptions are still thrown if the magic is too short or doesn't match expectations.
        """
        try:
            self.expect_magic(magic, meaning)
            return True
        except BinaryReaderMissingDataError:
            return False

    def read_struct(self, struct_format: str, meaning: Optional[str] = None) -> tuple:
        """
        Reads structured data from the underlying stream.

        Args:
            struct_format: The format of the structured data, as per the Python `struct` package. There is no need to
                prepend an endianness specifier, as one will be added automatically in accordance to the
                `BinaryReader`'s current setting, but if one is present, it will take precedence.
            meaning: An indication as to the meaning of the data being read (e.g. "file header"). It is used in the
                text of any exceptions that may be thrown.

        Returns:
           The data in the structure, as a tuple.

        Raises:
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got a
                complete structure.
        """

        if struct_format == '':
            return ()
        if struct_format[0] not in '@=<>!':
            struct_format = ('>' if self._big_endian else '<') + struct_format

        meaning = meaning or f"struct ({struct_format})"

        data = self.read_amount(struct.calcsize(struct_format), meaning)

        return struct.unpack(struct_format, data)

    def maybe_read_struct(self, struct_format: str, meaning: Optional[str] = None) -> Optional[tuple]:
        """
        Like `read_struct`, but returns None if there is no more data to be read.

        Note that an exception is still thrown if there is *some* data available short of the required amount.
        """
        try:
            return self.read_struct(struct_format, meaning)
        except BinaryReaderMissingDataError:
            return None


def _parse_main_input_arg(input_: Union[bytes, BinaryIO]) -> BinaryIO:
    if isinstance(input_, bytes):
        return BytesIO(input_)

    if not isinstance(input_, IOBase):
        raise TypeError("Input to BinaryReader must be either bytes or a file object")
    if isinstance(input_, TextIOBase):
        raise TypeError("BinaryReader works on binary, not text file objects")

    return input_


class BinaryReaderFormatError(Exception):
    """
    This is used by the `BinaryReader` specifically to signal situations where the data does not match the expected
    format.
    """


class BinaryReaderReadPastEndError(BinaryReaderFormatError):
    position: int
    expected_length: int
    actual_length: int
    meaning: Optional[str]

    def __init__(self, position: int, expected_length: int, actual_length: int, meaning: Optional[str]):
        self.position = position
        self.expected_length = expected_length
        self.actual_length = actual_length
        self.meaning = meaning

        super().__init__(
            f"At position {position}, expected {expected_length} "
            f"bytes{f' for {meaning}' if meaning is not None else ''}"
            f", but only {actual_length} were found"
        )


class BinaryReaderMissingDataError(BinaryReaderFormatError):
    position: int
    expected_length: int
    meaning: Optional[str]

    def __init__(self, position: int, expected_length: int, meaning: Optional[str]):
        self.position = position
        self.expected_length = expected_length
        self.meaning = meaning

        super().__init__(
            f"At position {position}, expected {expected_length} "
            f"bytes{f' for {meaning}' if meaning is not None else ''}"
            f", but the data ends"
        )


class BinaryReaderWrongMagicError(BinaryReaderFormatError):
    position: int
    expected_magic: bytes
    found_magic: bytes
    meaning: Optional[str]

    def __init__(self, position: int, expected_magic: bytes, found_magic: bytes, meaning: Optional[str]):
        self.position = position
        self.expected_magic = expected_magic
        self.found_magic = found_magic
        self.meaning = meaning

        super().__init__(
            f"At position {position}, expected {meaning or 'magic'} 0x{expected_magic.hex()}, but found "
            f"0x{found_magic.hex()}"
        )
