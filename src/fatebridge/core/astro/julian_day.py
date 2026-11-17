"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from fractions import Fraction

from fatebridge.utils.civil_time import UTCCalendar, utc_calendar


def _utc_calendar_from_julian_day(
    day: Fraction, *, before: Fraction | None = None
) -> UTCCalendar:
    """Round an exact nominal Gregorian day within its qualified interval.

    The caller has already selected a supported ordinary clock interval.
    Its excluded endpoint must not acquire a different atomic offset through
    microsecond rounding. This calendar operation does not convert TT/UT1.
    """
    epoch = Fraction(4881175, 2)
    micros = round((day - epoch) * 86_400_000_000)
    if before is not None:
        micros = min(micros, math.ceil((before - epoch) * 86_400_000_000) - 1)
    days, remainder = divmod(micros, 86_400_000_000)
    return UTCCalendar(719163 + days, remainder)


def _datetime_from_julian_day(
    day: Fraction, *, before: Fraction | None = None
) -> datetime:
    calendar = _utc_calendar_from_julian_day(day, before=before)
    moment = calendar.as_datetime()
    if moment is None:
        raise ValueError("UTC calendar label is outside Python datetime's year range")
    return moment


def _julian_day(target: datetime) -> float:
    """UTC-like JD of an ISO/Python proleptic Gregorian datetime.

    Historical Julian civil dates must first be converted to Gregorian. Mixing
    calendar conventions here made natal and timing charts disagree
    by days before 1582. This is not a UTC-to-UT1 conversion (see chart profile).
    Naive internal datetimes retain the historical assumption of UTC.
    """
    calendar = utc_calendar(
        target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target
    )
    return _julian_day_from_calendar(calendar)


def _julian_day_from_calendar(calendar: UTCCalendar) -> float:
    """Retain the established scalar-JD arithmetic for an exact UTC label."""
    year, month, calendar_day = calendar.date_parts
    if not 1 <= year <= 9999:
        return calendar.julian_day()
    hour, minute, second, microsecond = calendar.time_parts
    day = (
        calendar_day
        + (hour + minute / 60.0 + (second + microsecond / 1_000_000.0) / 3600.0) / 24.0
    )

    if month <= 2:
        year -= 1
        month += 12

    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5
