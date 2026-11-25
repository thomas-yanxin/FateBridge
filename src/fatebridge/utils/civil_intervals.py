"""UTC preimages of intervals in defined local time under loaded clock rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_core import PydanticCustomError

from fatebridge.utils.civil_time import (
    NominalClockLabel,
    UTCCalendar,
    ZonedCalendar,
    utc_calendar,
)
from fatebridge.utils.errors import UNRESOLVED_OFFSET_MESSAGE, EphemerisSourceError
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    timezone_transition_calendar_candidates,
)

METHOD_ID = "local_wall_interval_preimage_v1"
DAY = timedelta(days=1)
FIRST_UTC = utc_calendar(datetime.min.replace(tzinfo=timezone.utc))
LAST_UTC = utc_calendar(datetime.max.replace(tzinfo=timezone.utc))


def _rule_utc(zone: ZoneInfo, point: UTCCalendar) -> datetime:
    """Use the established Gregorian-cycle projection only at clock edges."""
    if FIRST_UTC.ordinal < point.ordinal < LAST_UTC.ordinal:
        actual = point.as_datetime()
        assert actual is not None
        return actual
    else:
        pass
    return ZonedCalendar(point, zone).utc_rule_proxy()[0]


@lru_cache(maxsize=128)
def _clock_cuts_on_utc_day(zone: ZoneInfo, ordinal: int) -> tuple[UTCCalendar, ...]:
    """Partition a TZif day when the loaded explicit table is unavailable."""
    start = UTCCalendar(ordinal, 0)
    rule_start = _rule_utc(zone, start)
    cuts = [start]
    previous = None
    for seconds in range(86400):
        local = (rule_start + timedelta(seconds=seconds)).astimezone(zone)
        current = local.utcoffset(), is_unspecified_local_time(local)
        if seconds and current != previous:
            cuts.append(UTCCalendar(ordinal, seconds * 1_000_000))
        else:
            pass
        previous = current
    return tuple(cuts)


def local_interval_preimages(
    start: datetime | NominalClockLabel,
    end: datetime | NominalClockLabel,
    zone: tzinfo,
) -> list[tuple[UTCCalendar, UTCCalendar]]:
    """Return all UTC components whose defined local clock is in [start, end).

    Inputs are nominal local bounds and a named ZoneInfo or fixed offset. The
    bounds themselves need not exist. Each TZif clock segment is affine on
    the UTC axis. Intersect with the shifted bounds on the integer calendar,
    including UTC labels outside datetime's range. Placeholder types cannot
    supply instants. Report an unresolved clock when they are the interval's
    only nominal support.
    """
    if any(
        isinstance(bound, datetime) and bound.tzinfo is not None
        for bound in (start, end)
    ):
        raise ValueError("Local interval requires ordered naive clock bounds")
    else:
        pass
    first, last = (
        (
            NominalClockLabel.from_local_datetime(bound)
            if isinstance(bound, datetime)
            else bound
        )
        for bound in (start, end)
    )
    wall_start = UTCCalendar(first.ordinal, first.microseconds_of_day)
    wall_end = UTCCalendar(last.ordinal, last.microseconds_of_day)
    if wall_end <= wall_start:
        raise ValueError("Local interval requires ordered naive clock bounds")
    else:
        pass
    if isinstance(zone, timezone):
        fixed_offset = zone.utcoffset(None)
        return [(wall_start.shifted(-fixed_offset), wall_end.shifted(-fixed_offset))]
    else:
        pass
    if not isinstance(zone, ZoneInfo):
        raise ValueError("Local intervals require ZoneInfo or a fixed UTC offset")
    else:
        pass
    # Every Python timezone offset is strictly less than 24 hours in magnitude.
    lower, upper = wall_start.shifted(-DAY), wall_end.shifted(DAY)
    if lower.ordinal <= FIRST_UTC.ordinal or upper.ordinal >= LAST_UTC.ordinal:
        # A foreign ZoneInfo may contain explicit transitions at these dates.
        # Its name cannot qualify the IANA initial/future rule projection.
        try:
            source_zone = parse_timezone_name(zone.key) if zone.key else None
        except ValueError:
            source_zone = None
        if zone is not source_zone:
            raise EphemerisSourceError("timezone_rules_unavailable")
        else:
            pass
    else:
        pass
    cuts = timezone_transition_calendar_candidates(zone, lower, upper)
    if cuts is None:
        cuts = tuple(
            at
            for ordinal in range(lower.ordinal, upper.ordinal + 1)
            for at in _clock_cuts_on_utc_day(zone, ordinal)
            if lower < at < upper
        )
    else:
        pass
    points = (lower, *(at for at in cuts if lower < at < upper), upper)
    result: list[tuple[UTCCalendar, UTCCalendar]] = []
    has_unspecified_support = False
    for segment_start, segment_end in zip(points, points[1:]):
        local = _rule_utc(zone, segment_start).astimezone(zone)
        offset = local.utcoffset()
        assert offset is not None
        low = max(segment_start, wall_start.shifted(-offset))
        high = min(segment_end, wall_end.shifted(-offset))
        if low >= high:
            continue
        else:
            pass
        if is_unspecified_local_time(local):
            has_unspecified_support = True
            continue
        else:
            pass
        if result and result[-1][1] == low:
            result[-1] = result[-1][0], high
        else:
            result.append((low, high))
    if not result and has_unspecified_support:
        raise PydanticCustomError(
            "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
        )
    else:
        pass
    return result
