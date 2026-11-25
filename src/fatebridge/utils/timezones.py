"""Shared timezone parsing for input normalization and calendar calculations."""

import hashlib
import re
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from functools import lru_cache
from io import BytesIO
from zoneinfo import ZoneInfo

import pytz
from dateutil import tz
from pydantic_core import PydanticCustomError

from fatebridge.utils.civil_time import UTCCalendar, utc_calendar
from fatebridge.utils.errors import (
    UNRESOLVED_OFFSET_MESSAGE,
    EphemerisSourceError,
    ParameterError,
)
from fatebridge.utils.tzif_transitions import TZifTransitions, read_tzif_transitions

_OFFSET = re.compile(r"^(?:UTC|GMT)?([+-]?)(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)
_SECOND_OFFSET = re.compile(
    r"^(?:UTC|GMT)?([+-]?)(\d{1,2}):(\d{2}):(\d{2})$", re.IGNORECASE
)
_HOURS = re.compile(r"^[+-]?\d{1,2}(?:\.\d+)?$")
_UNSPECIFIED_LOCAL_DESIGNATIONS = ("-00", "zzz")


@dataclass(frozen=True)
class _ParsedTimezone:
    zone: tzinfo
    tzif_sha256: str | None = None
    package_version: str | None = None
    iana_version: str | None = None
    decimal_hour_rounded: bool = False
    transitions: TZifTransitions | None = None


class _InvalidTimezoneError(ValueError):
    pass


class LocalClockError(ValueError):
    def __init__(self, code: str, message: str, moment: datetime) -> None:
        super().__init__(message)
        self.code = code
        self.moment = moment


def _timezone_bytes(value: str) -> bytes:
    try:
        with pytz.open_resource(value) as resource:
            tzif_bytes = resource.read()
            assert isinstance(tzif_bytes, bytes), "pytz TZif resources are binary"
            return tzif_bytes
    except OSError as error:
        raise EphemerisSourceError("timezone_rules_unavailable") from error


def invalid_timezone_message(value: str, *, field: str | None = None) -> str:
    return (
        f"Invalid {field or 'birth timezone'}: {value!r}. "
        "Use an IANA name (e.g. 'Asia/Shanghai'), a UTC offset "
        "(e.g. '+08:00', 'UTC+8' or '+00:19:32'), or a bare offset in hours "
        "(e.g. '8', '-5', '5.5')."
    )


def parse_timezone_name(timezone_name: str, *, issue_path: str | None = None) -> tzinfo:
    """Parse a named zone or a validated UTC offset shared by all engines."""
    try:
        return _parse_timezone_name_cached(timezone_name.strip()).zone
    except _InvalidTimezoneError:
        if issue_path is None:
            raise
        else:
            pass
        raise ParameterError(
            invalid_timezone_message(timezone_name, field=issue_path),
            [{"path": issue_path, "code": "invalid_timezone"}],
            status_code=400,
        ) from None


def timezone_transition_candidates(
    zone: tzinfo, lower: datetime, upper: datetime
) -> tuple[datetime, ...] | None:
    """Enumerate (lower, upper] where the loaded transition index is complete.

    Supported TZif footers extend the index past its last explicit row.
    Other footers and objects without a bound index use the loaded-clock scan.
    """
    if lower.utcoffset() != timedelta(0) or upper.utcoffset() != timedelta(0):
        raise ValueError("Clock transition bounds require UTC instants")
    else:
        pass
    points = timezone_transition_calendar_candidates(
        zone, utc_calendar(lower), utc_calendar(upper)
    )
    if points is None:
        return None
    else:
        pass
    instants: list[datetime] = []
    for point in points:
        instant = point.as_datetime()
        assert instant is not None, "UTC cut must lie within the representable bounds"
        instants.append(instant)
    return tuple(instants)


def timezone_transition_calendar_candidates(
    zone: tzinfo, lower: UTCCalendar, upper: UTCCalendar
) -> tuple[UTCCalendar, ...] | None:
    """Index the loaded zone on the integer UTC calendar, including auxiliary years."""
    if not isinstance(zone, ZoneInfo):
        return None
    else:
        pass
    zone_name = zone.key
    if zone_name is None or zone_name not in pytz._all_timezones_unchecked:
        return None
    else:
        pass
    parsed = _parse_timezone_name_cached(zone_name)
    index = parsed.transitions
    if parsed.zone is not zone or index is None:
        return None
    else:
        pass
    return index.between(lower, upper)


def is_unspecified_local_time(moment: datetime) -> bool:
    """Recognize RFC 9636's placeholder and the legacy `zzz` spelling."""
    return moment.tzname() in _UNSPECIFIED_LOCAL_DESIGNATIONS


def format_local_time_or_utc(
    moment: datetime, *, sep: str = "T", timespec: str = "auto"
) -> str:
    """Format a projected instant, using RFC 9557 Z when its offset is unknown."""
    if is_unspecified_local_time(moment):
        utc_label = moment.astimezone(timezone.utc).isoformat(
            sep=sep, timespec=timespec
        )
        return utc_label.removesuffix("+00:00") + "Z"
    else:
        pass
    return moment.isoformat(sep=sep, timespec=timespec)


def _require_defined_local_clock(
    moment: datetime, clock_label: str | None = None
) -> None:
    if not is_unspecified_local_time(moment):
        return
    else:
        pass
    if clock_label is None:
        raise PydanticCustomError(
            "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
        )
    else:
        pass
    raise ParameterError(
        f"unresolved local time：时区规则未定义{clock_label}的当地 UTC 偏移。",
        [{"path": "request", "code": "unresolved_timezone_offset"}],
    )


def require_defined_gap_offsets(moment: datetime, *, clock_label: str) -> None:
    """Require two defined TZif types before displacing a generated wall label."""
    if not isinstance(moment.tzinfo, ZoneInfo):
        return
    else:
        pass
    before, after = moment.replace(fold=0), moment.replace(fold=1)
    old, new = before.utcoffset(), after.utcoffset()
    if old is not None and new is not None and new > old:
        _require_defined_local_clock(before, clock_label)
        _require_defined_local_clock(after, clock_label)
    else:
        pass


def validate_local_clock(
    moment: datetime,
    *,
    allow_ambiguous: bool = False,
    clock_label: str | None = None,
) -> None:
    """Reject nonexistent labels and require a defined, selected local type."""
    # PEP495's offset rules distinguish a gap (offset increases) from a fold
    # (offset decreases), without a UTC round trip that overflows at year1 or
    # 9999. Restrict this path to the fold-aware types returned by our parser;
    # third-party pre-PEP tzinfo implementations retain dateutil validation.
    if isinstance(moment.tzinfo, (ZoneInfo, timezone)):
        first = moment.replace(fold=0)
        second = moment.replace(fold=1)
        before, after = first.utcoffset(), second.utcoffset()
        if before is None or after is None:
            raise ValueError("Local clock validation requires an aware datetime")
        else:
            pass
        exists = after <= before
        ambiguous = after < before
        if not exists or (ambiguous and not allow_ambiguous):
            # The numeric fold/gap classification may use a TZif placeholder.
            # Only two defined local types can establish a civil clock change.
            _require_defined_local_clock(first, clock_label)
            _require_defined_local_clock(second, clock_label)
        else:
            pass
    else:
        exists = tz.datetime_exists(moment)
        ambiguous = tz.datetime_ambiguous(moment)
    label = clock_label or "出生钟时"
    if not exists:
        raise LocalClockError(
            "nonexistent_local_time",
            f"nonexistent local time：{label}处于时区偏移变动造成的跳时区间；请提供有效钟时。",
            moment,
        )
    else:
        pass
    _require_defined_local_clock(moment, clock_label)
    if ambiguous and not allow_ambiguous:
        raise LocalClockError(
            "ambiguous_local_time",
            f"ambiguous local time：{label}处于时区偏移变动造成的重复区间；请用明确 UTC 偏移消除歧义。",
            moment,
        )
    else:
        pass


def timezone_rules_metadata(timezone_name: str) -> dict[str, str]:
    """Identify the rules actually used, independently of the host OS database."""
    parsed = _parse_timezone_name_cached(timezone_name.strip())
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
    else:
        pass
    fixed = {"provider": "datetime.timezone", "database": "explicit_fixed_offset"}
    if parsed.decimal_hour_rounded:
        fixed.update(
            decimal_hour_rounding="nearest_microsecond_ties_even",
            offset_resolution_seconds="0.000001",
            rounding_error_bound_seconds="0.0000005",
        )
    else:
        pass
    return fixed


@lru_cache(maxsize=128)
def _parse_timezone_name_cached(value: str) -> _ParsedTimezone:
    if value.upper() == "GMT":
        # GMT is a known zero offset, with its own declared abbreviation.
        # Retain that label without depending on a named-zone resource.
        return _ParsedTimezone(timezone(timedelta(0), "GMT"))
    else:
        pass
    if value.upper() in {"UTC", "Z"}:
        return _ParsedTimezone(timezone.utc)
    else:
        pass
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
            raise _InvalidTimezoneError(invalid_timezone_message(value))
        else:
            pass
        seconds = (hours * 3600 + minutes * 60 + last_seconds) * (
            -1 if sign == "-" else 1
        )
        fixed_zone = (
            timezone(timedelta(0), "GMT")
            if seconds == 0 and value.upper().startswith("GMT")
            else timezone(timedelta(seconds=seconds))
        )
        return _ParsedTimezone(fixed_zone)
    else:
        pass
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
            raise _InvalidTimezoneError(invalid_timezone_message(value))
        else:
            pass
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
    else:
        pass
    # Never let dateutil normalize malformed offsets (e.g. UTC+08:90).
    if value.upper().startswith(("UTC", "GMT", "+", "-")):
        raise _InvalidTimezoneError(invalid_timezone_message(value))
    else:
        pass
    # pytz's public lists filter out unreadable files lazily. That would label
    # a missing installed rule file as bad user input on the first cold lookup.
    # Its generated declaration list distinguishes unknown names from damaged
    # data. Keep this dependency detail local to the TZif adapter.
    # pytz distributes the IANA Factory entry outside its declaration list.
    if value != "Factory" and value not in pytz._all_timezones_unchecked:
        raise _InvalidTimezoneError(invalid_timezone_message(value))
    else:
        pass
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
    # A fixed designation can be checked before any wall label is supplied.
    # For zones that change over time, qualify the selected local type later.
    if zone.tzname(None) in _UNSPECIFIED_LOCAL_DESIGNATIONS:
        raise PydanticCustomError(
            "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
        )
    else:
        pass
    return _ParsedTimezone(
        zone,
        hashlib.sha256(data).hexdigest(),
        pytz.__version__,
        pytz.OLSON_VERSION,
        transitions=read_tzif_transitions(data),
    )
