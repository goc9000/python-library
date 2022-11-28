"""
Utilities for working with timestamps stored as a ``yyyy-mm-dd hh:mm:ss[.ssss...][+hh:mm]`` string.

Pros and Cons of This Format
----------------------------

Advantages:

- Directly human-readable
- Can be stored as-is in JSON/XML/YAML/etc.-based formats
- Supports any level of precision with no loss of data due to the limitations of the int- or float-based storage of
  other timestamp formats.

  - Since is supports up to nanoseconds and beyond, it can represent any other contemporary timestamp

- Can be roughly compared directly. The comparison can be made completely accurate if both timestamps are brought to
  the same number of decimals and same timezone specification.

Disadvantages:

- Limited to the Gregorian calendar
- Only for contemporary dates (no B.C. etc.) and up to the year 9999
- Doesn't store minutiae such as leap second or DST status
- Needs conversion if operations are to be performed on it; it's intended more as a storage format rather than live use.

Details
-------

ISO timestamps are strings of the form::

    yyyy-mm-dd hh:mm:ss[.ssss...][+hh:mm]

where:

- ``yyyy-mm-dd hh:mm:ss`` is the mandatory part consisting of the year, month, day, hours, minutes and seconds
  respectively, all featuring leading zeros so as to always have the exact same width.
- ``.sssss...`` is an optional part where decimals can be added to the seconds part so as to specify the time down to
  the millisecond, nanosecond etc.

  - It is acceptable for the decimals part to feature trailing zeros
  - A timestamp is *canonical* if it features no trailing zeros here, and if the decimals part is completely absent
    when all the decimals would be zero.

- ``+hh:mm`` is an optional part denoting the timezone (with ``+00:00`` meaning UTC)

  - A timestamp is *aware* if it features a timezone
  - Otherwise a timestamp is *naive*, and might represent anything from local time, to an unknown timezone, or might
    be implicitly UTC. It is up to the caller to keep track of the semantics.
"""

__version__ = '1.1.2'


import re
import math

from datetime import datetime, timedelta, timezone
from typing import NewType, Tuple


ISOTimestamp = NewType('ISOTimestamp', str)


def iso_from_datetime(py_datetime: datetime) -> ISOTimestamp:
    """
    Converts from a Python `datetime` object.

    The resulting timestamp is aware or naive depending on whether the datetime object is so. It is always canonical.
    """
    base_ts = py_datetime.isoformat(sep=' ', timespec='seconds')
    decimals = f".{py_datetime.microsecond:06}".rstrip('0.')

    return ISOTimestamp(f"{base_ts[:19]}{decimals}{base_ts[19:]}")


def iso_to_datetime(iso_time: ISOTimestamp) -> datetime:
    """
    Converts to a Python `datetime` object.

    Beware! Since datetimes only have microsecond resolution, accuracy will be lost!

    The resulting datetime is aware or naive depending on whether the ISO time is so.
    """
    base_ts, decimals, tz_part = iso_timestamp_split(iso_time)

    if decimals != '':
        decimals = f"{decimals[:7]:0<7}"

    return datetime.fromisoformat(base_ts + decimals + tz_part)


def iso_from_unix_time(unix_time: float, precision: int = 9) -> ISOTimestamp:
    """
    Converts from a UNIX timestamp, which is defined as the (possibly floating-point) number of seconds since the UNIX
    epoch "1970-01-01 00:00:00 UTC".

    The resulting timestamp is always canonical, aware and referenced to UTC.

    Note that since, realistically, Unix timestamps are only recorded down to the nanosecond, this function takes only
    9 decimal digits into account by default. You can use the `precision` parameter to tweak this up to the full
    theoretical 15-16 decimal digits of precision a float can store.

    Negative UNIX timestamps are also accepted.
    """
    frac_part, int_part = math.modf(unix_time)

    seconds = int(int_part)

    if frac_part < 0:
        seconds -= 1
        frac_part += 1

    decimals = f"{{0:.{precision}f}}".format(frac_part)[1:].rstrip('0.')  # noqa

    return _from_unix_time(seconds, decimals)


