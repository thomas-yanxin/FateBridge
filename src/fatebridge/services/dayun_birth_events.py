"""Dayun wall cells, boundary clock scans, future gap probes, and birth-time event probes."""

from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from fractions import Fraction
from functools import lru_cache
from itertools import pairwise
from typing import Literal, Mapping, Protocol, TypedDict

from dateutil.relativedelta import relativedelta
from typing_extensions import NotRequired

from fatebridge.core.almanac import SolarTerm, localize_datetime
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.bazi.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.services.birth_time_events import (
    BirthEventProbeRecord,
    BirthEventRecord,
    NatalEventPayload,
    NatalEventProbe,
    UnresolvedBirthEvent,
)
from fatebridge.utils.civil_clock import (
    CivilClockFold,
    CivilClockGap,
    backward_clock_folds_near_day,
    birth_civil_clock_cuts,
    clock_offset_changes,
    clock_scan_bounds,
    forward_clock_gaps_near_day,
    utc_instant,
)
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar, utc_calendar
from fatebridge.utils.solar_time import NormalizedBirthTime, rebase_birth_clock
from fatebridge.utils.timezones import parse_timezone_name

MICROSECOND = timedelta(microseconds=1)
MONTH_CARRY = timedelta(hours=6)  # 30 nominal days / 120 offset seconds per second.


class BirthClockAtInstant(Protocol):
    def __call__(self, birth_instant_utc: datetime, /) -> NormalizedBirthTime: ...


@dataclass(frozen=True, kw_only=True)
class DayunWallCell:
    lower: datetime
    upper: datetime
    last: datetime
    first_wall: datetime
    last_wall: datetime
    slope: int
    is_forward: bool
    reference_term: SolarTerm
    is_affine: bool

    @property
    def reference_timestamp(self) -> str:
        if self.reference_term.has_defined_local_clock:
            return self.reference_term.calendar.isoformat()
        else:
            return self.reference_term.calendar.utc.isoformat()

    @property
    def wall_range(self) -> tuple[datetime, datetime]:
        low, high = sorted((self.first_wall, self.last_wall))
        return low, high

    def inverse(self, target: datetime) -> tuple[datetime, datetime] | None:
        """Enclose the target on the microsecond grid of a qualified cell."""
        low, high = self.wall_range
        if not low <= target <= high:
            return None
        delta = (target - self.first_wall) // MICROSECOND
        quotient, remainder = divmod(delta, self.slope)
        lower = self.lower + quotient * MICROSECOND
        return lower, lower + bool(remainder) * MICROSECOND


def build_dayun_wall_cells(
    timezone_name: str,
    gender: str | None,
    cuts: set[datetime],
    high: datetime,
    clock_at: BirthClockAtInstant,
) -> tuple[DayunWallCell, ...]:
    ordered = sorted(cuts)
    intervals = [
        (left, right, right - MICROSECOND) for left, right in pairwise(ordered)
    ]
    # note (dayun): A cut at the inclusive endpoint owns a singleton final cell.
    intervals.append((ordered[-1], high, high))
    cells = []
    for left, right, last in intervals:
        start = TimingAnalysis.resolve_dayun_start(
            clock_at(left).input_datetime, gender, timezone_name
        )
        initial_wall, calendar_offset = start.calendar_wall_offset()
        reference_term = start.target_term
        is_forward = start.forward_direction
        # note (dayun): One elapsed second changes the nominal offset by 120 seconds.
        slope = -119 if is_forward else 121
        final_wall = initial_wall
        is_affine = True
        if left != last:
            end = TimingAnalysis.resolve_dayun_start(
                clock_at(last).input_datetime, gender, timezone_name
            )
            final_wall, final_offset = end.calendar_wall_offset()
            final_reference_term = end.target_term
            reference_point = reference_term.civil_point
            final_reference_point = final_reference_term.civil_point
            if reference_point is None and final_reference_point is None:
                has_same_reference = (
                    reference_term.has_defined_local_clock
                    and reference_term.calendar.isoformat()
                ) == (
                    final_reference_term.has_defined_local_clock
                    and final_reference_term.calendar.isoformat()
                )
            else:
                has_same_reference = reference_point == final_reference_point
            is_affine = (
                end.forward_direction == is_forward
                and has_same_reference
                and end.birth.date() == start.birth.date()
                and end.birth.utcoffset() == start.birth.utcoffset()
                and (final_offset["years"], final_offset["months"])
                == (calendar_offset["years"], calendar_offset["months"])
                and final_wall - initial_wall == slope * (last - left)
            )
        cells.append(
            DayunWallCell(
                lower=left,
                upper=right,
                last=last,
                first_wall=initial_wall,
                last_wall=final_wall,
                slope=slope,
                is_forward=is_forward,
                reference_term=reference_term,
                is_affine=is_affine,
            )
        )
    return tuple(cells)


