"""Exact UTC calendar labels, including local instants beyond datetime's bounds.

Python accepts a local year1..9999 and a UTC offset independently. Their UTC
label can consequently be in astronomical year0 or10000. Keep the integer
Gregorian ordinal and microseconds rather than clipping the physical instant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from fractions import Fraction
from zoneinfo import ZoneInfo

from fatebridge.utils.civil_clock import parse_iso_datetime

_DAY_MICROSECONDS = 86400 * 1000000

_ZERO_FRACTIONAL_OFFSET = re.compile(r"([+-])00(?::?00){0,2}[.,]([0-9]+)$")


def gregorian_ordinal(year: int, month: int, day: int) -> int:
    """Proleptic Gregorian ordinal, including auxiliary years0 and10000."""
    cycle, representative = divmod(year - 1, 400)
    return date(representative + 1, month, day).toordinal() + cycle * 146097


def gregorian_date_parts(ordinal: int) -> tuple[int, int, int]:
    """Invert the same Gregorian400-year calendar without datetime bounds."""
    cycle, remainder = divmod(ordinal - 1, 146097)
    representative = date.fromordinal(remainder + 1)
    return representative.year + cycle * 400, representative.month, representative.day


def _parse_calendar_isoformat(value: str) -> tuple[int, datetime]:
    """Parse ISO fields through a Gregorian-cycle representative when needed."""
    value = value[:-1] + "+00:00" if value.endswith("Z") else value
    extended = re.match(r"([+-]\d{6}|\d{4})(?=-)", value)
    if extended is not None:
        year = int(extended[1])
        if not 1 <= year <= 9999:
            proxy_year = 400 + year % 400
            proxy = parse_iso_datetime(f"{proxy_year:04d}" + value[extended.end() :])
            return year, proxy
    parsed = parse_iso_datetime(value)
    return parsed.year, parsed


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
        return gregorian_date_parts(self.ordinal)

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


@dataclass(frozen=True)
class ZonedCalendar:
    """An exact UTC label viewed through the selected civil-zone rules.

    Auxiliary year0/10000 labels need not fit Python datetime. Gregorian
    weekdays repeat after400years; IANA's initial offset and recurring future
    rules can therefore be queried through a representable calendar year.
    This is a timezone-model convention, not a prediction of future law.
    """

    utc: UTCCalendar
    zone: tzinfo = field(hash=False)

    @classmethod
    def from_datetime(cls, moment: datetime) -> ZonedCalendar:
        zone = moment.tzinfo
        if zone is None:
            raise ValueError("Civil-zone conversion requires an aware datetime")
        return cls(utc_calendar(moment), zone)

    @classmethod
    def from_isoformat(cls, value: str) -> ZonedCalendar:
        year, proxy = _parse_calendar_isoformat(value)
        result = cls.from_datetime(proxy)
        shift = gregorian_ordinal(year, proxy.month, proxy.day) - proxy.toordinal()
        return cls(
            UTCCalendar(result.utc.ordinal + shift, result.utc.microseconds_of_day),
            result.zone,
        )

    def _local_proxy(self) -> tuple[datetime, int]:
        year, month, day = self.utc.date_parts
        shift = 400 if year <= 1 else -400 if year >= 9999 else 0
        proxy = datetime(
            year + shift, month, day, *self.utc.time_parts, tzinfo=timezone.utc
        ).astimezone(self.zone)
        return proxy, shift

    @property
    def local_parts(self) -> tuple[int, int, int, int, int, int, int]:
        proxy, shift = self._local_proxy()
        return (
            proxy.year - shift,
            proxy.month,
            proxy.day,
            proxy.hour,
            proxy.minute,
            proxy.second,
            proxy.microsecond,
        )

    @property
    def local_ordinal(self) -> int:
        return gregorian_ordinal(*self.local_parts[:3])

    @property
    def offset(self) -> timedelta:
        proxy, _ = self._local_proxy()
        offset = proxy.utcoffset()
        if offset is None:
            raise ValueError("Civil-zone conversion requires a known UTC offset")
        return offset

    @property
    def fold(self) -> int:
        return self._local_proxy()[0].fold

    @property
    def timezone_label(self) -> str | None:
        if isinstance(self.zone, ZoneInfo):
            return self.zone.key
        return self._local_proxy()[0].tzname()

    def as_datetime(self) -> datetime | None:
        proxy, shift = self._local_proxy()
        year = proxy.year - shift
        return proxy.replace(year=year) if 1 <= year <= 9999 else None

    def require_datetime(self) -> datetime:
        moment = self.as_datetime()
        if moment is None:
            raise ValueError(
                "Civil calendar label is outside Python datetime's year range"
            )
        return moment

    def matches_wall_label(self, value: str) -> bool:
        year, proxy = _parse_calendar_isoformat(value)
        return self.local_parts == (
            year,
            proxy.month,
            proxy.day,
            proxy.hour,
            proxy.minute,
            proxy.second,
            proxy.microsecond,
        )

    def isoformat(self, *, sep: str = "T", include_offset: bool = True) -> str:
        proxy, shift = self._local_proxy()
        year = proxy.year - shift
        year_text = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
        display = proxy if include_offset else proxy.replace(tzinfo=None)
        return (
            f"{year_text}-{proxy.month:02d}-{proxy.day:02d}{sep}"
            + display.isoformat(sep=sep).split(sep, 1)[1]
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
