"""Positive-gap extrema probes for every configured dayun boundary image."""

from calendar import isleap
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from dateutil.relativedelta import relativedelta

from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.utils.clock_events import CivilClockGap
from fatebridge.utils.solar_time import NormalizedBirthTime
from fatebridge.utils.timezones import (
    parse_timezone_name,
    timezone_transition_candidates,
)

MICROSECOND = timedelta(microseconds=1)


def _micros(value: timedelta) -> int:
    return (value.days * 86400 + value.seconds) * 1_000_000 + value.microseconds


def projected_wall_image(
    low: datetime, high: datetime, year_offset: int
) -> Tuple[datetime, datetime]:
    """Enclose calendar-year addition, including the backward leap clip."""
    if low.tzinfo is not None or high.tzinfo is not None or high < low:
        raise ValueError("大运墙钟投影需要顺序明确的无时区标签")
    points = [low, high]
    for year in range(low.year, high.year + 1):
        projected = year + year_offset
        if not 1 <= projected <= 9999:
            raise ValueError("大运年份投影超出可表示范围")
        if isleap(year) and not isleap(projected):
            clip = datetime(year, 2, 29)
            if low <= clip <= high:
                points.append(clip)
                if low < clip:
                    points.append(clip - MICROSECOND)
    shifted = [point + relativedelta(years=year_offset) for point in points]
    return min(shifted), max(shifted)


@lru_cache(maxsize=256)
def _forward_changes_on_utc_day(
    zone: tzinfo, day: date
) -> Tuple[Tuple[datetime, timedelta, timedelta], ...]:
    """Share complete second scans between overlapping boundary images."""
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    candidates = timezone_transition_candidates(
        zone, start - MICROSECOND, start + timedelta(days=1) - MICROSECOND
    )
    if candidates is not None:
        changes = []
        for at in candidates:
            previous = (at - MICROSECOND).astimezone(zone).utcoffset()
            current = at.astimezone(zone).utcoffset()
            if previous is None or current is None:
                raise ValueError("未来跳时扫描需要明确的UTC偏移")
            if current > previous:
                changes.append((at, previous, current))
        return tuple(changes)
    previous = (start - MICROSECOND).astimezone(zone).utcoffset()
    if previous is None:
        raise ValueError("未来跳时扫描需要明确的UTC偏移")
    changes = []
    for seconds in range(86400):
        at = start + timedelta(seconds=seconds)
        current = at.astimezone(zone).utcoffset()
        if current is None:
            raise ValueError("未来跳时扫描遇到未定义的UTC偏移")
        if current > previous:
            changes.append((at, previous, current))
        previous = current
    return tuple(changes)


@lru_cache(maxsize=256)
def forward_gaps_for_wall_image(
    zone: tzinfo, low: datetime, high: datetime
) -> Tuple[Tuple[CivilClockGap, ...], datetime, datetime]:
    """Scan the loaded clock, with an offset bound rather than analysis date.

    datetime offsets have magnitude strictly below24hours. Thus any transition
    whose post-change wall label is in the image is inside this UTC window.
    The cache binds the actual zone object, never just its display key.
    """
    if low.tzinfo is not None or high.tzinfo is not None or high < low:
        raise ValueError("未来跳时扫描需要顺序明确的墙钟范围")
    start = (low - timedelta(days=1)).replace(tzinfo=timezone.utc)
    end = (high + timedelta(days=1)).replace(tzinfo=timezone.utc)
    if isinstance(zone, timezone):
        return (), start, end
    # Include all integer seconds in the window. The strict24h margin keeps
    # any relevant transition away from the scan's open starting endpoint.
    start = start.replace(microsecond=0)
    if end.microsecond:
        end = end.replace(microsecond=0) + timedelta(seconds=1)
    gaps = []
    for ordinal in range(start.date().toordinal(), end.date().toordinal() + 1):
        for at, previous, current in _forward_changes_on_utc_day(
            zone, date.fromordinal(ordinal)
        ):
            if not start < at <= end:
                continue
            upper_wall = at.replace(tzinfo=None) + current
            if low <= upper_wall <= high:
                gaps.append(
                    CivilClockGap(
                        instant_utc=at,
                        lower_wall=at.replace(tzinfo=None) + previous,
                        upper_wall=upper_wall,
                        offset_before_seconds=int(previous.total_seconds()),
                        offset_after_seconds=int(current.total_seconds()),
                    )
                )
    return tuple(gaps), start, end