class FutureClockScan(TypedDict):
    status: Literal[
        "not_applicable_explicit_age",
        "fixed_offset",
        "unavailable_clock_window",
        "calculated",
    ]
    timezone: NotRequired[str]
    analysis_utc_day: NotRequired[str]
    scan_start_utc: NotRequired[str]
    scan_end_utc: NotRequired[str]
    forward_gap_count: NotRequired[int]
    backward_fold_count: NotRequired[int]
    scan_step_seconds: NotRequired[int]
    continuous_completeness_certified: NotRequired[bool]
    physical_precision_certified: NotRequired[bool]


def collect_future_dayun_gap_events(
    template: NormalizedBirthTime,
    analysis_moment: datetime | None,
    cells: tuple[DayunWallCell, ...],
) -> tuple[
    list[BirthEventRecord],
    list[UnresolvedBirthEvent],
    FutureClockScan,
    tuple[CivilClockGap, ...],
]:
    """Retain calculated inverse brackets; never certify continuous coverage."""
    if analysis_moment is None:
        return [], [], {"status": "not_applicable_explicit_age"}, ()
    zone = parse_timezone_name(template.timezone)
    if isinstance(zone, timezone):
        return [], [], {"status": "fixed_offset"}, ()
    analysis = utc_calendar(localize_datetime(analysis_moment, template.timezone))
    try:
        utc_day = date(*analysis.date_parts)
        scan_low, scan_high = clock_scan_bounds(utc_day)
        gaps = forward_clock_gaps_near_day(zone, utc_day)
        folds = backward_clock_folds_near_day(zone, utc_day)
    except (ValueError, OverflowError):
        return (
            [],
            [{"reason": "future_clock_window_not_fully_representable"}],
            {
                "status": "unavailable_clock_window",
                "continuous_completeness_certified": False,
            },
            (),
        )
    scan: FutureClockScan = {
        "status": "calculated",
        "timezone": template.timezone,
        "analysis_utc_day": utc_day.isoformat(),
        "scan_start_utc": scan_low.isoformat(),
        "scan_end_utc": scan_high.isoformat(),
        "forward_gap_count": len(gaps),
        "backward_fold_count": len(folds),
        "scan_step_seconds": 1,
        "continuous_completeness_certified": False,
        "physical_precision_certified": False,
    }
    if not gaps and not folds:
        return [], [], scan, ()
    events: list[BirthEventRecord] = []
    unresolved: list[UnresolvedBirthEvent] = []
    seen = set()
    changes: tuple[CivilClockGap | CivilClockFold, ...] = (*gaps, *folds)
    for cell in cells:
        if not cell.is_affine:
            unresolved.append(
                {
                    "lower_utc": cell.lower.isoformat(),
                    "upper_utc": cell.upper.isoformat(),
                    "reason": "dayun_wall_cell_not_affine_under_declared_partition",
                }
            )
            continue
        for gap in changes:
            fold = gap.offset_after_seconds < gap.offset_before_seconds
            change_name = "fold" if fold else "gap"
            for index in range(DEFAULT_DAYUN_PERIODS + 1):
                targets = TimingAnalysis._dayun_wall_year_preimages(
                    gap.upper_wall, index * 10
                )
                for target in targets:
                    bracket = cell.inverse(target)
                    if bracket is None:
                        continue
                    lower, upper = bracket
                    key = (lower, upper, gap.instant_utc, index, target)
                    if key in seen:
                        continue
                    seen.add(key)
                    events.append(
                        {
                            "kind": (
                                "dayun_future_civil_fold_end"
                                if fold
                                else "dayun_future_civil_gap_end"
                            ),
                            "name": f"第{index}个十年边界的未来{'回拨' if fold else '跳时'}结束逆像",
                            "lower_utc": lower.isoformat(),
                            "upper_utc": upper.isoformat(),
                            "at_utc": upper.isoformat(),
                            "bracket_width_seconds": (upper - lower).total_seconds(),
                            "source": {
                                "policy": "three_days_one_year_calendar_v1",
                                "direction": "顺行" if cell.is_forward else "逆行",
                                "reference_jie": cell.reference_term.name,
                                "reference_at_utc": cell.reference_timestamp,
                                f"future_{change_name}_at_utc": gap.instant_utc.isoformat(),
                                f"future_{change_name}_start_wall": gap.lower_wall.isoformat(),
                                f"future_{change_name}_end_wall": gap.upper_wall.isoformat(),
                                "offset_before_seconds": str(gap.offset_before_seconds),
                                "offset_after_seconds": str(gap.offset_after_seconds),
                                "decade_boundary_index": str(index),
                                "inverse_initial_wall": target.isoformat(),
                                "precision_scope": "computed_calendar_inverse_not_physical_error_bound",
                            },
                        }
                    )
    return events, unresolved, scan, gaps


