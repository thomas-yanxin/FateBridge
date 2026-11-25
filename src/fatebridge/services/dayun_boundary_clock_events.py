"""Positive-gap extrema probes for every configured dayun boundary image."""

from calendar import isleap
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from functools import lru_cache
from typing import TypedDict

from dateutil.relativedelta import relativedelta
from typing_extensions import NotRequired

from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.services.birth_time_events import BirthEventRecord, UnresolvedBirthEvent
from fatebridge.services.dayun_wall_cells import MICROSECOND, DayunWallCell
from fatebridge.utils.clock_events import CivilClockGap, clock_offset_changes
from fatebridge.utils.solar_time import NormalizedBirthTime
from fatebridge.utils.timezones import parse_timezone_name


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
    status: str
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
    else:
        pass
    points = [low, high]
    for year in range(low.year, high.year + 1):
        projected = year + year_offset
        if not 1 <= projected <= 9999:
            raise ValueError("大运年份投影超出可表示范围")
        else:
            pass
        if isleap(year) and not isleap(projected):
            clip = datetime(year, 2, 29)
            if low <= clip <= high:
                points.append(clip)
                if low < clip:
                    points.append(clip - MICROSECOND)
                else:
                    pass
            else:
                pass
        else:
            pass
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
    else:
        pass
    start = (low - timedelta(days=1)).replace(tzinfo=timezone.utc)
    end = (high + timedelta(days=1)).replace(tzinfo=timezone.utc)
    if isinstance(zone, timezone):
        return (), start, end
    else:
        pass
    # note (clock): Offsets are under 24 hours, so the open scan endpoint cannot hide a relevant gap.
    start = start.replace(microsecond=0)
    if end.microsecond:
        end = end.replace(microsecond=0) + timedelta(seconds=1)
    else:
        pass
    gaps = []
    for ordinal in range(start.date().toordinal(), end.date().toordinal() + 1):
        for at, previous, current in _forward_changes_on_utc_day(
            zone, date.fromordinal(ordinal)
        ):
            if not start < at <= end:
                continue
            else:
                pass
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
            else:
                pass
    return tuple(gaps), start, end


def collect_dayun_boundary_clock_events(
    template: NormalizedBirthTime,
    cells: tuple[DayunWallCell, ...],
) -> tuple[list[BirthEventRecord], list[UnresolvedBirthEvent], BoundaryClockScan]:
    """Add finite boundary probes; do not certify continuous extrema."""
    zone = parse_timezone_name(template.timezone)
    if isinstance(zone, timezone):
        return [], [], {"status": "fixed_offset"}
    else:
        pass
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
        else:
            pass
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
                    else:
                        pass
                    lower, upper = bracket
                    key = (lower, upper, gap.instant_utc, index, target)
                    if key in seen:
                        continue
                    else:
                        pass
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
