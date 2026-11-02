"""Read loaded civil-clock gaps at the IANA integer-UTC-second resolution."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Tuple

from fatebridge.utils.timezones import timezone_transition_candidates


@dataclass(frozen=True)
class CivilClockGap:
    instant_utc: datetime
    lower_wall: datetime
    upper_wall: datetime
    offset_before_seconds: int
    offset_after_seconds: int


@dataclass(frozen=True)
class CivilClockFold:
    instant_utc: datetime
    lower_wall: datetime
    upper_wall: datetime
    offset_before_seconds: int
    offset_after_seconds: int


def clock_scan_bounds(day: date) -> Tuple[datetime, datetime]:
    """Cover the analysis day and four surrounding days on either side.

    This is a bounded computational clock search, not an uncertainty model.
    A tzinfo offset is strictly less than24hours; the wider window retains
    nearby gap-end discontinuities even with the resolver's adjacent-day
    offset comparison. It does not certify physical future clock laws.
    """
    low_day = date.fromordinal(max(1, day.toordinal() - 4))
    high_day = date.fromordinal(min(date.max.toordinal(), day.toordinal() + 5))
    return (
        datetime.combine(low_day, time.min, tzinfo=timezone.utc),
        datetime.combine(high_day, time.min, tzinfo=timezone.utc),
    )


@lru_cache(maxsize=128)
def _clock_changes_near_day(
    zone: tzinfo, day: date
) -> Tuple[Tuple[datetime, timedelta, timedelta], ...]:
    """Use the actual loaded zone object, including its data identity.

    The cache must not reuse a zone-name-only entry after the loaded clock
    object changes. Fixed offsets have no gaps. Scanning each integer UTC
    second retains multiple changes inside one hour or day in the declared
    TZif model; it is not an astronomical or recording precision claim.
    """
    if isinstance(zone, timezone):
        return ()
    low, high = clock_scan_bounds(day)
    previous = low.astimezone(zone).utcoffset()
    if previous is None:
        raise ValueError("未来钟时事件需要明确的UTC偏移")
    candidates = timezone_transition_candidates(zone, low, high)
    if candidates is not None:
        changes = []
        for at in candidates:
            previous = (at - timedelta(microseconds=1)).astimezone(zone).utcoffset()
            current = at.astimezone(zone).utcoffset()
            if previous is None or current is None:
                raise ValueError("未来钟时事件需要明确的UTC偏移")
            if current != previous:
                changes.append((at, previous, current))
        return tuple(changes)
    changes = []
    for seconds in range(1, int((high - low).total_seconds()) + 1):
        at = low + timedelta(seconds=seconds)
        current = at.astimezone(zone).utcoffset()
        if current is None:
            raise ValueError("未来钟时事件遇到未定义的UTC偏移")
        if current != previous:
            changes.append((at, previous, current))
        previous = current
    return tuple(changes)


@lru_cache(maxsize=128)
def forward_clock_gaps_near_day(zone: tzinfo, day: date) -> Tuple[CivilClockGap, ...]:
    return tuple(
        CivilClockGap(
            instant_utc=at,
            lower_wall=at.replace(tzinfo=None) + old,
            upper_wall=at.replace(tzinfo=None) + new,
            offset_before_seconds=int(old.total_seconds()),
            offset_after_seconds=int(new.total_seconds()),
        )
        for at, old, new in _clock_changes_near_day(zone, day)
        if new > old
    )


@lru_cache(maxsize=128)
def backward_clock_folds_near_day(
    zone: tzinfo, day: date
) -> Tuple[CivilClockFold, ...]:
    return tuple(
        CivilClockFold(
            instant_utc=at,
            lower_wall=at.replace(tzinfo=None) + new,
            upper_wall=at.replace(tzinfo=None) + old,
            offset_before_seconds=int(old.total_seconds()),
            offset_after_seconds=int(new.total_seconds()),
        )
        for at, old, new in _clock_changes_near_day(zone, day)
        if new < old
    )
