"""
Utilities for handling ZIP "extra data" fields
"""

from typing import List, Dict, Callable

from atmfjstc.lib.binary_utils.BinaryReader import BinaryReader

from . import ZipExtraHeader, ZipExtraHeaderInterpretation, MalformedZipExtraDataError, ZXHZip64, ZXHPkWareNTFS, \
    ZXHPkWareUnix, ZXHNTSecurityDescriptor, ZXHExtendedTimestamps, ZXHInfoZipUnixV1, ZXHInfoZipUnicodeComment, \
    ZXHInfoZipUnicodePath, ZXHInfoZipUnixV2, ZXHInfoZipUnixV3, ZXHJARMarker


def parse_zip_extra_data(data: bytes, is_local: bool) -> List[ZipExtraHeader]:
    result = []

    reader = BinaryReader(data, big_endian=False)

    try:
        for header_id, value in reader.iter_tlv(type_bytes=2, length_bytes=2, meaning='ZIP extra headers'):
            result.append(_parse_header_from_tlv(header_id, value, is_local))
    except Exception as e:
        raise MalformedZipExtraDataError(
            f"Malformed binary data for ZIP {'local' if is_local else 'central'} extra field"
        ) from e

    return result


def _parse_header_from_tlv(header_id: int, data: bytes, is_local: bool) -> ZipExtraHeader:
    reader = BinaryReader(data, big_endian=False)

    parser = _PARSERS_BY_MAGIC.get(header_id)

    if parser is None:
        return ZipExtraHeader(
            magic=header_id,
            is_local=is_local,
            interpretation=None,
            warnings=(),
            unconsumed_data=reader.read_remainder()
        )

    warnings = []
    interpretation = parser(reader, is_local, warnings)

    unconsumed_data = None

    if not reader.eof():
        warnings.append("Header was not fully consumed")
        unconsumed_data = reader.read_remainder()

    return ZipExtraHeader(
        magic=header_id,
        is_local=is_local,
        interpretation=interpretation,
        warnings=tuple(warnings),
        unconsumed_data=unconsumed_data,
    )


_PARSERS_BY_MAGIC : Dict[int, Callable[[BinaryReader, bool, List[str]], ZipExtraHeaderInterpretation]] = {
    0x0001: ZXHZip64.parse,
    0x000a: ZXHPkWareNTFS.parse,
    0x000d: ZXHPkWareUnix.parse,
    0x4453: ZXHNTSecurityDescriptor.parse,
    0x5455: ZXHExtendedTimestamps.parse,
    0x5855: ZXHInfoZipUnixV1.parse,
    0x6375: ZXHInfoZipUnicodeComment.parse,
    0x7075: ZXHInfoZipUnicodePath.parse,
    0x7855: ZXHInfoZipUnixV2.parse,
    0x7875: ZXHInfoZipUnixV3.parse,
    0xcafe: ZXHJARMarker.parse,
}
