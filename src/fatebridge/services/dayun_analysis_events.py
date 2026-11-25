"""Actual analysis-instant inverses and decade leap-day clipping probes."""

from calendar import isleap
from datetime import datetime

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.services.birth_time_events import BirthEventRecord, UnresolvedBirthEvent
from fatebridge.services.dayun_wall_cells import (
    MICROSECOND,
    BirthClockAtInstant,
    DayunWallCell,
)
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.clock_events import CivilClockGap
from fatebridge.utils.solar_time import NormalizedBirthTime


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