def collect_dayun_analysis_events(
    template: NormalizedBirthTime,
    gender: str | None,
    analysis_moment: datetime | None,
    cells: tuple[DayunWallCell, ...],
    clock_at: BirthClockAtInstant,
    future_gaps: tuple[CivilClockGap, ...],
) -> tuple[list[BirthEventRecord], list[UnresolvedBirthEvent]]:
    analysis = None
    analysis_walls = []
    if analysis_moment is not None:
        local = localize_datetime(analysis_moment, template.timezone)
        analysis = utc_calendar(local)
        analysis_walls.append(local.replace(tzinfo=None))
        for gap in future_gaps:
            width = gap.upper_wall - gap.lower_wall
            gap_start = utc_calendar(gap.instant_utc)
            if gap_start <= analysis < gap_start.shifted(width):
                # note (dayun): The timeline shifts an imaginary label by the gap width.
                analysis_walls.append(
                    gap.lower_wall + analysis.elapsed_since(gap_start)
                )
    events: list[BirthEventRecord] = []
    unresolved: list[UnresolvedBirthEvent] = []
    seen = set()
    for cell in cells:
        if not cell.is_affine:
            unresolved.append(
                dict(
                    lower_utc=cell.lower.isoformat(),
                    upper_utc=cell.upper.isoformat(),
                    reason="analysis_inverse_wall_cell_not_affine",
                )
            )
            continue
        low_wall, high_wall = cell.wall_range
        targets = []
        for index in range(DEFAULT_DAYUN_PERIODS + 1):
            for analysis_wall in analysis_walls:
                for target in TimingAnalysis._dayun_wall_year_preimages(
                    analysis_wall, index * 10
                ):
                    targets.append(("dayun_analysis_moment", index, target))
            for year in range(low_wall.year, high_wall.year + 1):
                projected_year = year + index * 10
                if (
                    1 <= projected_year <= 9999
                    and isleap(year)
                    and not isleap(projected_year)
                ):
                    targets.append(
                        ("dayun_decade_leap_clip", index, datetime(year, 2, 29))
                    )
        for kind, index, target in targets:
            bracket = cell.inverse(target)
            if bracket is None:
                continue
            lower, upper = bracket
            key = (kind, index, target, lower, upper)
            if key in seen:
                continue
            seen.add(key)
            if kind == "dayun_analysis_moment":
                # note (dayun): Check the actual instant because a wall label can repeat in a fold.
                actual = []
                for at in {lower - MICROSECOND, lower, upper, upper + MICROSECOND}:
                    if not cell.lower <= at <= cell.last:
                        continue
                    birth, _, wall, _ = TimingAnalysis._dayun_calendar_wall_context(
                        clock_at(at).input_datetime, gender, template.timezone
                    )
                    resolved, _ = TimingAnalysis._resolve_dayun_calendar_boundary(
                        birth, wall, index * 10, template.timezone
                    )
                    actual.append(utc_calendar(resolved))
                if (
                    not actual
                    or analysis is None
                    or not min(actual) <= analysis <= max(actual)
                ):
                    continue
            source = dict(
                policy="three_days_one_year_calendar_v1",
                direction="顺行" if cell.is_forward else "逆行",
                reference_jie=cell.reference_term.name,
                reference_at_utc=cell.reference_timestamp,
                decade_boundary_index=str(index),
                inverse_initial_wall=target.isoformat(),
                precision_scope="computed_calendar_inverse_not_physical_error_bound",
            )
            if kind == "dayun_analysis_moment":
                assert analysis is not None
                source["analysis_at_utc"] = analysis.isoformat()
            else:
                source["projected_year"] = str(target.year + index * 10)
                source["calendar_discontinuity"] = (
                    "February29_to_February28_year_clipping"
                )
            events.append(
                dict(
                    kind=kind,
                    name=f"第{index}个十年边界的{'分析时刻' if kind == 'dayun_analysis_moment' else '闰日裁剪'}逆像",
                    lower_utc=lower.isoformat(),
                    upper_utc=upper.isoformat(),
                    at_utc=upper.isoformat(),
                    bracket_width_seconds=(upper - lower).total_seconds(),
                    source=source,
                )
            )
    return events, unresolved