def iso_from_unix_time_nanos(unix_time_nanos: int) -> ISOTimestamp:
    """
    Like `iso_from_unix_time`, but takes a UNIX time specified in an integral number of nanoseconds since the UNIX
    epoch, as is the case for the `stat` call in more modern POSIX systems.
    """
    seconds, nanos = divmod(unix_time_nanos, 1000000000)

    return _from_unix_time(seconds, f".{nanos:09}".rstrip('0.'))


def iso_from_unix_time_string(unix_time_str: str) -> ISOTimestamp:
    """
    Like `iso_from_unix_time`, but takes a UNIX time formatted as a string containing an integer or floating-point
    number. This ensures that all decimals present in the string are preserved.
    """

    m = re.fullmatch(r'(\d+)(\.\d*)?', unix_time_str)
    if m is None:
        raise ValueError(f"String is not a Unix timestamp: '{unix_time_str}'")

    return _from_unix_time(int(m.group(1)), (m.group(2) or '').rstrip('0.'))


def _from_unix_time(seconds: int, decimals: str) -> ISOTimestamp:
    base_datetime = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    base_ts = base_datetime.isoformat(sep=' ', timespec='seconds')

    return ISOTimestamp(f"{base_ts[:19]}{decimals}{base_ts[19:]}")


def iso_to_unix_time(iso_time: ISOTimestamp) -> float:
    """
    Converts to UNIX time, in float format.

    Note that this function does not check whether the resulting value fits any POSIX-specific limits.

    If the timestamp does not specify any timezone, it will be assumed to be relative to UTC.
    """
    base_ts, decimals, tz_part = iso_timestamp_split(iso_time)

    if tz_part == '':
        tz_part = '+00:00'

    return datetime.fromisoformat(base_ts + tz_part).timestamp() + (float(decimals) if decimals != '' else 0)


def iso_to_unix_time_nanos(iso_time: ISOTimestamp) -> int:
    """
    Converts to UNIX time, in integral nanoseconds format.

    Note that this function does not check whether the resulting value fits any POSIX-specific limits.

    If the timestamp does not specify any timezone, it will be assumed to be relative to UTC.
    """
    base_ts, decimals, tz_part = iso_timestamp_split(iso_time)

    if tz_part == '':
        tz_part = '+00:00'

    nanos = int(_decimals_to_precision(decimals, 9, True)[1:])

    return int(datetime.fromisoformat(base_ts + tz_part).timestamp()) * 1000000000 + nanos


def iso_fix_precision(iso_time: ISOTimestamp, precision: int, truncate: bool = False) -> ISOTimestamp:
    """
    Returns a variant of an ISO timestamp with a fixed number of decimals.

    If the decimals actually stored by the timestamp do not fit in the new width, they will either be silently
    truncated (if `truncate` is True), or a `ValueError` will be raised (if False).
    """
    base_ts, decimals, tz_part = iso_timestamp_split(iso_time)

    return ISOTimestamp(base_ts + _decimals_to_precision(decimals, precision, truncate) + tz_part)


def _decimals_to_precision(decimals: str, precision: int, truncate: bool) -> str:
    decimals = decimals.rstrip('0.')

    final_length = (1 + precision) if precision > 0 else 0

    if len(decimals) > final_length:
        if not truncate:
            raise ValueError(f"ISO timestamp would lose precision with {precision} decimals")

        decimals = decimals[:final_length]

    if final_length > 0:
        if decimals == '':
            decimals = '.'

        decimals += '0' * (final_length - len(decimals))

    return decimals


def iso_canonical(iso_time: ISOTimestamp) -> ISOTimestamp:
    """
    Returns the variant of an ISO timestamp (i.e. with all trailing zero decimals removed).
    """
    base_ts, decimals, tz_part = iso_timestamp_split(iso_time)

    return ISOTimestamp(base_ts + decimals.rstrip('0.') + tz_part)


def iso_timestamp_split(iso_time: ISOTimestamp) -> Tuple[str, str, str]:
    """
    Splits an ISO timestamp into its three components (date, decimal part, timezone).

    Missing components will be rendered as empty strings. Concatenating the three strings in the result yields the
    original timestamp.
    """
    m = re.match(r'^(.{19})((?:\.\d+)?)(.*)$', iso_time)

    return m.group(1), m.group(2), m.group(3)
