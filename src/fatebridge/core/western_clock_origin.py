"""Explicit midnight/noon hour labels, before timezone or solar-clock resolution.

Source day labels remain integers until the hour-origin carry is applied. This
also supports a valid final Gregorian date when the intermediate Julian source
date is outside datetime's Gregorian representation range.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fatebridge.core.civil_calendar import (
    GREGORIAN_ORDINAL_TO_JDN,
    _calendar_conversion_receipt,
    civil_date_jdn,
)

METHOD = "fatebridge.western_hour_origin.v1"
SOURCE = "https://wellcomecollection.org/works/s7z7c46y"


def event_wall_datetime(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    calendar: str = "proleptic_gregorian",
    hour_origin: str = "midnight",
) -> tuple[datetime, dict[str, Any], dict[str, Any]]:
    """Normalize an explicitly selected hour index to a midnight-based label.

    Noon hour0 is the date's12:00; hours12..23 are next-date00:00..11:00.
    This is nominal clock-label arithmetic, never elapsed physical duration,
    a timezone correction, automatic calendar reform or an inferred source.
    """
    if hour_origin not in {"midnight", "noon"}:
        raise ValueError("Unknown hour origin; select midnight or noon explicitly")
    if any(type(v) is not int for v in (hour, minute)):
        raise ValueError("Hour-origin clock parts must be integers")
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Hour-origin labels require hour0..23 and minute0..59")
    jdn = civil_date_jdn(year, month, day, calendar)
    noon = hour_origin == "noon"
    carry = int(noon and hour >= 12)
    normalized_hour = (hour + 12) % 24 if noon else hour
    raw_ordinal = jdn - GREGORIAN_ORDINAL_TO_JDN
    final_ordinal = raw_ordinal + carry
    if not 1 <= final_ordinal <= date.max.toordinal():
        raise ValueError(
            "Final hour-origin wall label lies outside Gregorian year1..9999"
        )
    final_date = date.fromordinal(final_ordinal)
    wall = datetime(
        final_date.year, final_date.month, final_date.day, normalized_hour, minute
    )
    raw_label = None
    if 1 <= raw_ordinal <= date.max.toordinal():
        raw_date = date.fromordinal(raw_ordinal)
        raw_label = datetime(raw_date.year, raw_date.month, raw_date.day, hour, minute)
    calendar_receipt = _calendar_conversion_receipt(
        year, month, day, hour, minute, calendar, jdn, raw_label
    )
    return (
        wall,
        calendar_receipt,
        {
            "method_id": METHOD,
            "input_hour_origin": hour_origin,
            "input_calendar": calendar,
            "input_date": {"year": year, "month": month, "day": day},
            "input_clock": {"hour": hour, "minute": minute},
            "source_date_label_jdn": jdn,
            "source_date_gregorian_representable": raw_label is not None,
            "calendar_normalized_label": raw_label.isoformat() if raw_label else None,
            "normalized_wall_calendar": "proleptic_gregorian",
            "normalized_wall_datetime": wall.isoformat(),
            "normalized_date_label_jdn": jdn + carry,
            "day_carry": carry,
            "nominal_label_shift_minutes": 720 if noon else 0,
            "normalization_performed": noon,
            "physical_duration_applied": False,
            "timezone_applied": False,
            "source_clock_identification_performed": False,
            "selection_source": "Declared request value or the API midnight default; source document clock origin not independently identified",
            "rule_source": (
                "William Lilly, Christian Astrology, London1647, pp30-31"
                if noon
                else "API midnight-based 24-hour clock convention"
            ),
            "rule_source_url": SOURCE if noon else None,
            "source_pages": [30, 31] if noon else [],
            "scope": "Selected ephemeris-table hour convention only, not every printed chart. Calendar day-label arithmetic and nominal day carry precede final Gregorian range validation; civil/LMT/LAT and timezone resolution follow. Not physical elapsed duration, a Julian-date epoch offset, regional reform, March25 year conversion, clock-accuracy or original-chart certification.",
        },
    )