def collect_dayun_boundary_clock_events(
    template: NormalizedBirthTime,
    gender: Optional[str],
    cuts: Iterable[datetime],
    clock_at: Callable[[datetime], NormalizedBirthTime],
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]], Dict[str, Any]]:
    """Add finite boundary probes; do not certify continuous extrema."""
    zone = parse_timezone_name(template.timezone)
    if isinstance(zone, timezone):
        return [], [], {"status": "fixed_offset"}
    ordered = sorted(set(cuts))
    events: list[Dict[str, Any]] = []
    unresolved: list[Dict[str, Any]] = []
    windows: list[Dict[str, Any]] = []
    seen = set()
    for left, right in zip(ordered, ordered[1:]):
        last = right - MICROSECOND
        birth_a, details, wall_a, offset_a = (
            TimingAnalysis._dayun_calendar_wall_context(
                clock_at(left).input_datetime, gender, template.timezone
            )
        )
        birth_b, other, wall_b, offset_b = TimingAnalysis._dayun_calendar_wall_context(
            clock_at(last).input_datetime, gender, template.timezone
        )
        forward = details["forward_direction"]
        slope = -119 if forward else 121
        reference = details["reference_term"]
        if not (
            other["forward_direction"] == forward
            and other["reference_term"]["datetime_with_offset"]
            == reference["datetime_with_offset"]
            and birth_a.date() == birth_b.date()
            and birth_a.utcoffset() == birth_b.utcoffset()
            and (offset_a["years"], offset_a["months"])
            == (offset_b["years"], offset_b["months"])
            and _micros(wall_b - wall_a) == slope * _micros(last - left)
        ):
            unresolved.append(
                dict(
                    lower_utc=left.isoformat(),
                    upper_utc=right.isoformat(),
                    reason="boundary_clock_wall_cell_not_affine",
                )
            )
            continue
        low_wall, high_wall = sorted((wall_a, wall_b))
        for index in range(DEFAULT_DAYUN_PERIODS + 1):
            try:
                projected_low, projected_high = projected_wall_image(
                    low_wall, high_wall, index * 10
                )
                gaps, scan_start, scan_end = forward_gaps_for_wall_image(
                    zone, projected_low, projected_high
                )
            except (ValueError, OverflowError):
                unresolved.append(
                    dict(
                        lower_utc=left.isoformat(),
                        upper_utc=right.isoformat(),
                        reason="boundary_clock_window_not_fully_representable",
                        decade_boundary_index=index,
                    )
                )
                continue
            windows.append(
                dict(
                    lower_utc=left.isoformat(),
                    upper_utc=right.isoformat(),
                    decade_boundary_index=index,
                    projected_wall_start=projected_low.isoformat(),
                    projected_wall_end=projected_high.isoformat(),
                    scan_start_utc=scan_start.isoformat(),
                    scan_end_utc=scan_end.isoformat(),
                    forward_gap_count=len(gaps),
                )
            )
            for gap in gaps:
                for target in TimingAnalysis._dayun_wall_year_preimages(
                    gap.upper_wall, index * 10
                ):
                    if not low_wall <= target <= high_wall:
                        continue
                    quotient, remainder = divmod(_micros(target - wall_a), slope)
                    lower = left + MICROSECOND * quotient
                    upper = lower + MICROSECOND * bool(remainder)
                    key = (lower, upper, gap.instant_utc, index, target)
                    if not left <= lower <= upper <= last or key in seen:
                        continue
                    seen.add(key)
                    events.append(
                        dict(
                            kind="dayun_future_civil_gap_end",
                            name=f"第{index}个十年边界墙钟范围的跳时结束逆像",
                            lower_utc=lower.isoformat(),
                            upper_utc=upper.isoformat(),
                            at_utc=upper.isoformat(),
                            bracket_width_seconds=(upper - lower).total_seconds(),
                            source=dict(
                                policy="three_days_one_year_calendar_v1",
                                direction="顺行" if forward else "逆行",
                                reference_jie=reference["name"],
                                reference_at_utc=reference["datetime_with_offset"],
                                future_gap_at_utc=gap.instant_utc.isoformat(),
                                future_gap_start_wall=gap.lower_wall.isoformat(),
                                future_gap_end_wall=gap.upper_wall.isoformat(),
                                offset_before_seconds=str(gap.offset_before_seconds),
                                offset_after_seconds=str(gap.offset_after_seconds),
                                decade_boundary_index=str(index),
                                inverse_initial_wall=target.isoformat(),
                                scan_basis="projected_boundary_wall_image_independent_of_analysis_context",
                                precision_scope="computed_calendar_inverse_not_physical_error_bound",
                            ),
                        )
                    )
    return (
        events,
        unresolved,
        dict(
            status="calculated",
            timezone=template.timezone,
            scan_basis="all_configured_projected_boundary_wall_images",
            boundary_count=DEFAULT_DAYUN_PERIODS + 1,
            scan_step_seconds=1,
            windows=windows,
            continuous_completeness_certified=False,
            physical_precision_certified=False,
        ),
    )
