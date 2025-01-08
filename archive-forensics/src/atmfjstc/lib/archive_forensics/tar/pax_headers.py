from dataclasses import dataclass, field, replace, asdict
from typing import Dict, Optional, Tuple, Union

from atmfjstc.lib.py_lang_utils.convert_struct import make_struct_converter
from atmfjstc.lib.iso_timestamp import iso_from_unix_time_string, ISOTimestamp
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID, INodeNo, PosixDeviceIDKDevTFormat
from atmfjstc.lib.os_forensics.generic import UserName, UserGroupName

from . import TarCharset


@dataclass(frozen=True)
class TarArchivePaxHeaders:
    """
    Data structure for storing interpreted TAR PAX headers that add extra information about the archive itself as
    opposed to the entries.

    Note that there are no such headers yet defined in the official spec, but if any extra archive-level metadata is
    ever specified, it will likely use PAX headers for implementation.

    Also, "archive-level" and "global" are two different concepts, although archive-level headers will almost certainly
    have to be global headers.
    """
    canceled_headers: Tuple[str, ...] = (),
    unhandled_headers: Dict[str, str] = field(default_factory=dict)


def parse_tar_archive_pax_headers(raw_headers: Dict[str, str]) -> TarArchivePaxHeaders:
    raw_headers, canceled_headers = _extract_canceled_headers(raw_headers)

    return TarArchivePaxHeaders(
        # No per-archive headers defined yet
        canceled_headers=canceled_headers,
        unhandled_headers=raw_headers,
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
    unhandled_headers: Dict[str, str] = field(default_factory=dict)

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
        # canceled_headers and unhandled_headers will intentionally be taken 100% from the override

        return TarArchiveEntryPaxHeaders(**raw_data)


def parse_tar_entry_pax_headers(raw_headers: Dict[str, str]) -> TarArchiveEntryPaxHeaders:
    raw_headers, canceled_headers = _extract_canceled_headers(raw_headers)

    result, unhandled = _convert_entry_headers(raw_headers)

    return TarArchiveEntryPaxHeaders(
        **result,
        canceled_headers=canceled_headers,
        unhandled_headers=unhandled,
    )


def parse_tar_archive_and_entry_pax_headers(
    raw_headers: Dict[str, str]
) -> Tuple[TarArchivePaxHeaders, TarArchiveEntryPaxHeaders]:
    """
    Convenience function for extracting both archive-level and entry-level headers, useful particularly for handling
    the global headers, which contain both (entry-level headers there apply to all files).
    """
    archive_headers = parse_tar_archive_pax_headers(raw_headers)
    entry_pax_headers = parse_tar_entry_pax_headers(archive_headers.unhandled_headers)

    archive_headers = replace(archive_headers, unhandled_headers=entry_pax_headers.unhandled_headers)

    return archive_headers, entry_pax_headers


def _extract_canceled_headers(raw_headers: Dict[str, str]) -> Tuple[Dict[str, str], Tuple[str, ...]]:
    return {k: v for k, v in raw_headers.items() if len(v) > 0}, tuple(k for k, v in raw_headers.items() if len(v) == 0)


def _parse_charset(raw: str) -> Optional[Union[TarCharset, str]]:
    try:
        return TarCharset(raw)
    except ValueError:
        return raw


_convert_entry_headers = make_struct_converter(
    source_type='dict',
    dest_type='dict',
    fields=dict(
        complete_path=dict(src='path'),
        complete_link_path=dict(src='linkpath'),
        comment=True,
        file_size=dict(src='size', convert=int),
        mtime=dict(convert=iso_from_unix_time_string),
        ctime=dict(convert=iso_from_unix_time_string),
        atime=dict(convert=iso_from_unix_time_string),
        owner_uid=dict(src='uid', convert=lambda x: PosixUID(int(x))),
        owner_username=dict(src='uname', convert=UserName),
        group_gid=dict(src='gid', convert=lambda x: PosixGID(int(x))),
        group_name=dict(src='gname', convert=UserGroupName),
        charset=dict(src='charset', convert=_parse_charset),
        header_charset=dict(src='hdrcharset', convert=_parse_charset),
        # SCHILY.* headers are added by the `star` program by Jörg Schilling
        inode=dict(src='SCHILY.ino', convert=lambda x: INodeNo(int(x))),
        host_device_kdev=dict(src='SCHILY.dev', convert=lambda x: PosixDeviceIDKDevTFormat(int(x))),
        n_links=dict(src='SCHILY.nlink', convert=int),
        # libarchive headers
        creation_time=dict(src='LIBARCHIVE.creationtime', convert=lambda x: iso_from_unix_time_string(x)),
    ),
    return_unparsed=True,
)
