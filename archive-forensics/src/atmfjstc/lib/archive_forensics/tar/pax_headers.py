from dataclasses import dataclass, asdict, replace
from typing import Dict, Optional, Tuple, Union, Callable, Any, Iterable

from atmfjstc.lib.iso_timestamp import iso_from_unix_time_string, ISOTimestamp
from atmfjstc.lib.os_forensics.posix import PosixUID, PosixGID, INodeNo, PosixDeviceIDKDevTFormat
from atmfjstc.lib.os_forensics.generic import UserName, UserGroupName

from . import TarCharset


RawHeaders = Dict[str, str]


@dataclass(frozen=True)
class TarEntryFields:
    """
    Data structure for storing known metadata fields in a TAR entry, or an assignment thereof. It is meant for helping
    with computing the final result of headers overriding one another (e.g. local entry extended headers override
    global headers, which override standard TAR headers etc)
    """
    path: Optional[str] = None
    link_path: Optional[str] = None

    comment: Optional[str] = None

    content_size: Optional[int] = None
    content_charset: Optional[Union[TarCharset, str]] = None

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

    def apply_override(self, override: 'TarEntryFields') -> 'TarEntryFields':
        raw_data = asdict(self)
        raw_data.update({k: v for k, v in asdict(override).items() if v is not None})

        return TarEntryFields(**raw_data)

    def clear_fields(self, fields: Iterable[str]) -> 'TarEntryFields':
        return replace(self, **{field: None for field in fields})


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
    entry_fields: TarEntryFields
    cleared_fields: Tuple[str, ...] = (),
    header_charset: Optional[Union[TarCharset, str]] = None

    def apply_to_entry(self, tar_entry: TarEntryFields) -> TarEntryFields:
        return tar_entry.apply_override(self.entry_fields).clear_fields(self.cleared_fields)


def parse_tar_entry_pax_headers(raw_headers: RawHeaders) -> Tuple[TarArchiveEntryPaxHeaders, RawHeaders]:
    unhandled = raw_headers.copy()

    set_fields = dict()
    cleared_fields = []

    header_charset = None
    if 'hdrcharset' in unhandled:
        raw_value = unhandled.pop('hdrcharset')
        # For now we just store the charset and assume the caller has already converted the headers to UTF-8. Could add
        # support for binary headers later
        header_charset = _parse_charset(raw_value) if raw_value != '' else TarCharset.UTF8

    for field in _ENTRY_FIELD_CONVERSIONS:
        raw_value = unhandled.pop(field.src, None)

        if raw_value is None:
            continue
        elif raw_value == '':
            cleared_fields.append(field.dest)
            continue

        set_fields[field.dest] = field.convert(raw_value)

    return (
        TarArchiveEntryPaxHeaders(
            entry_fields=TarEntryFields(**set_fields),
            cleared_fields=tuple(cleared_fields),
            header_charset=header_charset,
        ),
        unhandled
    )


def parse_tar_global_pax_headers(
    raw_headers: RawHeaders
) -> Tuple[TarArchivePaxHeaders, TarArchiveEntryPaxHeaders, RawHeaders]:
    """
    Convenience function for extracting both archive-level and entry-level headers from global PAX headers. The
    entry-level headers apply to all files in the archive.
    """
    archive_headers, unhandled = parse_tar_archive_pax_headers(raw_headers)
    entry_pax_headers, unhandled = parse_tar_entry_pax_headers(unhandled)

    return archive_headers, entry_pax_headers, unhandled


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


_ENTRY_FIELD_CONVERSIONS = (
    _FieldSpec(dest='path', src='path'),
    _FieldSpec(dest='link_path', src='linkpath'),
    _FieldSpec(dest='comment', src='comment'),
    _FieldSpec(dest='content_size', src='size', convert=int),
    _FieldSpec(dest='content_charset', src='charset', convert=_parse_charset),
    _FieldSpec(dest='mtime', src='mtime', convert=iso_from_unix_time_string),
    _FieldSpec(dest='ctime', src='ctime', convert=iso_from_unix_time_string),
    _FieldSpec(dest='atime', src='atime', convert=iso_from_unix_time_string),
    _FieldSpec(dest='owner_uid', src='uid', convert=lambda x: PosixUID(int(x))),
    _FieldSpec(dest='owner_username', src='uname', convert=UserName),
    _FieldSpec(dest='group_gid', src='gid', convert=lambda x: PosixGID(int(x))),
    _FieldSpec(dest='group_name', src='gname', convert=UserGroupName),
    # SCHILY.* headers are added by the `star` program by Jörg Schilling
    _FieldSpec(dest='inode', src='SCHILY.ino', convert=lambda x: INodeNo(int(x))),
    _FieldSpec(dest='host_device_kdev', src='SCHILY.dev', convert=lambda x: PosixDeviceIDKDevTFormat(int(x))),
    _FieldSpec(dest='n_links', src='SCHILY.nlink', convert=int),
    # libarchive headers
    _FieldSpec(dest='creation_time', src='LIBARCHIVE.creationtime', convert=lambda x: iso_from_unix_time_string(x)),
)
