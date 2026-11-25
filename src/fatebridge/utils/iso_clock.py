"""ISO clock parsing independent of civil-zone resolution."""

import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Context, Decimal

_SUBSECOND_ZERO_OFFSET = re.compile(r"([+-])00(?::?00){0,2}[.,]([0-9]+)$")
_ISO_FRACTION = re.compile(
    r"(?:[0-9]{2}(?::?[0-9]{2}){0,2}[.,]"
    r"|[0-9]{6}(?=[0-9]{2})"
    r"|[0-9]{2}(?::[0-9]{2}){2}:)([0-9]+)"
)
_ASCII_DIGITS = re.compile(r"[0-9]*")
_OFFSET_SIGN = re.compile(r"[+-]")
_NINES_COMPLEMENT = str.maketrans("0123456789", "9876543210")
_REDUCED_WALL_FRACTION = re.compile(
    r"([0-9]{2})(?::?([0-9]{2}))?[.,]([0-9]+)(?=[+-]|$)"
)
_PORTABLE_ISO = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}[\s\S][0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.([0-9]+))?"
    r"(?:([+-][0-9]{2}:[0-9]{2})(?:(:[0-9]{2})(?:\.([0-9]+))?)?)?"
)


def parse_iso_datetime(value: str, *, portable: bool = True) -> datetime:
    """Restore fractional zero-second offsets lost by CPython gh-152079.

    Portable parsing normalizes those offsets to six fractional digits for
    Python 3.10. Native parsing retains the stdlib grammar and rejects excess
    offset digits when restoring an offset that the parser collapsed to UTC.
    """
    match = _SUBSECOND_ZERO_OFFSET.search(value)
    parser_value = value
    if portable and match is not None and match.start() > 10:
        parser_value = (
            value[: match.start()] + match[1] + "00:00:00." + match[2][:6].ljust(6, "0")
        )
    parsed = datetime.fromisoformat(parser_value)
    if match is not None and parsed.utcoffset() == timedelta(0):
        sign, fraction = match.groups()
        if not portable and len(fraction) > 6:
            raise ValueError("ISO UTC offset fractional seconds support at most6digits")
        microseconds = int(fraction[:6].ljust(6, "0"))
        if microseconds:
            offset = timedelta(
                microseconds=-microseconds if sign == "-" else microseconds
            )
            return parsed.replace(tzinfo=timezone(offset))
    return parsed


def _iso_date_end(value: str) -> int:
    """Locate the clock separator using the stdlib date layouts."""
    if value[4] == "-":
        if value[5] != "W":
            return 10
        # YYYY-Www-HH uses a dash separator after the reduced week date.
        return 10 if value[8:9] == "-" and not "0" <= value[10:11] <= "9" else 8
    if value[4] != "W":
        return 8
    # CPython resolves a digit separator in a basic week date by parity.
    digits = _ASCII_DIGITS.match(value, 7)
    assert digits is not None
    end = digits.end()
    if end < 9:
        return end
    return 7 if end % 2 == 0 else 8


def _fraction_digits(clock: str) -> str:
    # CPython also accepts some compact fractions without a decimal point.
    match = _ISO_FRACTION.match(clock)
    return match[1] if match is not None else ""


def parse_microsecond_iso_datetime(value: str) -> tuple[datetime, int]:
    """Parse an exact wall clock or return a UTC carry for offset input.

    In the aware case, subtract the parsed offset before applying the carry.
    Only the resulting instant needs to be an integral number of microseconds.
    A decimal wall-clock fraction applies to the last supplied time component.
    """
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    clock_start = _iso_date_end(value) + 1 if len(value) > 8 else len(value)
    # ISO 8601-1 §5.4.1 requires a complete date in a datetime. A week
    # without a weekday uses Python's legacy Monday and clock semantics.
    week_without_day = (
        clock_start == 8
        and value[4:5] == "W"
        or clock_start == 9
        and value[4:6] == "-W"
    )
    if not week_without_day and (
        reduced := _REDUCED_WALL_FRACTION.match(value, clock_start)
    ):
        hour, minute, digits = reduced.groups()
        unit_seconds = 3600 if minute is None else 60
        # Keep all scaled digits for the UTC grid calculation below.
        scaled = Context(prec=len(digits) + 4).multiply(
            Decimal("0." + digits), unit_seconds
        )
        whole, _, tail = format(scaled, "f").partition(".")
        whole_minutes, whole_seconds = divmod(int(whole), 60)
        wall = f"{hour}:{minute or f'{whole_minutes:02d}'}:{whole_seconds:02d}.{tail}"
        value = value[:clock_start] + wall + value[reduced.end() :]
    parser_value = value
    portable = _PORTABLE_ISO.fullmatch(value) if sys.version_info < (3, 11) else None
    if portable is not None:
        # Python 3.10 requires fixed-width fractions. Normalize only after
        # matching complete date, time and offset fields, and retain the tails.
        wall, fraction, hours_minutes, seconds, offset_fraction = portable.groups()
        parser_value = wall
        if fraction is not None:
            parser_value += "." + fraction[:6].ljust(6, "0")
        if hours_minutes is not None:
            parser_value += hours_minutes + (seconds or "")
        if offset_fraction is not None:
            parser_value += "." + offset_fraction[:6].ljust(6, "0")
    moment = parse_iso_datetime(parser_value)
    clock = value[clock_start:]
    offset = moment.utcoffset()
    if offset is None:
        if _fraction_digits(clock)[6:].rstrip("0"):
            raise ValueError("Local ISO clock must be representable to the microsecond")
        return moment, 0

    sign = _OFFSET_SIGN.search(clock)
    assert sign is not None
    wall_tail = _fraction_digits(clock[: sign.start()])[6:].rstrip("0")
    offset_digits = _fraction_digits(clock[sign.end() :])
    offset_tail = offset_digits[6:].rstrip("0")
    negative = sign[0] == "-"

    if not offset and offset_digits:
        # Recover the compact zero-second offset too.
        micros = int(offset_digits[:6].ljust(6, "0"))
        offset = timedelta(microseconds=-micros if negative else micros)
        moment = moment.replace(tzinfo=timezone(offset))

    # A positive offset's tail must cancel the wall tail. A negative
    # offset's tail must add to the wall tail to reach the next microsecond.
    carry = 0
    if negative and offset_tail:
        offset_tail = offset_tail[:-1].translate(_NINES_COMPLEMENT) + str(
            10 - int(offset_tail[-1])
        )
        carry = 1
    if wall_tail != offset_tail:
        raise ValueError("UTC instant must be representable to the microsecond")
    return moment, carry
