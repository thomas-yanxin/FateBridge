"""Read loaded civil-clock transitions at the IANA integer-UTC-second resolution."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Iterable, Literal
from zoneinfo import ZoneInfo

from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    timezone_transition_candidates,
)


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


def clock_scan_bounds(day: date) -> tuple[datetime, datetime]:
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


def _defined_offset(local: datetime) -> timedelta | None:
    offset = local.utcoffset()
    if offset is None:
        raise ValueError("未来钟时事件需要明确的UTC偏移")
    if isinstance(local.tzinfo, ZoneInfo) and is_unspecified_local_time(local):
        return None
    return offset


def birth_civil_clock_cuts(
    zone: tzinfo,
    lower: datetime,
    upper: datetime,
    *,
    boundary: Literal["offset", "date", "shichen"],
) -> tuple[tuple[tuple[datetime, datetime], ...], int | None]:
    """Return nominal cuts in (lower, upper], with their post-cut wall labels.

    Translate midnight and odd-hour labels within each constant-offset
    segment. At transitions compare both actual sides. Unspecified clock
    types can have nominal cuts, though they cannot resolve a birth label.
    The second result is the scan step when the loaded index lacks coverage.
    """
    if lower == upper:
        return (), None
    transitions = (
        ()
        if isinstance(zone, timezone)
        else timezone_transition_candidates(zone, lower, upper)
    )
    previous = lower.astimezone(zone)
    probes: Iterable[datetime]
    if transitions is None:
        floor = lower.replace(microsecond=0)
        probes = (
            floor + timedelta(seconds=second)
            for second in range(1, (upper - floor) // timedelta(seconds=1) + 1)
        )
    else:
        candidates = set(transitions)
        if boundary != "offset":
            hours = (0,) if boundary == "date" else (0, *range(1, 24, 2))
            for start, end in zip((lower, *transitions), (*transitions, upper)):
                local = previous if start == lower else start.astimezone(zone)
                elapsed = timedelta(
                    hours=local.hour,
                    minutes=local.minute,
                    seconds=local.second,
                    microseconds=local.microsecond,
                )
                span = end - start
                for day in range((elapsed + span).days + 1):
                    for hour in hours:
                        delta = timedelta(days=day, hours=hour) - elapsed
                        if timedelta(0) < delta <= span:
                            candidates.add(start + delta)
        probes = sorted(candidates)
    cuts = []
    for at in probes:
        if transitions is not None:
            previous = (at - timedelta(microseconds=1)).astimezone(zone)
        local = at.astimezone(zone)
        changed = (
            local.utcoffset() != previous.utcoffset()
            or (boundary != "offset" and local.date() != previous.date())
            or (
                boundary == "shichen"
                and (local.hour + 1) // 2 % 12 != (previous.hour + 1) // 2 % 12
            )
        )
        if changed:
            cuts.append((at, local))
        previous = local
    return tuple(cuts), 1 if transitions is None else None


def clock_offset_changes(
    zone: tzinfo, lower: datetime, upper: datetime
) -> tuple[tuple[datetime, timedelta, timedelta], ...]:
    """Return changes between defined offsets at UTC seconds in (lower, upper].

    Use the loaded zone's explicit table where available. The fallback samples
    every integer second so successive changes in the same day are retained.
    """
    if isinstance(zone, timezone):
        return ()
    previous = _defined_offset(lower.astimezone(zone))
    candidates = timezone_transition_candidates(zone, lower, upper)
    probes: Iterable[datetime]
    if candidates is None:
        floor = lower.replace(microsecond=0)
        span = upper - floor
        probes = (
            floor + timedelta(seconds=seconds)
            for seconds in range(1, span.days * 86400 + span.seconds + 1)
        )
    else:
        probes = candidates

    changes = []
    for at in probes:
        if candidates is not None:
            previous = _defined_offset(
                (at - timedelta(microseconds=1)).astimezone(zone)
            )
        current = _defined_offset(at.astimezone(zone))
        if previous is not None and current is not None and current != previous:
            changes.append((at, previous, current))
        previous = current
    return tuple(changes)


@lru_cache(maxsize=128)
def _clock_changes_near_day(
    zone: tzinfo, day: date
) -> tuple[tuple[datetime, timedelta, timedelta], ...]:
    return clock_offset_changes(zone, *clock_scan_bounds(day))


@lru_cache(maxsize=128)
def forward_clock_gaps_near_day(zone: tzinfo, day: date) -> tuple[CivilClockGap, ...]:
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
) -> tuple[CivilClockFold, ...]:
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
