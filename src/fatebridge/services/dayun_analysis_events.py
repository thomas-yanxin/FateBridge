"""Actual analysis-instant inverses and decade leap-day clipping probes."""

from calendar import isleap
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.utils.solar_time import NormalizedBirthTime

MICROSECOND = timedelta(microseconds=1)


def _micros(value: timedelta) -> int:
    return (value.days * 86400 + value.seconds) * 1_000_000 + value.microseconds


def collect_dayun_analysis_events(
    template: NormalizedBirthTime,
    gender: Optional[str],
    analysis_moment: Optional[datetime],
    cuts: Iterable[datetime],
    clock_at: Callable[[datetime], NormalizedBirthTime],
) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    ordered = sorted(set(cuts))
    analysis = (
        localize_datetime(analysis_moment, template.timezone).astimezone(timezone.utc)
        if analysis_moment is not None
        else None
    )
    analysis_wall = (
        localize_datetime(analysis, template.timezone).replace(tzinfo=None)
        if analysis is not None
        else None
    )
    events, unresolved = [], []
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
                    reason="analysis_inverse_wall_cell_not_affine",
                )
            )
            continue
        low_wall, high_wall = sorted((wall_a, wall_b))
        targets = []
        for index in range(DEFAULT_DAYUN_PERIODS + 1):
            if analysis_wall is not None:
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
            if not low_wall <= target <= high_wall:
                continue
            quotient, remainder = divmod(_micros(target - wall_a), slope)
            lower = left + MICROSECOND * quotient
            upper = lower + MICROSECOND * bool(remainder)
            key = (kind, index, target, lower, upper)
            if not left <= lower <= upper <= last or key in seen:
                continue
            seen.add(key)
            if kind == "dayun_analysis_moment":
                # The same wall label can select an earlier fold occurrence.
                # Keep only brackets that straddle the actual analysis instant.
                actual = []
                for at in {lower - MICROSECOND, lower, upper, upper + MICROSECOND}:
                    if not left <= at <= last:
                        continue
                    birth, _, wall, _ = TimingAnalysis._dayun_calendar_wall_context(
                        clock_at(at).input_datetime, gender, template.timezone
                    )
                    resolved, _ = TimingAnalysis._resolve_dayun_calendar_boundary(
                        birth, wall, index * 10, template.timezone
                    )
                    actual.append(resolved.astimezone(timezone.utc))
                if (
                    not actual
                    or analysis is None
                    or not min(actual) <= analysis <= max(actual)
                ):
                    continue
            source = dict(
                policy="three_days_one_year_calendar_v1",
                direction="顺行" if forward else "逆行",
                reference_jie=reference["name"],
                reference_at_utc=reference["datetime_with_offset"],
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