class BoundaryClockWindow(TypedDict):
    lower_utc: str
    upper_utc: str
    decade_boundary_index: int
    projected_wall_start: str
    projected_wall_end: str
    scan_start_utc: str
    scan_end_utc: str
    forward_gap_count: int


class BoundaryClockScan(TypedDict):
    status: Literal["fixed_offset", "calculated"]
    timezone: NotRequired[str]
    scan_basis: NotRequired[str]
    boundary_count: NotRequired[int]
    scan_step_seconds: NotRequired[int]
    windows: NotRequired[list[BoundaryClockWindow]]
    continuous_completeness_certified: NotRequired[bool]
    physical_precision_certified: NotRequired[bool]


def projected_wall_image(
    low: datetime, high: datetime, year_offset: int
) -> tuple[datetime, datetime]:
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
) -> tuple[tuple[datetime, timedelta, timedelta], ...]:
    """Share complete second scans between overlapping boundary images."""
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return tuple(
        (at, previous, current)
        for at, previous, current in clock_offset_changes(
            zone, start - MICROSECOND, start + timedelta(days=1) - MICROSECOND
        )
        if current > previous
    )


@lru_cache(maxsize=256)
def forward_gaps_for_wall_image(
    zone: tzinfo, low: datetime, high: datetime
) -> tuple[tuple[CivilClockGap, ...], datetime, datetime]:
    """Find defined forward gap ends in the projected wall clock using its loaded zone."""
    if low.tzinfo is not None or high.tzinfo is not None or high < low:
        raise ValueError("未来跳时扫描需要顺序明确的墙钟范围")
    start = (low - timedelta(days=1)).replace(tzinfo=timezone.utc)
    end = (high + timedelta(days=1)).replace(tzinfo=timezone.utc)
    if isinstance(zone, timezone):
        return (), start, end
    # note (clock): Offsets are under 24 hours, so the open scan endpoint cannot hide a relevant gap.
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
    cells: tuple[DayunWallCell, ...],
) -> tuple[list[BirthEventRecord], list[UnresolvedBirthEvent], BoundaryClockScan]:
    """Add finite boundary probes; do not certify continuous extrema."""
    zone = parse_timezone_name(template.timezone)
    if isinstance(zone, timezone):
        return [], [], {"status": "fixed_offset"}
    events: list[BirthEventRecord] = []
    unresolved: list[UnresolvedBirthEvent] = []
    windows: list[BoundaryClockWindow] = []
    seen = set()
    for cell in cells:
        if not cell.is_affine:
            unresolved.append(
                dict(
                    lower_utc=cell.lower.isoformat(),
                    upper_utc=cell.upper.isoformat(),
                    reason="boundary_clock_wall_cell_not_affine",
                )
            )
            continue
        low_wall, high_wall = cell.wall_range
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
                        lower_utc=cell.lower.isoformat(),
                        upper_utc=cell.upper.isoformat(),
                        reason="boundary_clock_window_not_fully_representable",
                        decade_boundary_index=index,
                    )
                )
                continue
            windows.append(
                dict(
                    lower_utc=cell.lower.isoformat(),
                    upper_utc=cell.upper.isoformat(),
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
                    bracket = cell.inverse(target)
                    if bracket is None:
                        continue
                    lower, upper = bracket
                    key = (lower, upper, gap.instant_utc, index, target)
                    if key in seen:
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
                                direction="顺行" if cell.is_forward else "逆行",
                                reference_jie=cell.reference_term.name,
                                reference_at_utc=cell.reference_timestamp,
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


class DayunBirthEventPayload(TypedDict):
    method_id: Literal["dayun_all_boundary_gap_and_analysis_probes_v4"]
    status: Literal["partial_unresolved_cells", "calculated_probes"]
    range_basis: str
    clock_basis: str
    nominal_month_carry_seconds: int
    guard_probe_offsets_microseconds: list[int]
    events: list[BirthEventRecord]
    probes: list[BirthEventProbeRecord]
    probe_count: int
    future_clock_scan: FutureClockScan
    boundary_clock_scan: BoundaryClockScan
    unresolved_cells: list[UnresolvedBirthEvent]
    unresolved_layers: list[str]
    continuous_completeness_certified: Literal[False]
    physical_precision_certified: Literal[False]
    interpretation_scope: str


@dataclass(frozen=True, kw_only=True)
class DayunBirthEventAssessment:
    payload: DayunBirthEventPayload
    probes: tuple[NatalEventProbe, ...]


def collect_dayun_birth_event_probes(
    template: NormalizedBirthTime,
    start: datetime,
    end: datetime,
    gender: str | None,
    *,
    natal_events: NatalEventPayload,
    analysis_moment: datetime | None = None,
    known_clocks: Mapping[datetime, NormalizedBirthTime] | None = None,
) -> DayunBirthEventAssessment:
    """Probe the selected Jie carry points and the inverse images of Dayun boundaries."""
    low, high = utc_instant(start), utc_instant(end)
    if high < low or high - low > timedelta(minutes=240):
        raise ValueError("大运出生事件需要顺序明确且不超过240分钟的实际范围")
    clocks = dict(known_clocks or {})
    low_day = utc_calendar(low).julian_day_exact()
    high_day = utc_calendar(high).julian_day_exact()

    def clock_at(at: datetime) -> NormalizedBirthTime:
        if at not in clocks:
            clocks[at] = rebase_birth_clock(template, at)
        return clocks[at]

    cuts = {low}
    jie_guards = set()
    events: list[BirthEventRecord] = []
    # note (dayun): Partition raw civil changes separately from the corrected natal clock.
    birth_zone = parse_timezone_name(template.timezone)
    clock_cuts, _ = birth_civil_clock_cuts(birth_zone, low, high, boundary="date")
    clock_scope = (
        "fixed_offset_civil_clock_microsecond"
        if isinstance(birth_zone, timezone)
        else "loaded_civil_clock_integer_utc_second"
    )
    for at, _ in clock_cuts:
        cuts.add(at)
        events.append(
            {
                "kind": "dayun_civil_clock",
                "name": "大运原始民用日期或偏移变更",
                "lower_utc": at.isoformat(),
                "upper_utc": at.isoformat(),
                "at_utc": at.isoformat(),
                "bracket_width_seconds": 0.0,
                "source": {
                    "timezone": template.timezone,
                    "precision_scope": clock_scope,
                },
            }
        )
    for event in natal_events.get("events", []):
        if event["kind"] == "jie":
            for boundary in {event["lower_utc"], event["upper_utc"]}:
                at = utc_instant(datetime.fromisoformat(boundary))
                if low <= at <= high:
                    cuts.add(at)
                    jie_guards.add(at)
    ordered = sorted(cuts | {high})
    intervals = list(zip(ordered, ordered[1:])) or [(low, high)]
    seen = set()
    for left, right in intervals:
        representative = left + (right - left) / 2
        resolution = TimingAnalysis.resolve_dayun_start(
            clock_at(representative).input_datetime, gender, template.timezone
        )
        reference = resolution.target_term
        root = reference.point
        forward = resolution.forward_direction
        left_day = utc_calendar(left).julian_day_exact()
        right_day = utc_calendar(right).julian_day_exact()
        distances = (
            (root.day - right_day, root.day - left_day)
            if forward
            else (left_day - root.day, right_day - root.day)
        )
        first = max(0, distances[0] // Fraction(1, 4))
        last = distances[1] // Fraction(1, 4)
        if last - first > 2:
            raise ValueError("名义月进位跨度异常，不能静默裁剪")
        for index in range(first, last + 1):
            point = CivilPoint(root.day + (-1 if forward else 1) * Fraction(index, 4))
            if not (
                low_day <= point.day <= high_day and left_day <= point.day <= right_day
            ):
                continue
            key = (point.day, root.day, forward)
            if key in seen:
                continue
            seen.add(key)
            lower, upper = point.nominal_calendar_bracket()
            left_label = ZonedCalendar(lower, timezone.utc).require_datetime()
            right_label = ZonedCalendar(upper, timezone.utc).require_datetime()
            cuts.update((left_label, right_label))
            if low <= right_label + timedelta(microseconds=1) <= high:
                cuts.add(right_label + timedelta(microseconds=1))
            events.append(
                {
                    "kind": "dayun_nominal_month_carry",
                    "name": f"{index}个名义月进位",
                    "lower_utc": left_label.isoformat(),
                    "upper_utc": right_label.isoformat(),
                    "at_utc": right_label.isoformat(),
                    "bracket_width_seconds": (right_label - left_label).total_seconds(),
                    "civil_point": point.to_record(),
                    "reference_point": root.to_record(),
                    "bracket_basis": "nominal_gregorian_microsecond_enclosure_v1",
                    "source": {
                        "policy": "three_days_one_year_calendar_v1",
                        "direction": "顺行" if forward else "逆行",
                        "reference_jie": reference.name,
                        "reference_at_utc": utc_instant(reference.moment).isoformat(),
                        "reference_provider": reference.resolution_provider,
                        "precision_scope": "computed_calendar_carry_not_physical_error_bound",
                    },
                }
            )
    future_cuts = cuts | {datetime.fromisoformat(e["at_utc"]) for e in events}
    cells = build_dayun_wall_cells(
        template.timezone, gender, future_cuts, high, clock_at
    )
    # note (dayun): Share the original cells so unrelated probes cannot split inverse brackets.
    future_events, unresolved_cells, future_scan, future_gaps = (
        collect_future_dayun_gap_events(template, analysis_moment, cells)
    )
    analysis_events, analysis_unresolved = collect_dayun_analysis_events(
        template, gender, analysis_moment, cells, clock_at, future_gaps
    )
    events.extend(analysis_events)
    events.extend(future_events)
    unresolved_cells.extend(analysis_unresolved)
    boundary_events, boundary_unresolved, boundary_scan = (
        collect_dayun_boundary_clock_events(template, cells)
    )
    events.extend(boundary_events)
    unresolved_cells.extend(boundary_unresolved)
    events.sort(key=lambda e: (e["at_utc"], e["kind"]))
    instants = set()
    # note (dayun): Keep non-grid Jie guards when the first wall label selects a different reference.
    guard_centers = jie_guards | {
        datetime.fromisoformat(boundary)
        for event in events
        for boundary in (event["lower_utc"], event["upper_utc"])
    }
    for at in guard_centers:
        for displacement in [-1000, -1, 0, 1, 1000]:
            probe = at + timedelta(microseconds=displacement)
            if low <= probe <= high:
                instants.add(probe)
    probes = []
    records: list[BirthEventProbeRecord] = []
    for instant in sorted(instants):
        normalized = clock_at(instant)
        pillars = BaZiCalendar.get_four_pillars(
            normalized.corrected_datetime,
            timezone_name=template.timezone,
            civil_datetime=normalized.input_datetime,
        )
        probes.append(NatalEventProbe(normalized=normalized, pillars=pillars))
        records.append(
            {
                "instant_utc": instant.isoformat(),
                "civil_datetime": normalized.input_datetime.isoformat(),
                "corrected_clock_datetime": normalized.corrected_datetime.isoformat(),
                "pillars": {k: "".join(v) for k, v in pillars.items()},
            }
        )
    return DayunBirthEventAssessment(
        payload={
            "method_id": "dayun_all_boundary_gap_and_analysis_probes_v4",
            "status": (
                "partial_unresolved_cells" if unresolved_cells else "calculated_probes"
            ),
            "range_basis": "elapsed_utc_minutes_about_nominal_reference",
            "clock_basis": "civil_actual_instant_for_dayun_corrected_clock_for_natal",
            "nominal_month_carry_seconds": int(MONTH_CARRY.total_seconds()),
            "guard_probe_offsets_microseconds": [-1000, -1, 0, 1, 1000],
            "events": events,
            "probes": records,
            "probe_count": len(probes),
            "future_clock_scan": future_scan,
            "boundary_clock_scan": boundary_scan,
            "unresolved_cells": unresolved_cells,
            "unresolved_layers": [
                "all_continuous_current_dayun_state_changes",
                "continuous_future_clock_and_boundary_extrema_not_certified",
                "continuous_boundary_extrema_and_near_carry_floating_root_order",
                "birth_record_error_model_and_physical_time_accuracy",
            ],
            "continuous_completeness_certified": False,
            "physical_precision_certified": False,
            "interpretation_scope": "补充民用出生日期、名义月进位、分析时刻、十年闰日裁剪、分析日附近回拨及全部配置十年边界墙钟范围的跳时结束逆像探针；跳时范围扫描也适用于显式年龄，三日一年与公历加法政策不变。探针包络不是连续极值，微秒是派生数值位置，不是出生记录或物理精度。",
        },
        probes=tuple(probes),
    )
