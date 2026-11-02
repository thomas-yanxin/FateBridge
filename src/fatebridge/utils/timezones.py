"""Shared timezone parsing for input normalization and calendar calculations."""

import hashlib
import re
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from functools import lru_cache
from io import BytesIO
from typing import cast
from zoneinfo import ZoneInfo

import pytz
from dateutil import tz
from pydantic_core import PydanticCustomError

from fatebridge.utils.errors import UNRESOLVED_OFFSET_MESSAGE, EphemerisSourceError
from fatebridge.utils.tzif_transitions import explicit_transition_seconds

_OFFSET = re.compile(r"^(?:UTC|GMT)?([+-]?)(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)
_SECOND_OFFSET = re.compile(
    r"^(?:UTC|GMT)?([+-]?)(\d{1,2}):(\d{2}):(\d{2})$", re.IGNORECASE
)
_HOURS = re.compile(r"^[+-]?\d{1,2}(?:\.\d+)?$")


@dataclass(frozen=True)
class _ParsedTimezone:
    zone: tzinfo
    tzif_sha256: str | None = None
    package_version: str | None = None
    iana_version: str | None = None
    decimal_hour_rounded: bool = False
    transition_seconds: tuple[int, ...] | None = None


def _timezone_bytes(value: str) -> bytes:
    try:
        with pytz.open_resource(value) as resource:
            return cast(bytes, resource.read())
    except OSError as error:
        raise EphemerisSourceError("timezone_rules_unavailable") from error


def _current_timezone(value: str) -> _ParsedTimezone:
    parsed = _parse_timezone_name_cached(value)
    if parsed.tzif_sha256 is not None and (
        hashlib.sha256(_timezone_bytes(value)).hexdigest() != parsed.tzif_sha256
        or pytz.__version__ != parsed.package_version
        or pytz.OLSON_VERSION != parsed.iana_version
    ):
        # ZoneInfo is immutable (PEP615). Silently reloading the cache here
        # could mix old datetime objects with new rules in one calculation.
        raise EphemerisSourceError("timezone_rules_changed")
    return parsed


def invalid_timezone_message(value: str) -> str:
    return (
        f"Invalid birth timezone: {value!r}. "
        "Use an IANA name (e.g. 'Asia/Shanghai'), a UTC offset "
        "(e.g. '+08:00', 'UTC+8' or '+00:19:32'), or a bare offset in hours "
        "(e.g. '8', '-5', '5.5')."
    )


def parse_timezone_name(timezone_name: str) -> tzinfo:
    """Parse a named zone or a validated UTC offset shared by all engines."""
    return _current_timezone(timezone_name.strip()).zone


def timezone_transition_candidates(
    zone: tzinfo, lower: datetime, upper: datetime
) -> tuple[datetime, ...] | None:
    """Enumerate (lower,upper] only within this loaded object's explicit table.

    None requests the complete existing scanner. A name alone never binds
    another ZoneInfo object's data. No POSIX footer is inferred here.
    """
    key = getattr(zone, "key", None)
    if (
        not isinstance(zone, ZoneInfo)
        or not isinstance(key, str)
        or key not in pytz._all_timezones_unchecked
    ):
        return None
    parsed = _current_timezone(key)
    values = parsed.transition_seconds
    if parsed.zone is not zone or not values:
        return None
    if lower.utcoffset() != timedelta(0) or upper.utcoffset() != timedelta(0):
        raise ValueError("Clock transition bounds require UTC instants")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = upper - epoch
    if (delta.days * 86400 + delta.seconds, delta.microseconds) > (values[-1], 0):
        return None
    start = lower - epoch
    first = start.days * 86400 + start.seconds
    last = delta.days * 86400 + delta.seconds
    return tuple(
        epoch + timedelta(seconds=value) for value in values if first < value <= last
    )


def validate_local_clock(moment: datetime) -> None:
    """Reject DST gaps/folds rather than inventing an astronomical instant."""
    abbreviation = moment.tzname()
    if (
        moment.utcoffset() == timedelta(0)
        and abbreviation is not None
        and (abbreviation.startswith("-") or abbreviation == "zzz")
    ):
        # TZif's -00 convention is an unspecified UT offset, not known GMT.
        # Keep actual numeric offsets (including known zero) usable instead
        # of assigning an astronomical instant to an unresolved local clock.
        raise PydanticCustomError(
            "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
        )
    # PEP495's offset rules distinguish a gap (offset increases) from a fold
    # (offset decreases), without a UTC round trip that overflows at year1 or
    # 9999. Restrict this path to the fold-aware types returned by our parser;
    # third-party pre-PEP tzinfo implementations retain dateutil validation.
    if isinstance(moment.tzinfo, (ZoneInfo, timezone)):
        before = moment.replace(fold=0).utcoffset()
        after = moment.replace(fold=1).utcoffset()
        if before is None or after is None:
            raise ValueError("Local clock validation requires an aware datetime")
        exists = after <= before
        ambiguous = after < before
    else:
        exists = tz.datetime_exists(moment)
        ambiguous = tz.datetime_ambiguous(moment)
    if not exists:
        raise ValueError(
            "nonexistent local time：出生钟时为夏令时跳过的不存在钟时；请提供有效钟时。"
        )
    if ambiguous:
        raise ValueError(
            "ambiguous local time：出生钟时处于夏令时重复区间；请用明确 UTC 偏移消除歧义。"
        )


def timezone_rules_metadata(timezone_name: str) -> dict[str, str]:
    """Identify the rules actually used, independently of the host OS database."""
    parsed = _current_timezone(timezone_name.strip())
    if parsed.tzif_sha256 is not None:
        assert parsed.package_version is not None and parsed.iana_version is not None
        return {
            "provider": "zoneinfo.from_file",
            "database": "pytz",
            "package_version": parsed.package_version,
            "iana_version": parsed.iana_version,
            "tzif_sha256": parsed.tzif_sha256,
            "future_policy": "extrapolate_pinned_rules_subject_to_legal_changes",
        }
    fixed = {"provider": "datetime.timezone", "database": "explicit_fixed_offset"}
    if parsed.decimal_hour_rounded:
        fixed.update(
            decimal_hour_rounding="nearest_microsecond_ties_even",
            offset_resolution_seconds="0.000001",
            rounding_error_bound_seconds="0.0000005",
        )
    return fixed


@lru_cache(maxsize=128)
def _parse_timezone_name_cached(value: str) -> _ParsedTimezone:
    if value.upper() == "GMT":
        # GMT is a known zero offset, with its own declared abbreviation.
        # Retain that label without depending on a named-zone resource.
        return _ParsedTimezone(timezone(timedelta(0), "GMT"))
    if value.upper() in {"UTC", "Z"}:
        return _ParsedTimezone(timezone.utc)
    match = _SECOND_OFFSET.fullmatch(value) or _OFFSET.fullmatch(value)
    if match:
        parts = match.groups()
        sign, hour_text, minute_text = parts[:3]
        hours, minutes = int(hour_text), int(minute_text or 0)
        last_seconds = int(parts[3]) if len(parts) == 4 else 0
        if (
            minutes >= 60
            or last_seconds >= 60
            or hours > 15
            or (hours == 15 and (minutes or last_seconds))
        ):
            raise ValueError(invalid_timezone_message(value))
        seconds = (hours * 3600 + minutes * 60 + last_seconds) * (
            -1 if sign == "-" else 1
        )
        fixed_zone = (
            timezone(timedelta(0), "GMT")
            if seconds == 0 and value.upper().startswith("GMT")
            else timezone(timedelta(seconds=seconds))
        )
        return _ParsedTimezone(fixed_zone)
    if _HOURS.fullmatch(value):
        # Preserve Unicode-digit and arbitrary decimal input scope. Compute
        # exactly before the final, explicitly reported microsecond step.
        decimal_text = "".join(str(int(c)) if c.isdecimal() else c for c in value)
        normalized = (
            decimal_text.rstrip("0").rstrip(".")
            if "." in decimal_text
            else decimal_text
        )
        offset_hours = Decimal(normalized)
        if offset_hours.copy_abs() > Decimal(15):
            raise ValueError(invalid_timezone_message(value))
        with localcontext() as context:
            # The ten-digit multiplier remains exact for long inputs. Do not
            # inherit a caller's decimal precision or exponent limits.
            context.prec = max(28, len(normalized) + 16)
            context.Emin = min(context.Emin, -len(normalized) - 32)
            context.Emax = max(context.Emax, 32)
            microseconds = offset_hours * Decimal(3_600_000_000)
            rounded = microseconds.to_integral_value(rounding=ROUND_HALF_EVEN)
        return _ParsedTimezone(
            timezone(timedelta(microseconds=int(rounded))),
            decimal_hour_rounded=microseconds != rounded,
        )
    # Never let dateutil normalize malformed offsets (e.g. UTC+08:90).
    if value.upper().startswith(("UTC", "GMT", "+", "-")):
        raise ValueError(invalid_timezone_message(value))
    # pytz's public lists filter out unreadable files lazily. That would label
    # a missing installed rule file as bad user input on the first cold lookup.
    # Its generated declaration list distinguishes unknown names from damaged
    # data. Keep this dependency detail local to the TZif adapter.
    if value not in pytz._all_timezones_unchecked:
        raise ValueError(invalid_timezone_message(value))
    # Read the locked dependency's IANA TZif with the standard-library reader.
    # dateutil.tzfile truncates its transition table to the 32-bit interval:
    # pre-1901 dates can retain LMT and post-2037 dates lose future DST rules.
    # ZoneInfo handles the 64-bit section and POSIX footer. Loading the declared
    # data also avoids OS-dependent rules and missing newly introduced zones.
    data = _timezone_bytes(value)
    try:
        zone = ZoneInfo.from_file(BytesIO(data), key=value)
    except (ValueError, EOFError, struct.error, AssertionError) as error:
        raise EphemerisSourceError("timezone_rules_invalid") from error
    return _ParsedTimezone(
        zone,
        hashlib.sha256(data).hexdigest(),
        pytz.__version__,
        pytz.OLSON_VERSION,
        transition_seconds=explicit_transition_seconds(data),
    )
