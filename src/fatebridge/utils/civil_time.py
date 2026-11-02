"""Exact UTC calendar labels, including local instants beyond datetime's bounds.

Python accepts a local year1..9999 and a UTC offset independently. Their UTC
label can consequently be in astronomical year0 or10000. Keep the integer
Gregorian ordinal and microseconds rather than clipping the physical instant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

_DAY_MICROSECONDS = 86400 * 1000000

_ZERO_FRACTIONAL_OFFSET = re.compile(r"([+-])00(?::?00){0,2}[.,]([0-9]+)$")


def datetime_fromisoformat_preserving_offset(value: str) -> datetime:
    """Restore fractional zero-whole-second offsets on affected CPython builds.

    CPython issue152079 can collapse these offsets to UTC. Keep the normal
    parser's grammar and naive-datetime behavior, restoring just that offset.
    """
    result = datetime.fromisoformat(value)
    match = _ZERO_FRACTIONAL_OFFSET.search(value)
    if match is not None and result.utcoffset() == timedelta(0):
        digits = match[2]
        if len(digits) > 6:
            raise ValueError("ISO UTC offset fractional seconds support at most6digits")
        micros = int(digits.ljust(6, "0")) * (-1 if match[1] == "-" else 1)
        result = result.replace(tzinfo=timezone(timedelta(microseconds=micros)))
    return result


@dataclass(frozen=True)
class UTCCalendar:
    ordinal: int
    microseconds_of_day: int

    @property
    def date_parts(self) -> tuple[int, int, int]:
        # Gregorian leap rules repeat exactly every400 years. The remainder
        # is representable by date even when the actual UTC year is not.
        cycle, remainder = divmod(self.ordinal - 1, 146097)
        representative = date.fromordinal(remainder + 1)
        return (
            representative.year + cycle * 400,
            representative.month,
            representative.day,
        )

    @property
    def time_parts(self) -> tuple[int, int, int, int]:
        seconds, microsecond = divmod(self.microseconds_of_day, 1000000)
        hour, remainder = divmod(seconds, 3600)
        minute, second = divmod(remainder, 60)
        return hour, minute, second, microsecond

    def as_datetime(self) -> datetime | None:
        year, month, day = self.date_parts
        if not 1 <= year <= 9999:
            return None
        return datetime(year, month, day, *self.time_parts, tzinfo=timezone.utc)

    def isoformat(self) -> str:
        normal = self.as_datetime()
        if normal is not None:
            return normal.isoformat()
        year, month, day = self.date_parts
        year_text = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
        hour, minute, second, microsecond = self.time_parts
        fraction = f".{microsecond:06d}" if microsecond else ""
        return (
            f"{year_text}-{month:02d}-{day:02d}T"
            f"{hour:02d}:{minute:02d}:{second:02d}{fraction}+00:00"
        )

    def julian_day(self) -> float:
        return float(
            Fraction(2 * self.ordinal + 3442849, 2)
            + Fraction(self.microseconds_of_day, _DAY_MICROSECONDS)
        )


def utc_calendar(moment: datetime) -> UTCCalendar:
    """Normalize an aware instant using integer arithmetic, without astimezone."""
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError("UTC calendar normalization requires an aware datetime")
    offset_us = (offset.days * 86400 + offset.seconds) * 1000000 + offset.microseconds
    local_us = (
        (moment.hour * 60 + moment.minute) * 60 + moment.second
    ) * 1000000 + moment.microsecond
    carry, utc_us = divmod(local_us - offset_us, _DAY_MICROSECONDS)
    return UTCCalendar(moment.toordinal() + carry, utc_us)


def utc_ordering_key(moment: datetime) -> tuple[int, int]:
    """Order physical instants without requiring a Python UTC datetime."""
    calendar = utc_calendar(moment)
    return calendar.ordinal, calendar.microseconds_of_day
