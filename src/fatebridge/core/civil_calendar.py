"""Explicit CE civil date labels, converted before timezone/time-scale handling.

This integer conversion does not reconstruct local mean/apparent time, choose
a country's reform date, or infer English March25 year numbering.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

CivilCalendar = Literal["proleptic_gregorian", "julian"]
GREGORIAN_ORDINAL_TO_JDN = 1721425


def civil_date_jdn(
    year: int, month: int, day: int, calendar: str = "proleptic_gregorian"
) -> int:
    """Validate a CE source date and retain its integer day label.

    A Julian source label can precede Python's first Gregorian date. Keep the
    integer until any explicitly declared clock-label day carry is applied.
    """
    if calendar not in {"proleptic_gregorian", "julian"}:
        raise ValueError("Unknown civil calendar")
    if any(type(v) is not int for v in (year, month, day)):
        raise ValueError("Civil date parts must be integers")
    if calendar == "proleptic_gregorian":
        return date(year, month, day).toordinal() + GREGORIAN_ORDINAL_TO_JDN
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ValueError("Julian calendar requires CE year1..9999 and month1..12")
    length = (31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if not 1 <= day <= length[month - 1]:
        raise ValueError("Invalid Julian calendar date")
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083


def gregorian_date(
    year: int, month: int, day: int, calendar: str = "proleptic_gregorian"
) -> date:
    """Map a valid selected calendar label to Python's proleptic Gregorian date."""
    ordinal = civil_date_jdn(year, month, day, calendar) - GREGORIAN_ORDINAL_TO_JDN
    if not 1 <= ordinal <= date.max.toordinal():
        raise ValueError("Converted date lies outside supported Gregorian year1..9999")
    return date.fromordinal(ordinal)


def civil_datetime(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    calendar: str = "proleptic_gregorian",
) -> tuple[datetime, dict[str, Any]]:
    """Preserve the supplied wall clock; timezone is applied by the chart builder."""
    converted = gregorian_date(year, month, day, calendar)
    if any(type(v) is not int for v in (hour, minute)):
        raise ValueError("Civil clock parts must be integers")
    moment = datetime(converted.year, converted.month, converted.day, hour, minute)
    return moment, _calendar_conversion_receipt(
        year,
        month,
        day,
        hour,
        minute,
        calendar,
        converted.toordinal() + GREGORIAN_ORDINAL_TO_JDN,
        moment,
    )


def _calendar_conversion_receipt(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    calendar: str,
    jdn: int,
    normalized_label: datetime | None,
) -> dict[str, Any]:
    """Date stage only; a raw hour label may still need origin normalization."""
    try:
        same_label = date(year, month, day)
    except ValueError:
        same_label = None
    return {
        "method_id": "explicit_ce_civil_calendar_integer_v1",
        "input_calendar": calendar,
        "input_date": {"year": year, "month": month, "day": day},
        "input_clock": {"hour": hour, "minute": minute},
        "normalized_calendar": "proleptic_gregorian",
        "normalized_local_datetime": (
            normalized_label.isoformat() if normalized_label else None
        ),
        "normalized_date_representable": normalized_label is not None,
        "normalized_local_datetime_scope": "Calendar-normalized date with the raw hour label preserved. Any declared hour origin is a separate step before timezone or solar-clock resolution; this is not a physical time-scale epoch.",
        "date_label_jdn": jdn,
        "date_label_jdn_scope": "Integer day label; not the chart's UTC/UT1/TT instant or a timezone-adjusted Julian day",
        "same_label_gregorian_date_valid": same_label is not None,
        "same_label_gregorian_offset_days": (
            None
            if same_label is None
            else jdn - same_label.toordinal() - GREGORIAN_ORDINAL_TO_JDN
        ),
        "calendar_conversion_performed": calendar == "julian",
        "clock_preserved": True,
        "automatic_regional_reform_applied": False,
        "year_numbering": "CE January1; no year0, BCE or March25 old-style year rollover inferred",
        "calendar_selection_source": "Declared request value or the API's proleptic Gregorian default; source document dating not independently verified",
        "timezone_order": "Convert date labels first, then validate and apply the supplied timezone to the normalized local clock",
        "historical_clock_reconstruction_performed": False,
        "scope": "Civil date-label conversion only; no LMT/LAT, historical clock, measured UT1 or original chart reconstruction certificate",
    }
