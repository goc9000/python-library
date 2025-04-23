"""
Utilities for handling ZIP "extra data" fields
"""

from typing import List, Optional, Dict, Type

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

    header_class = _get_header_class_for_magic(header_id)
    if header_class is None:
        return ZipExtraHeader(header_id, is_local, None, (), reader.read_remainder())

    warnings = []
    interpretation = header_class.parse(reader, is_local, warnings)

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


_cached_header_index: Optional[Dict[int, Type[ZipExtraHeaderInterpretation]]] = None


def _get_header_class_for_magic(magic: int) -> Optional[Type[ZipExtraHeaderInterpretation]]:
    global _cached_header_index

    if _cached_header_index is None:
        _cached_header_index = { header_class.magic: header_class for header_class in _ALL_HEADER_CLASSES }

    return _cached_header_index.get(magic)


_ALL_HEADER_CLASSES : List[Type[ZipExtraHeaderInterpretation]] = [
    ZXHZip64, ZXHPkWareNTFS, ZXHPkWareUnix, ZXHNTSecurityDescriptor, ZXHExtendedTimestamps, ZXHInfoZipUnixV1,
    ZXHInfoZipUnicodeComment, ZXHInfoZipUnicodePath, ZXHInfoZipUnixV2, ZXHInfoZipUnixV3, ZXHJARMarker
]
