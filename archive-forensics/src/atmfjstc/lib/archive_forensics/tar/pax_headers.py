from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple, Union, Callable, Any

from atmfjstc.lib.iso_timestamp import iso_from_unix_time_string, ISOTimestamp
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID, INodeNo, PosixDeviceIDKDevTFormat
from atmfjstc.lib.os_forensics.generic import UserName, UserGroupName

from . import TarCharset


RawHeaders = Dict[str, str]


@dataclass(frozen=True)
class TarArchivePaxHeaders:
    """
    Data structure for storing interpreted TAR PAX headers that add extra information about the archive itself as
    opposed to the entries.

    Note that there are no such standard headers yet defined in the official spec, but other implementations such as
    `star` do feature some, e.g. `SCHILY.volhdr.*`. In any case, if any standard archive-level metadata is ever
    specified, it will likely use PAX headers for implementation.

    Also, "archive-level" and "global" are two different concepts, although archive-level headers will almost certainly
    have to be global headers.
    """


def parse_tar_archive_pax_headers(raw_headers: RawHeaders) -> Tuple[TarArchivePaxHeaders, RawHeaders]:
    return (
        TarArchivePaxHeaders(
            # No per-archive headers defined yet
        ),
        raw_headers.copy()
    )


@dataclass(frozen=True)
class TarArchiveEntryPaxHeaders:
    complete_path: Optional[str] = None
    complete_link_path: Optional[str] = None

    comment: Optional[str] = None

    file_size: Optional[int] = None

    mtime: Optional[ISOTimestamp] = None
    ctime: Optional[ISOTimestamp] = None
    atime: Optional[ISOTimestamp] = None
    creation_time: Optional[ISOTimestamp] = None

    owner_uid: Optional[PosixUID] = None
    owner_username: Optional[UserName] = None
    group_gid: Optional[PosixGID] = None
    group_name: Optional[UserGroupName] = None

    inode: Optional[INodeNo] = None
    host_device_kdev: Optional[PosixDeviceIDKDevTFormat] = None
    n_links: Optional[int] = None

    charset: Optional[Union[TarCharset, str]] = None
    header_charset: Optional[Union[TarCharset, str]] = None

    canceled_headers: Tuple[str, ...] = (),

    def apply_override(self, override: 'TarArchiveEntryPaxHeaders') -> 'TarArchiveEntryPaxHeaders':
        """
        Overrides these parsed headers with another set; this is intended for applying entry-level headers over any
        defaults set by global-level headers.

        Note that canceled headers are not processed here; they should be processed by the caller because they also
        effect values in the original entry data.
        """
        raw_data = asdict(self)
        raw_data.update({k: v for k, v in asdict(override).items() if v is not None})

        raw_data['charset'] = override.charset
        raw_data['header_charset'] = override.header_charset
        # canceled_headers will intentionally be taken 100% from the override

        return TarArchiveEntryPaxHeaders(**raw_data)


def parse_tar_entry_pax_headers(raw_headers: RawHeaders) -> Tuple[TarArchiveEntryPaxHeaders, RawHeaders]:
    unhandled, canceled_headers = _extract_canceled_headers(raw_headers)
    result = dict()

    if 'hdrcharset' in unhandled:
        raw_value = unhandled.pop('hdrcharset')
        # For now we just store the charset and assume the caller has already converted the headers to UTF-8. Could add
        # support for binary headers later
        result['header_charset'] = _parse_charset(raw_value) if raw_value != '' else TarCharset.UTF8

    for field in _FIELD_CONVERSIONS:
        raw_value = unhandled.pop(field.src, None)

        if raw_value is None:
            continue

        result[field.dest] = field.convert(raw_value)

    return (
        TarArchiveEntryPaxHeaders(
            **result,
            canceled_headers=canceled_headers,
        ),
        unhandled
    )


def parse_tar_archive_and_entry_pax_headers(
    raw_headers: RawHeaders
) -> Tuple[TarArchivePaxHeaders, TarArchiveEntryPaxHeaders, RawHeaders]:
    """
    Convenience function for extracting both archive-level and entry-level headers, useful particularly for handling
    the global headers, which contain both (entry-level headers there apply to all files).
    """
    archive_headers, unhandled = parse_tar_archive_pax_headers(raw_headers)
    entry_pax_headers, unhandled = parse_tar_entry_pax_headers(unhandled)

    return archive_headers, entry_pax_headers, unhandled


def _extract_canceled_headers(raw_headers: RawHeaders) -> Tuple[RawHeaders, Tuple[str, ...]]:
    return {k: v for k, v in raw_headers.items() if len(v) > 0}, tuple(k for k, v in raw_headers.items() if len(v) == 0)


def _parse_charset(raw: str) -> Optional[Union[TarCharset, str]]:
    try:
        return TarCharset(raw)
    except ValueError:
        return raw


@dataclass(frozen=True)
class _FieldSpec:
    dest: str
    src: str
    convert: Callable[[str], Any] = lambda v: v


_FIELD_CONVERSIONS = (
    _FieldSpec(dest='complete_path', src='path'),
    _FieldSpec(dest='complete_link_path', src='linkpath'),
    _FieldSpec(dest='comment', src='comment'),
    _FieldSpec(dest='file_size', src='size', convert=int),
    _FieldSpec(dest='mtime', src='mtime', convert=iso_from_unix_time_string),
    _FieldSpec(dest='ctime', src='ctime', convert=iso_from_unix_time_string),
    _FieldSpec(dest='atime', src='atime', convert=iso_from_unix_time_string),
    _FieldSpec(dest='owner_uid', src='uid', convert=lambda x: PosixUID(int(x))),
    _FieldSpec(dest='owner_username', src='uname', convert=UserName),
    _FieldSpec(dest='group_gid', src='gid', convert=lambda x: PosixGID(int(x))),
    _FieldSpec(dest='group_name', src='gname', convert=UserGroupName),
    _FieldSpec(dest='charset', src='charset', convert=_parse_charset),
    # SCHILY.* headers are added by the `star` program by Jörg Schilling
    _FieldSpec(dest='inode', src='SCHILY.ino', convert=lambda x: INodeNo(int(x))),
    _FieldSpec(dest='host_device_kdev', src='SCHILY.dev', convert=lambda x: PosixDeviceIDKDevTFormat(int(x))),
    _FieldSpec(dest='n_links', src='SCHILY.nlink', convert=int),
    # libarchive headers
    _FieldSpec(dest='creation_time', src='LIBARCHIVE.creationtime', convert=lambda x: iso_from_unix_time_string(x)),
)
