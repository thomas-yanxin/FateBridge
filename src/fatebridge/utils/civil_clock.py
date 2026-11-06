"""Physical instant ordering and explicit-offset resolution of local clocks."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from dateutil import tz

from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

_OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})(?::(\d{2}))?$")
_SUBSECOND_ZERO_OFFSET = re.compile(r"([+-])00(?::?00){0,2}[.,]([0-9]+)$")


def parse_iso_datetime(value: str) -> datetime:
    """Preserve the UTC offset when reading an ISO datetime.

    CPython gh-152079 drops a fractional offset whose whole-second part is
    zero. Normalize that offset to six fractional digits for Python 3.10,
    validate with the stdlib parser, then restore the component from its text.
    Naive clocks retain their original parsing and timezone behavior.
    """
    match = _SUBSECOND_ZERO_OFFSET.search(value)
    parser_value = value
    if match is not None and match.start() > 10:
        parser_value = (
            value[: match.start()] + match[1] + "00:00:00." + match[2][:6].ljust(6, "0")
        )
    parsed = datetime.fromisoformat(parser_value)
    if parsed.utcoffset() == timedelta(0):
        if match is not None:
            sign, fraction = match.groups()
            # Match datetime's microsecond resolution and truncation policy.
            microseconds = int(fraction[:6].ljust(6, "0"))
            if microseconds:
                offset = timedelta(
                    microseconds=microseconds * (1 if sign == "+" else -1)
                )
                return parsed.replace(tzinfo=timezone(offset))
    return parsed


def utc_instant(moment: datetime) -> datetime:
    """Never compare same-zone wall labels when an actual instant is intended."""
    if moment.utcoffset() is None:
        raise ValueError("实际时刻比较必须带时区，不能默认服务器时区")
    return moment.astimezone(timezone.utc)


def format_utc_offset(offset: timedelta) -> str:
    """Format an actual offset, including IANA's historical offsets over 15h.

    Python requires a magnitude below 24h. The separate fixed-zone input
    policy is narrower; it must not reject an offset from a named zone.
    """
    seconds = offset.total_seconds()
    if not seconds.is_integer() or abs(seconds) >= 24 * 3600:
        raise ValueError("UTC偏移须为有效整秒且绝对值小于24小时")
    sign = "+" if seconds >= 0 else "-"
    hours, remainder = divmod(abs(int(seconds)), 3600)
    minutes, rest = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}" + (f":{rest:02d}" if rest else "")


def resolve_civil_clock(
    wall: datetime,
    zone: str,
    explicit_offset: Optional[str] = None,
    *,
    offset_field: str = "analysis_utc_offset",
    recorded_offset: Optional[str] = None,
) -> datetime:
    """Resolve a local label without inventing a side of a fold or a gap.

    The named zone remains the calendar zone. An offset only selects and
    verifies the actual instant, including historical offsets with seconds.
    """
    if wall.utcoffset() is not None:
        raise ValueError("本地钟表字段须为无时区标签，实际时刻另外明确偏移")
    if recorded_offset is not None:
        if explicit_offset is None:
            explicit_offset = recorded_offset
        elif explicit_offset != recorded_offset:
            requested = resolve_civil_clock(
                wall, zone, explicit_offset, offset_field=offset_field
            )
            recorded = resolve_civil_clock(
                wall, zone, recorded_offset, offset_field=offset_field
            )
            if utc_instant(requested) != utc_instant(recorded):
                raise ValueError(f"{offset_field}与已确认出生记录的UTC偏移选择冲突")
            return requested
    zone_info = parse_timezone_name(zone)
    local = wall.replace(tzinfo=zone_info)
    if explicit_offset is None:
        validate_local_clock(local)
        return local
    if type(explicit_offset) is not str:
        raise ValueError(f"{offset_field}须为±HH:MM或±HH:MM:SS")
    match = _OFFSET.fullmatch(explicit_offset.strip())
    if match is None:
        raise ValueError(f"{offset_field}须为±HH:MM或±HH:MM:SS")
    sign, hour, minute, second = match.groups()
    h, m, s = int(hour), int(minute), int(second or 0)
    if h >= 24 or m >= 60 or s >= 60:
        raise ValueError(f"{offset_field}超出有效UTC偏移范围")
    expected = timedelta(hours=h, minutes=m, seconds=s) * (1 if sign == "+" else -1)
    if not tz.datetime_exists(local):
        validate_local_clock(local)  # Keep the shared, non-retryable gap error.
    candidates: dict[datetime, datetime] = {}
    for fold in (0, 1):
        candidate = local.replace(fold=fold)
        if candidate.utcoffset() == expected:
            actual = utc_instant(candidate)
            roundtrip = actual.astimezone(zone_info)
            if roundtrip.replace(tzinfo=None) == wall:
                # UTC -> UTC can retain the synthetic fold=1 candidate even
                # though it is the same unambiguous instant as fold=0. Keep
                # the first canonical representation instead of relabelling it.
                candidates.setdefault(actual, roundtrip)
    if len(candidates) != 1:
        raise ValueError(f"{offset_field}与指定时区在该民用钟时的实际偏移不一致")
    return next(iter(candidates.values()))
