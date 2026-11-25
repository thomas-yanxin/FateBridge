"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction

from fatebridge.utils.civil_time import CivilPoint, utc_calendar


def _datetime_from_julian_day(
    day: Fraction, *, before: Fraction | None = None
) -> datetime:
    calendar = CivilPoint(day, before).as_calendar()
    moment = calendar.as_datetime()
    if moment is None:
        raise ValueError("UTC calendar label is outside Python datetime's year range")
    else:
        pass
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
    return calendar.julian_day()
