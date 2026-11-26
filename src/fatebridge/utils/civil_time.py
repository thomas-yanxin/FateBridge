"""Exact UTC calendar labels, including local instants beyond datetime's bounds.

Python accepts a local year1..9999 and a UTC offset independently. Their UTC
label can consequently be in astronomical year0 or10000. Keep the integer
Gregorian ordinal and microseconds rather than clipping the physical instant.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from fractions import Fraction
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

from fatebridge.utils.iso_clock import (
    parse_iso_datetime,
    parse_microsecond_iso_datetime,
)

DAY_MICROSECONDS = 86400 * 1000000


def gregorian_ordinal(year: int, month: int, day: int) -> int:
    """Proleptic Gregorian ordinal, including auxiliary years0 and10000."""
    cycle, representative = divmod(year - 1, 400)
    return date(representative + 1, month, day).toordinal() + cycle * 146097


def gregorian_date_parts(ordinal: int) -> tuple[int, int, int]:
    """Invert the same Gregorian400-year calendar without datetime bounds."""
    cycle, remainder = divmod(ordinal - 1, 146097)
    representative = date.fromordinal(remainder + 1)
    return representative.year + cycle * 400, representative.month, representative.day


ClockTimespec = Literal["auto", "minutes", "seconds", "microseconds"]


def _wall_microseconds(moment: datetime) -> int:
    return (
        (moment.hour * 60 + moment.minute) * 60 + moment.second
    ) * 1000000 + moment.microsecond


def _time_parts(microseconds_of_day: int) -> tuple[int, int, int, int]:
    seconds, microsecond = divmod(microseconds_of_day, 1000000)
    hour, remainder = divmod(seconds, 3600)
    minute, second = divmod(remainder, 60)
    return hour, minute, second, microsecond


@dataclass(frozen=True)
class NominalClockLabel:
    """A zone-free clock label, never a second physical instant.

    Solar correction consumes the original timedelta quantization, then carries
    days with integer arithmetic. Auxiliary label years are Gregorian calendar
    coordinates; they do not extend any lunar table or ephemeris source domain.
    """

    ordinal: int
    microseconds_of_day: int

    @classmethod
    def from_local_datetime(cls, moment: datetime) -> NominalClockLabel:
        return cls(moment.toordinal(), _wall_microseconds(moment))

    def shifted(self, delta: timedelta) -> NominalClockLabel:
        delta_us = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
        carry, remainder = divmod(self.microseconds_of_day + delta_us, DAY_MICROSECONDS)
        return NominalClockLabel(self.ordinal + carry, remainder)

    @property
    def date_parts(self) -> tuple[int, int, int]:
        return gregorian_date_parts(self.ordinal)

    @property
    def time_parts(self) -> tuple[int, int, int, int]:
        return _time_parts(self.microseconds_of_day)

    def date_isoformat(self) -> str:
        year, month, day = self.date_parts
        year_text = f"{year:04d}" if 0 <= year <= 9999 else f"{year:+07d}"
        return f"{year_text}-{month:02d}-{day:02d}"

    def isoformat(self, *, sep: str = "T", timespec: ClockTimespec = "auto") -> str:
        hour, minute, second, microsecond = self.time_parts
        clock = f"{hour:02d}:{minute:02d}"
        if timespec != "minutes":
            clock += f":{second:02d}"
        if timespec == "microseconds" or (timespec == "auto" and microsecond):
            clock += f".{microsecond:06d}"
        return f"{self.date_isoformat()}{sep}{clock}"


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
    """Parse using the running Python version's ISO grammar."""
    return parse_iso_datetime(value, portable=False)


@dataclass(frozen=True, order=True)
class UTCCalendar:
    ordinal: int
    microseconds_of_day: int

    def shifted(self, delta: timedelta) -> UTCCalendar:
        label = NominalClockLabel(self.ordinal, self.microseconds_of_day).shifted(delta)
        return UTCCalendar(label.ordinal, label.microseconds_of_day)

    def elapsed_since(self, earlier: UTCCalendar) -> timedelta:
        """Subtract nominal UTC coordinates before any display conversion."""
        return timedelta(
            days=self.ordinal - earlier.ordinal,
            microseconds=self.microseconds_of_day - earlier.microseconds_of_day,
        )

    @property
    def date_parts(self) -> tuple[int, int, int]:
        # Gregorian leap rules repeat exactly every400 years. The remainder
        # is representable by date even when the actual UTC year is not.
        return gregorian_date_parts(self.ordinal)

    @property
    def time_parts(self) -> tuple[int, int, int, int]:
        return _time_parts(self.microseconds_of_day)

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

    def julian_day_exact(self) -> Fraction:
        """Nominal Gregorian day before scalar-JD rounding; not UTC quasi-JD."""
        return Fraction(2 * self.ordinal + 3442849, 2) + Fraction(
            self.microseconds_of_day, DAY_MICROSECONDS
        )

    def julian_day(self) -> float:
        return float(self.julian_day_exact())


