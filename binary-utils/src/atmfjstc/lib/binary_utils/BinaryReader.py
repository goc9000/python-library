"""
This module contains the `BinaryReader` class, a wrapper for binary I/O streams that offers functions for extracting
binary-encoded data such as ints, strings, structures etc.
"""

import struct

from typing import Union, BinaryIO, Optional, AnyStr
from io import BytesIO, IOBase, TextIOBase
from os import SEEK_SET, SEEK_CUR, SEEK_END


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

    def name(self) -> Optional[AnyStr]:
        name = getattr(self._fileobj, 'name', None)

        return None if ((name is None) or (name == '')) else name

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

    def read_at_most(self, n_bytes: int) -> bytes:
        """
        Try to read `n_bytes` of data, returning fewer only if the data is exhausted.

        Short reads, e.g. from a socket, are handled.

        Args:
            n_bytes: The number of bytes to try to read.

        Returns:
            The read data, at most `n_bytes` in length. Note that the function never raises a format error.
        """

        if n_bytes < 0:
            raise ValueError("The number of bytes to read cannot be negative")
        if n_bytes == 0:
            return b''

        data = self._fileobj.read(n_bytes)
        self._position += len(data)

        while len(data) < n_bytes:
            new_data = self._fileobj.read(n_bytes - len(data))

            if len(new_data) == 0:
                break

            self._position += len(new_data)
            data += new_data

        return data

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

        data = self.read_at_most(n_bytes)

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

    def skip_bytes(self, n_bytes: int, meaning: Optional[str] = None):
        """
        Skips over a number of bytes, ignoring the data. The bytes MUST be present.

        Args:
            n_bytes: The number of bytes to skip.
            meaning: An indication as to the meaning of the data being skipped (e.g. "compressed date"). It is used in
                the text of any exceptions that may be thrown.

        Raises:
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got the
                full length required.
        """

        if n_bytes < 0:
            raise ValueError("Number of bytes to skip must be non-negative")
        if n_bytes == 0:
            return

        original_pos = self._position

        if self.seekable():
            bytes_avail = self.bytes_remaining()
            if bytes_avail == 0:
                raise BinaryReaderMissingDataError(original_pos, n_bytes, meaning)
            if bytes_avail < n_bytes:
                self.seek(bytes_avail, SEEK_CUR)
                raise BinaryReaderReadPastEndError(original_pos, n_bytes, bytes_avail, meaning)

            self.seek(n_bytes, SEEK_CUR)
            return

        # Fall back to non-seeking algorithm

        BUF_SIZE = 1000000

        total_read = 0
        while total_read < n_bytes:
            to_read = min(BUF_SIZE, n_bytes - total_read)

            data = self.read_at_most(to_read)
            total_read += len(data)

            if len(data) < to_read:
                if total_read == 0:
                    raise BinaryReaderMissingDataError(original_pos, n_bytes, meaning)

                raise BinaryReaderReadPastEndError(original_pos, n_bytes, total_read, meaning)

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

    def read_null_terminated_bytes(
        self, meaning: Optional[str] = None, safety_limit: Optional[int] = 65536, buffer_size: int = 65536
    ) -> bytes:
        """
        Reads a null-terminated byte string from the file object.

        If the stream is seekable, this function will attempt to read the string in larger blocks and backtrack once
        it finds the null. Otherwise, it is reduced to reading it one byte at a time.

        Args:
            meaning: An indication as to the meaning of the data being read (e.g. "file name"). It is used in the text
                of any exceptions that may be thrown.
            safety_limit: The maximum expected size of the string, including the null terminator. The function will
                raise an exception if the null terminator is not found after that many bytes. This is intended to
                prevent trying to load huge files into memory if a null-terminated string is corrupt. Use None to
                disable this.
            buffer_size: The size of the chunks the string is read in, for a seekable stream. Use 0 here to force the
                string to be read byte by byte even if the stream is seekable.

        Returns:
            The byte string, as a `bytes` value, without the null terminator.

        Raises:
            BinaryReaderNullStrTooLong: Raised if the string is clearly longer than the `safety_limit`. Note that this
                is considered a format error.
            BinaryReaderNullStrReadPastEnd: Raised if we reached the end of the data without ever encountering the
                null terminator.
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
        """

        if (safety_limit is not None) and safety_limit < 1:
            raise ValueError(f"safety_limit must be strictly positive! (is: {safety_limit})")
        if buffer_size < 0:
            raise ValueError(f"buffer_size must be non-negative! (is: {buffer_size})")

        original_pos = self._position

        if (buffer_size < 1) or (not self.seekable()):
            buffer_size = 1

        data_parts = []
        total_length = 0

        while True:
            data = self.read_at_most(buffer_size)

            if len(data) == 0:
                if len(data_parts) == 0:
                    raise BinaryReaderMissingDataError(original_pos, 1, meaning or 'null-terminated string')

                raise BinaryReaderNullStrReadPastEndError(original_pos, meaning)

            null_pos = data.find(b'\x00')
            if null_pos != -1:
                data_parts.append(data[:null_pos])
                break

            data_parts.append(data)
            total_length += len(data)
            if (safety_limit is not None) and (total_length > safety_limit):
                break

        data = b''.join(data_parts)

        if (safety_limit is not None) and (total_length > safety_limit):
            raise BinaryReaderNullStrTooLongError(original_pos, safety_limit, meaning)

        if self.seekable() and (buffer_size > 1):
            self.seek(original_pos + len(data) + 1, SEEK_SET)

        return data

    def maybe_read_null_terminated_bytes(
        self, meaning: Optional[str] = None, safety_limit: Optional[int] = 65536, buffer_size: int = 65536
    ) -> Optional[bytes]:
        """
        Like `read_null_terminated_bytes`, but returns None if there is no more data to be read.

        Note that an exception is still thrown if there is *some* data available short of the required amount.
        """
        try:
            return self.read_null_terminated_bytes(meaning, safety_limit=safety_limit, buffer_size=buffer_size)
        except BinaryReaderMissingDataError:
            return None

    def read_length_prefixed_bytes(
        self, meaning: Optional[str] = None, length_bytes: int = 1, big_endian: Optional[bool] = None
    ) -> bytes:
        """
        Reads a byte string from the file object whose length is indicated by a fixed int occurring before it.

        Args:
            meaning: An indication as to the meaning of the data being read (e.g. "file name"). It is used in the text
                of any exceptions that may be thrown.
            length_bytes: The number of bytes over which the length is stored.
            big_endian: Use a non-None value here to override the `BinaryReader`'s current endianness setting, if
                necessary.

        Returns:
            The byte string, as a `bytes` value.

        Raises:
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got the
                full string.
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
        """

        length = self.read_fixed_size_int(
            n_bytes=length_bytes, meaning=f"length of {meaning or 'string'}", big_endian=big_endian
        )

        return self.read_amount(length, meaning=meaning)

    def maybe_read_length_prefixed_bytes(
        self, meaning: Optional[str] = None, length_bytes: int = 1, big_endian: Optional[bool] = None
    ) -> Optional[bytes]:
        """
        Like `read_length_prefixed_bytes`, but returns None if there is no more data to be read.

        Note that an exception is still thrown if there is *some* data available short of the required amount.
        """
        try:
            return self.read_length_prefixed_bytes(meaning, length_bytes=length_bytes, big_endian=big_endian)
        except BinaryReaderMissingDataError:
            return None

    def read_fixed_size_int(
        self, n_bytes: int, meaning: Optional[str] = None, signed: bool = False, big_endian: Optional[bool] = None
    ) -> int:
        """
        Reads an integer stored in a given number of bytes.

        Args:
            n_bytes: The number of bytes the int is stored over (e.g. a 32 bit int has 4 bytes). Must be at least 1.
            meaning: An indication as to the meaning of the data being read (e.g. "user ID"). It is used in the text
                of any exceptions that may be thrown.
            signed: Whether to interpret the integer as signed.
            big_endian: Use a non-None value here to override the `BinaryReader`'s current endianness setting, if
                necessary.

        Returns:
            The parsed integer.

        Raises:
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got a
                complete int.
        """

        if n_bytes < 1:
            raise ValueError("Number of bytes in int must be at least 1")

        big_endian = self._big_endian if big_endian is None else big_endian

        return int.from_bytes(
            self.read_amount(n_bytes, meaning=meaning or 'int'),
            byteorder='big' if big_endian else 'little',
            signed=signed
        )

    def maybe_read_fixed_size_int(
        self, n_bytes: int, meaning: Optional[str] = None, signed: bool = False, big_endian: Optional[bool] = None
    ) -> Optional[int]:
        """
        Like `read_fixed_size_int`, but returns None if there is no more data to be read.

        Note that an exception is still thrown if there is *some* data available short of the required amount.
        """
        try:
            return self.read_fixed_size_int(n_bytes, meaning=meaning, signed=signed, big_endian=big_endian)
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


class BinaryReaderNullStrReadPastEndError(BinaryReaderFormatError):
    position: int
    meaning: Optional[str]

    def __init__(self, position: int, meaning: Optional[str]):
        self.position = position
        self.meaning = meaning

        super().__init__(
            f"At position {position}, null-terminated string{f' for {meaning}' if meaning is not None else ''} "
            f"starts but end of the data occurs without the null terminator being found"
        )


class BinaryReaderNullStrTooLongError(BinaryReaderFormatError):
    position: int
    max_length: int
    meaning: Optional[str]

    def __init__(self, position: int, max_length: int, meaning: Optional[str]):
        self.position = position
        self.max_length = max_length
        self.meaning = meaning

        super().__init__(
            f"At position {position}, null-terminated string{f' for {meaning}' if meaning is not None else ''} "
            f"exceeds maximum length of {max_length}, possibly due to corrupt data"
        )
