"""Expand reduced local-clock fractions before converting a cycle reference.

ISO8601 fractions apply to the lowest supplied local time unit. CPython's
fromisoformat accepts reduced fractions but interprets them as seconds instead.
Preserve its existing date, separator and offset compatibility; only repair the
hour/minute local-clock fraction. This is not a general ISO8601 implementation.
"""

import re
from datetime import date, datetime, timedelta

from fatebridge.core.human_design_reference_order import validate_reference_precision
from fatebridge.utils.civil_time import datetime_fromisoformat_preserving_offset

LEAP_REFERENCE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):60(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})"
)
_REDUCED_FRACTION = re.compile(
    r"(?P<date>[0-9]{4}(?:-[0-9]{2}-[0-9]{2}|[0-9]{4}|-W[0-9]{2}(?:-[0-9])?|W[0-9]{2}[0-9]?))"
    r"[\s\S](?P<clock>[0-9]{2}(?::?[0-9]{2})?)[.,](?P<fraction>[0-9]{1,6})"
    r"(?P<offset>Z|[+-][0-9]{2}(?::?[0-9]{2})?(?::?[0-9]{2})?(?:[.,][0-9]{1,6})?)?"
)


def _portable_base(match: re.Match) -> datetime:
    """Use Python3.10's complete form for the recognized reduced grammar."""
    calendar = match["date"].replace("-", "")
    if "W" in calendar:
        day = date.fromisocalendar(
            int(calendar[:4]), int(calendar[5:7]), int(calendar[7:] or "1")
        )
    else:
        day = date(int(calendar[:4]), int(calendar[4:6]), int(calendar[6:]))
    clock = match["clock"].replace(":", "")
    offset = match["offset"] or ""
    if offset == "Z":
        offset = "+00:00"
    elif offset:
        whole, dot, fraction = offset[1:].replace(",", ".").partition(".")
        whole = whole.replace(":", "").ljust(6, "0")
        offset = offset[0] + ":".join((whole[:2], whole[2:4], whole[4:]))
        if dot:
            offset += "." + fraction.ljust(6, "0")
    canonical = f"{day.isoformat()}T{clock[:2]}:{clock[2:] or '00'}:00{offset}"
    return datetime_fromisoformat_preserving_offset(canonical)


def reference_datetime(value: str) -> datetime:
    """Keep naive input naive and require the normal parser's valid grammar."""
    validate_reference_precision(value)
    match = _REDUCED_FRACTION.fullmatch(value)
    try:
        parsed = datetime_fromisoformat_preserving_offset(value.replace("Z", "+00:00"))
    except ValueError:
        if match is None:
            raise
        parsed = _portable_base(match)
    if match is None:
        return parsed
    digits = match["fraction"]
    unit_seconds = 3600 if len(match["clock"]) == 2 else 60
    # At most six digits means every expanded value is an integer microsecond.
    micros = int(digits) * unit_seconds * (10 ** (6 - len(digits)))
    return parsed.replace(microsecond=0) + timedelta(microseconds=micros)
