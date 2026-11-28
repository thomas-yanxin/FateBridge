"""Physical instant ordering, explicit-offset resolution, intervals, and transition events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Iterable, Literal
from zoneinfo import ZoneInfo

from pydantic_core import PydanticCustomError

from fatebridge.utils.civil_time import (
    NominalClockLabel,
    UTCCalendar,
    ZonedCalendar,
    normalize_date_text,
    normalize_time_text,
    parse_civil_iso_clock,
    utc_calendar,
    utc_ordering_key,
)
from fatebridge.utils.errors import (
    UNRESOLVED_OFFSET_MESSAGE,
    EphemerisSourceError,
    ParameterError,
)
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    timezone_transition_calendar_candidates,
    timezone_transition_candidates,
    validate_local_clock,
)

OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})(?::(\d{2}))?$")
LOCAL_INTERVAL_METHOD_ID = "local_wall_interval_preimage_v1"
DAY = timedelta(days=1)
FIRST_UTC = utc_calendar(datetime.min.replace(tzinfo=timezone.utc))
LAST_UTC = utc_calendar(datetime.max.replace(tzinfo=timezone.utc))


def parse_local_datetime(
    date_text: str,
    time_text: str,
    timezone_name: str | None = None,
    *,
    validate_wall: bool = False,
) -> datetime:
    clock = parse_civil_iso_clock(
        f"{normalize_date_text(date_text)} {normalize_time_text(time_text)}"
    )
    zone = parse_timezone_name(timezone_name or DEFAULT_BIRTH_TIMEZONE)
    if isinstance(clock, UTCCalendar):
        moment = ZonedCalendar(clock, zone).require_datetime()
        allow_ambiguous = True
    else:
        moment = clock.replace(tzinfo=zone)
        allow_ambiguous = False
    if validate_wall:
        validate_local_clock(moment, allow_ambiguous=allow_ambiguous)
    return moment


def utc_instant(moment: datetime) -> datetime:
    """Never compare same-zone wall labels when an actual instant is intended."""
    if moment.utcoffset() is None:
        raise ValueError("实际时刻比较必须带时区，不能默认服务器时区")
    return moment.astimezone(timezone.utc)


def format_utc_offset(offset: timedelta) -> str:
    """Render the actual offset at the same precision as an ISO clock label."""
    return time(tzinfo=timezone(offset)).isoformat().removeprefix("00:00:00")


def resolve_civil_clock(
    wall: datetime,
    zone: str,
    explicit_offset: str | None = None,
    *,
    offset_field: str = "analysis_utc_offset",
    timezone_field: str | None = None,
    recorded_offset: str | None = None,
) -> datetime:
    """Resolve a local label without inventing a side of a fold or a gap.

    The named zone remains the calendar zone. An offset only selects and
    verifies the actual instant, including historical offsets with seconds.
    """
    if wall.utcoffset() is not None:
        raise ValueError("本地钟表字段须为无时区标签，实际时刻另外明确偏移")
    if recorded_offset is not None:
        if explicit_offset is None:
            explicit_offset = recorded_offset
        elif explicit_offset != recorded_offset:
            requested = resolve_civil_clock(
                wall,
                zone,
                explicit_offset,
                offset_field=offset_field,
                timezone_field=timezone_field,
            )
            recorded = resolve_civil_clock(
                wall,
                zone,
                recorded_offset,
                offset_field=offset_field,
                timezone_field=timezone_field,
            )
            if utc_ordering_key(requested) != utc_ordering_key(recorded):
                raise ParameterError(
                    f"{offset_field}与已确认出生记录的UTC偏移选择冲突",
                    [{"path": offset_field, "code": "conflicting_utc_offset"}],
                    status_code=400,
                )
            return requested
    zone_info = parse_timezone_name(zone, issue_path=timezone_field)
    local = wall.replace(tzinfo=zone_info)
    if explicit_offset is None:
        validate_local_clock(local)
        return local
    match = (
        OFFSET.fullmatch(explicit_offset.strip())
        if type(explicit_offset) is str
        else None
    )
    if match is None:
        raise ParameterError(
            f"{offset_field}须为±HH:MM或±HH:MM:SS",
            [{"path": offset_field, "code": "invalid_utc_offset"}],
            status_code=400,
        )
    sign, hour, minute, second = match.groups()
    h, m, s = int(hour), int(minute), int(second or 0)
    if h >= 24 or m >= 60 or s >= 60:
        raise ParameterError(
            f"{offset_field}超出有效UTC偏移范围",
            [{"path": offset_field, "code": "invalid_utc_offset"}],
            status_code=400,
        )
    expected = timedelta(hours=h, minutes=m, seconds=s) * (1 if sign == "+" else -1)
    candidates = local.replace(fold=0), local.replace(fold=1)
    for candidate in candidates:
        if candidate.utcoffset() == expected:
            # The parsed types are fold-aware. Validate the selected member
            # and keep fold=0 for an ordinary label with equal offsets.
            validate_local_clock(candidate, allow_ambiguous=True)
            return candidate
    defined = next(
        (
            candidate
            for candidate in candidates
            if not is_unspecified_local_time(candidate)
        ),
        candidates[0],
    )
    validate_local_clock(defined, allow_ambiguous=True)
    allowed = sorted(
        {
            format_utc_offset(offset)
            for candidate in candidates
            if not is_unspecified_local_time(candidate)
            and (offset := candidate.utcoffset()) is not None
        }
    )
    raise ParameterError(
        f"{offset_field}={explicit_offset!r}与该钟时在时区{zone!r}的实际偏移不一致。"
        f"该时区规则给出的偏移为{'、'.join(allowed)}，请核对原始钟时和时区。",
        [
            {
                "path": offset_field,
                "code": "utc_offset_mismatch",
                "constraints": {"expected": allowed},
            }
        ],
        status_code=400,
    )


def _rule_utc(zone: ZoneInfo, point: UTCCalendar) -> datetime:
    """Use the established Gregorian-cycle projection only at clock edges."""
    if FIRST_UTC.ordinal < point.ordinal < LAST_UTC.ordinal:
        actual = point.as_datetime()
        assert actual is not None
        return actual
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
    if isinstance(zone, timezone):
        fixed_offset = zone.utcoffset(None)
        return [(wall_start.shifted(-fixed_offset), wall_end.shifted(-fixed_offset))]
    if not isinstance(zone, ZoneInfo):
        raise ValueError("Local intervals require ZoneInfo or a fixed UTC offset")
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
    cuts = timezone_transition_calendar_candidates(zone, lower, upper)
    if cuts is None:
        cuts = tuple(
            at
            for ordinal in range(lower.ordinal, upper.ordinal + 1)
            for at in _clock_cuts_on_utc_day(zone, ordinal)
            if lower < at < upper
        )
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
        if is_unspecified_local_time(local):
            has_unspecified_support = True
            continue
        if result and result[-1][1] == low:
            result[-1] = result[-1][0], high
        else:
            result.append((low, high))
    if not result and has_unspecified_support:
        raise PydanticCustomError(
            "unresolved_timezone_offset", UNRESOLVED_OFFSET_MESSAGE
        )
    return result


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