class CivilFractionRecord(TypedDict):
    numerator: str
    denominator: str


class CivilPointRecord(TypedDict):
    unit: Literal["nominal_gregorian_day"]
    numerator: str
    denominator: str
    excluded_before: CivilFractionRecord | None


def nominal_calendar_bracket(day: Fraction) -> tuple[UTCCalendar, UTCCalendar]:
    """Enclose a nominal coordinate without assuming a clock-formatting cap.

    This is calendar arithmetic, not ordinary-clock qualification, a
    physical error interval or an actual rounded-wall event threshold.
    """
    epoch = Fraction(4881175, 2)
    micros = (day - epoch) * DAY_MICROSECONDS
    lower_days, lower_us = divmod(math.floor(micros), DAY_MICROSECONDS)
    upper_days, upper_us = divmod(math.ceil(micros), DAY_MICROSECONDS)
    return (
        UTCCalendar(719163 + lower_days, lower_us),
        UTCCalendar(719163 + upper_days, upper_us),
    )


@dataclass(frozen=True)
class CivilPoint:
    """An unrounded nominal Gregorian JD and its qualified formatting cap.

    This coordinate orders ordinary civil labels; it is neither a UTC
    quasi-JD nor a uniform SI duration. The clock owner selects the source
    domain. Before atomic UTC, its existing modeled UT1 convention applies.
    """

    day: Fraction
    excluded_before: Fraction | None = None

    def as_calendar(self) -> UTCCalendar:
        """Round within the ordinary interval already selected by the clock."""
        epoch = Fraction(4881175, 2)
        micros = round((self.day - epoch) * DAY_MICROSECONDS)
        if self.excluded_before is not None:
            micros = min(
                micros,
                math.ceil((self.excluded_before - epoch) * DAY_MICROSECONDS) - 1,
            )
        days, remainder = divmod(micros, DAY_MICROSECONDS)
        return UTCCalendar(719163 + days, remainder)

    def nominal_calendar_bracket(self) -> tuple[UTCCalendar, UTCCalendar]:
        """Return the pure nominal enclosure; the point's cap is not used."""
        return nominal_calendar_bracket(self.day)

    def to_record(self) -> CivilPointRecord:
        """Serialize exact integers as strings, including an explicit cap."""
        bound = self.excluded_before
        return {
            "unit": "nominal_gregorian_day",
            "numerator": str(self.day.numerator),
            "denominator": str(self.day.denominator),
            "excluded_before": (
                None
                if bound is None
                else {
                    "numerator": str(bound.numerator),
                    "denominator": str(bound.denominator),
                }
            ),
        }


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

    def utc_rule_proxy(self) -> tuple[datetime, int]:
        """Return the representable UTC input and its Gregorian year shift."""
        year, month, day = self.utc.date_parts
        shift = 400 if year <= 1 else -400 if year >= 9999 else 0
        proxy = datetime(
            year + shift, month, day, *self.utc.time_parts, tzinfo=timezone.utc
        )
        return proxy, shift

    def _local_proxy(self) -> tuple[datetime, int]:
        proxy, shift = self.utc_rule_proxy()
        return proxy.astimezone(self.zone), shift

    def rule_sample(self) -> datetime:
        """Read the loaded zone's offset and designation on its rule calendar."""
        return self._local_proxy()[0]

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
    carry, utc_us = divmod(_wall_microseconds(moment) - offset_us, DAY_MICROSECONDS)
    return UTCCalendar(moment.toordinal() + carry, utc_us)


def parse_civil_iso_clock(value: str) -> datetime | UTCCalendar:
    """Resolve an explicit offset on the extended UTC calendar."""
    moment, carry = parse_microsecond_iso_datetime(value)
    if moment.tzinfo is None:
        return moment
    calendar = utc_calendar(moment)
    return calendar.shifted(timedelta(microseconds=carry)) if carry else calendar


def utc_ordering_key(moment: datetime) -> tuple[int, int]:
    """Order physical instants without requiring a Python UTC datetime."""
    calendar = utc_calendar(moment)
    return calendar.ordinal, calendar.microseconds_of_day
