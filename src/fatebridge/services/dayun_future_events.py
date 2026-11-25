"""Invert future civil gap ends through the existing dayun calendar policy."""

from datetime import date, datetime, timezone
from typing import TypedDict

from typing_extensions import NotRequired

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.services.birth_time_events import BirthEventRecord, UnresolvedBirthEvent
from fatebridge.services.dayun_wall_cells import DayunWallCell
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.clock_events import (
    CivilClockFold,
    CivilClockGap,
    backward_clock_folds_near_day,
    clock_scan_bounds,
    forward_clock_gaps_near_day,
)
from fatebridge.utils.solar_time import NormalizedBirthTime
from fatebridge.utils.timezones import parse_timezone_name


class FutureClockScan(TypedDict):
    status: str
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
