"""Invert future civil gap ends through the existing dayun calendar policy."""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.utils.clock_events import (
    CivilClockFold,
    CivilClockGap,
    backward_clock_folds_near_day,
    clock_scan_bounds,
    forward_clock_gaps_near_day,
)
from fatebridge.utils.solar_time import NormalizedBirthTime
from fatebridge.utils.timezones import parse_timezone_name


def _micros(delta: timedelta) -> int:
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def collect_future_dayun_gap_events(
    template: NormalizedBirthTime,
    gender: Optional[str],
    analysis_moment: Optional[datetime],
    cuts: Iterable[datetime],
    clock_at: Callable[[datetime], NormalizedBirthTime],
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]], Dict[str, Any]]:
    """Retain calculated inverse brackets; never certify continuous coverage."""
    if analysis_moment is None:
        return [], [], {"status": "not_applicable_explicit_age"}
    zone = parse_timezone_name(template.timezone)
    if isinstance(zone, timezone):
        return [], [], {"status": "fixed_offset"}
    analysis = localize_datetime(analysis_moment, template.timezone).astimezone(
        timezone.utc
    )
    try:
        scan_low, scan_high = clock_scan_bounds(analysis.date())
        gaps = forward_clock_gaps_near_day(zone, analysis.date())
        folds = backward_clock_folds_near_day(zone, analysis.date())
    except (ValueError, OverflowError):
        return (
            [],
            [{"reason": "future_clock_window_not_fully_representable"}],
            {
                "status": "unavailable_clock_window",
                "continuous_completeness_certified": False,
            },
        )
    scan = {
        "status": "calculated",
        "timezone": template.timezone,
        "analysis_utc_day": analysis.date().isoformat(),
        "scan_start_utc": scan_low.isoformat(),
        "scan_end_utc": scan_high.isoformat(),
        "forward_gap_count": len(gaps),
        "backward_fold_count": len(folds),
        "scan_step_seconds": 1,
        "continuous_completeness_certified": False,
        "physical_precision_certified": False,
    }
    if not gaps and not folds:
        return [], [], scan
    ordered = sorted(set(cuts))
    events: list[Dict[str, Any]] = []
    unresolved: list[Dict[str, Any]] = []
    seen = set()
    for left, right in zip(ordered, ordered[1:]):
        last = max(left, right - timedelta(microseconds=1))
        birth_a, details_a, wall_a, offset_a = (
            TimingAnalysis._dayun_calendar_wall_context(
                clock_at(left).input_datetime, gender, template.timezone
            )
        )
        birth_b, details_b, wall_b, offset_b = (
            TimingAnalysis._dayun_calendar_wall_context(
                clock_at(last).input_datetime, gender, template.timezone
            )
        )
        forward = details_a["forward_direction"]
        slope = -119 if forward else 121
        reference = details_a["reference_term"]
        affine = (
            details_b["forward_direction"] == forward
            and details_b["reference_term"]["datetime_with_offset"]
            == reference["datetime_with_offset"]
            and birth_a.date() == birth_b.date()
            and birth_a.utcoffset() == birth_b.utcoffset()
            and (offset_a["years"], offset_a["months"])
            == (offset_b["years"], offset_b["months"])
            and _micros(wall_b - wall_a) == slope * _micros(last - left)
        )
        if not affine:
            unresolved.append(
                {
                    "lower_utc": left.isoformat(),
                    "upper_utc": right.isoformat(),
                    "reason": "dayun_wall_cell_not_affine_under_declared_partition",
                }
            )
            continue
        changes: Tuple[CivilClockGap | CivilClockFold, ...] = (*gaps, *folds)
        for gap in changes:
            fold = gap.offset_after_seconds < gap.offset_before_seconds
            change_name = "fold" if fold else "gap"
            for index in range(DEFAULT_DAYUN_PERIODS + 1):
                targets = TimingAnalysis._dayun_wall_year_preimages(
                    gap.upper_wall, index * 10
                )
                for target in targets:
                    if not min(wall_a, wall_b) <= target <= max(wall_a, wall_b):
                        continue
                    quotient, remainder = divmod(_micros(target - wall_a), slope)
                    lower = left + timedelta(microseconds=quotient)
                    upper = lower + timedelta(microseconds=bool(remainder))
                    key = (lower, upper, gap.instant_utc, index, target)
                    if not left <= lower <= upper <= last or key in seen:
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
                                "direction": "顺行" if forward else "逆行",
                                "reference_jie": reference["name"],
                                "reference_at_utc": reference["datetime_with_offset"],
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
    return events, unresolved, scan
