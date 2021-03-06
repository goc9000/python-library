"""
This module contains the `BinaryReader` class, a wrapper for binary I/O streams that offers functions for extracting
binary-encoded data such as ints, strings, structures etc.
"""

import struct

from typing import Union, BinaryIO, Optional, AnyStr, Iterable, Tuple
from io import BytesIO, IOBase, TextIOBase, UnsupportedOperation
from os import SEEK_SET, SEEK_CUR

from atmfjstc.lib.file_utils.fileobj import get_fileobj_size


class BinaryReader:
    """
    This class wraps a binary I/O file object and offers functions for extracting binary-encoded ints, strings,
    structures etc.

    Note that all the functions that encounter data different than what was expected will throw an exception from a
    subclass of `BinaryReaderFormatError`. This allows you to easily add specific processing for corrupted files vs
    other kinds of momentary or system errors.
    """

    _fileobj: BinaryIO
    _big_endian: bool

    _bytes_read: Optional[int] = 0
    _cached_total_size: Optional[int] = None
    _synthetic_eof: bool = False

    def __init__(self, data_or_fileobj: Union[bytes, BinaryIO], big_endian: bool):
        """
        Constructor.

        Args:
            data_or_fileobj: Either a `bytes` object, or a binary mode file object to read data from. For a file object,
                the data will be read starting from the file object's current position.
            big_endian: Set True to read ints and structures in big-endian mode, False to read them in little-endian.
                This setting can be overridden in individual calls if needed.

        Notes:
            - The passed in file object can be either seekable or non-seekable. For non-seekable streams, some of the
              functions of the `BinaryReader` will be unavailable, and others will run less efficiently.
            - You should avoid manipulating the file object in between calls to the `BinaryReader`. If you must,
              be aware that the reader does not automatically restore its last position, it will continue from where
              you left the stream before you called again.
        """

        self._fileobj = _parse_main_input_arg(data_or_fileobj)
        self._big_endian = big_endian

    def name(self) -> Optional[AnyStr]:
        name = getattr(self._fileobj, 'name', None)

        return None if ((name is None) or (name == '')) else name

    def seekable(self) -> bool:
        return self._fileobj.seekable()

    def _require_seekable(self):
        if not self.seekable():
            raise UnsupportedOperation("This operation can only be performed on seekable readers")

    def seek(self, offset: int, whence: type(SEEK_SET) = SEEK_SET) -> int:
        self._require_seekable()

        return self._fileobj.seek(offset, whence)

    def tell(self) -> int:
        """
        Reports the position of the reader in the binary data.

        Note that, as opposed to a regular file object, the `BinaryReader` can report the position even if the
        underlying stream is not seekable. In this case, the reported position represents the number of bytes read so
        far from the stream, by the `BinaryReader` itself.

        Returns:
            The position of the binary reader within the input, in bytes
        """
        return self._fileobj.tell() if self.seekable() else self._bytes_read

    def total_size(self) -> int:
        """
        Gets the total size of the data in the underlying file object (which must be seekeable).

        Returns:
            The size of the data, in bytes.
        """

        self._require_seekable()

        if self._cached_total_size is None:
            self._cached_total_size = get_fileobj_size(self._fileobj)

        return self._cached_total_size

    def bytes_remaining(self) -> int:
        """
        Gets the total size of the data remaining in the file object (from the current position to the end). The reader
        must be seekable for this.

        Returns:
            The size of the data, in bytes.
        """

        self._require_seekable()

        return self.total_size() - self.tell()

    def eof(self) -> bool:
        """
        Checks whether we are at the end of the data.

        If the stream is seekable, this function is always accurate. If not, this just returns a flag that is set when
        we attempt to read data in the past and ran against the end.

        Returns:
            True if no more data is available.
        """

        return (self.bytes_remaining() == 0) if self.seekable() else self._synthetic_eof

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

        data = b''

        while len(data) < n_bytes:
            new_data = self._fileobj.read(n_bytes - len(data))

            if len(new_data) == 0:
                self._synthetic_eof = True
                break

            self._bytes_read += len(new_data)

            if data == b'':
                data = new_data
            else:
                data += new_data

        return data

    def read_remainder(self) -> bytes:
        """
        Reads all the remaining data in the input.

        This is intended for use inside relatively small data structures of some bigger file, e.g. if the tail of a
        record in a TLV sequence represents some path or text string.

        Returns:
            The data, as a `bytes` object.
        """

        BUF_SIZE = 1000000

        data = b''

        while not self.eof():
            new_data = self.read_at_most(BUF_SIZE)
            if data == b'':
                data = new_data
            else:
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

        original_pos = self.tell()

        data = self.read_at_most(n_bytes)

        if len(data) == 0:
            raise BinaryReaderMissingDataError(original_pos, n_bytes, meaning)
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

    def peek(self, n_bytes: int) -> bytes:
        """
        Reads up to `n_bytes` of data without advancing the current position. Only for seekable inputs.

        Args:
            n_bytes: The number of bytes to read ahead.

        Returns:
            A byte string `n_bytes` in length, or less, if there is less data available.
        """

        self._require_seekable()

        data = self.read_at_most(n_bytes)
        self.seek(-len(data), SEEK_CUR)

        return data

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

        original_pos = self.tell()

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
            raise BinaryReaderWrongMagicError(self.tell() - len(magic), magic, data, meaning)

    def maybe_expect_magic(self, magic: bytes, meaning: Optional[str] = None) -> bool:
        """
        Like `expect_magic`, but returns False if there is no more data to be read.

        Note that other exceptions are still thrown if the magic is too short or doesn't match expectations.
        """
        try:
            self.expect_magic(magic, meaning)
            return True
        except BinaryReaderMissingDataError:
            return False

    def peek_magic(self, magic: bytes) -> bool:
        """
        Checks whether the following bytes match a given sequence, without advancind the read position.

        Only for seekable streams.

        Args:
            magic: A `bytes` object containing the expected sequence

        Returns:
            True if there is a match.
        """

        self._require_seekable()

        return self.peek(len(magic)) == magic

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

        original_pos = self.tell()

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

    def iter_tlv(
        self, type_bytes: int, length_bytes: int, meaning: Optional[str] = None, total_size: Optional[int] = None
    ) -> Iterable[Tuple[int, bytes]]:
        """
        Reads the incoming data as a sequence of TLV (Type-Length-Value) records. As the name implies, each record
        consists of an integer identifying the record Type, then an int indicating the length of the corresponding
        Value in bytes, and then the Value bytes themselves.

        Args:
            type_bytes: The size of the int denoting the Type, in bytes
            length_bytes: The size of the int denoting the Length, in bytes
            meaning: An indication as to the meaning of the data being read for a record (e.g. "header"). It is used in
                the text of any exceptions that may be thrown.
            total_size: The expected total size of the TLV records, so the reader knows when to stop, if there is other
                data after the TLV sequence. If this is None, the reader will continue to the end of the file.

        Returns:
            Yields (type, value) pairs for each incoming record.

        Raises:
            BinaryReaderReadPastEndError: If we read some bytes, but reached the end of the data before we got the
                full string.
            BinaryReaderMissingDataError: If we are at the end of the stream and no bytes are left at all.
        """

        tlv_meaning = f"{f'{meaning} ' if meaning is not None else ''}TLV"

        total_read = 0
        original_position = self.tell()

        while (total_size is None) or (total_read < total_size):
            tag = self.maybe_read_fixed_size_int(type_bytes, f"Type of {tlv_meaning} record")
            if tag is None:
                break

            length = self.read_fixed_size_int(length_bytes, f"Length of {tlv_meaning} record")
            value = self.read_amount(length, f"Value of {tlv_meaning} record")

            total_read += type_bytes + length_bytes + length

            yield tag, value

        if (total_size is not None) and (total_read > total_size):
            raise BinaryReaderReadPastEndError(original_position, total_size, total_read, f"{tlv_meaning} sequence")

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

    def read_uint8(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading an 8-bit unsigned integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(1, meaning or 'uint8', signed=False, big_endian=big_endian)

    def read_int8(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading an 8-bit signed integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(1, meaning or 'int8', signed=True, big_endian=big_endian)

    def maybe_read_uint8(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 8-bit unsigned integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(1, meaning or 'uint8', signed=False, big_endian=big_endian)

    def maybe_read_int8(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 8-bit signed integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(1, meaning or 'int8', signed=True, big_endian=big_endian)

    def read_uint16(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading a 16-bit unsigned integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(2, meaning or 'uint16', signed=False, big_endian=big_endian)

    def read_int16(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading a 16-bit signed integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(2, meaning or 'int8', signed=True, big_endian=big_endian)

    def maybe_read_uint16(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 16-bit unsigned integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(2, meaning or 'uint16', signed=False, big_endian=big_endian)

    def maybe_read_int16(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 16-bit signed integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(2, meaning or 'int16', signed=True, big_endian=big_endian)

    def read_uint32(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading a 32-bit unsigned integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(4, meaning or 'uint32', signed=False, big_endian=big_endian)

    def read_int32(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading a 32-bit signed integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(4, meaning or 'int32', signed=True, big_endian=big_endian)

    def maybe_read_uint32(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 32-bit unsigned integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(4, meaning or 'uint32', signed=False, big_endian=big_endian)

    def maybe_read_int32(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 32-bit signed integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(4, meaning or 'int32', signed=True, big_endian=big_endian)

    def read_uint64(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading a 64-bit unsigned integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(8, meaning or 'uint64', signed=False, big_endian=big_endian)

    def read_int64(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> int:
        """
        Convenient shortcut for reading a 64-bit signed integer. See `read_fixed_size_int`.
        """
        return self.read_fixed_size_int(8, meaning or 'int64', signed=True, big_endian=big_endian)

    def maybe_read_uint64(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 64-bit unsigned integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(8, meaning or 'uint64', signed=False, big_endian=big_endian)

    def maybe_read_int64(self, meaning: Optional[str] = None, big_endian: Optional[bool] = None) -> Optional[int]:
        """
        Convenient shortcut for reading an optional 64-bit signed integer. See `maybe_read_fixed_size_int`.
        """
        return self.maybe_read_fixed_size_int(8, meaning or 'int64', signed=True, big_endian=big_endian)


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
