"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from datetime import datetime, timezone

from fatebridge.utils.civil_time import utc_calendar


def _julian_day(target: datetime) -> float:
    """UTC-like JD of an ISO/Python proleptic Gregorian datetime.

    Historical Julian civil dates must first be converted to Gregorian. Mixing
    calendar conventions here made natal and Kerykeion timing charts disagree
    by days before 1582. This is not a UTC-to-UT1 conversion (see chart profile).
    Naive internal datetimes retain the historical assumption of UTC.
    """
    if target.tzinfo is not None:
        try:
            target = target.astimezone(timezone.utc)
        except OverflowError:
            return utc_calendar(target).julian_day()
    year = target.year
    month = target.month
    day = (
        target.day
        + (
            target.hour
            + target.minute / 60.0
            + (target.second + target.microsecond / 1_000_000.0) / 3600.0
        )
        / 24.0
    )

    if month <= 2:
        year -= 1
        month += 12

    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5
