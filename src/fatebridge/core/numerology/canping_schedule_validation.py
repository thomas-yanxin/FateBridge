"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from pydantic import ValidationError

from fatebridge.core.contracts.output_chinese import (
    CanpingRow,
    CanpingSeries,
    CanpingTiming,
)
from fatebridge.core.numerology.canping_schedule_basis import (
    APPLIED,
    LEGACY,
    build_schedule_basis,
)
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.json_values import same_value


def _registered_facts_match(actual: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _registered_facts_match(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_registered_facts_match(a, e) for a, e in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def _known_facts_agree(actual: object, expected: object) -> bool:
    """Compare shared facts; an explicitly null civil cap is a known fact."""
    if actual is None or expected is None:
        return True
    if isinstance(actual, dict) and isinstance(expected, dict):
        return all(
            (
                actual[key] is expected[key]
                if key == "excluded_before"
                and (actual[key] is None or expected[key] is None)
                else _known_facts_agree(actual[key], expected[key])
            )
            for key in actual.keys() & expected.keys()
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _known_facts_agree(a, e) for a, e in zip(actual, expected)
        )
    return type(actual) is type(expected) and actual == expected


def _require_interval_binding(
    timing: CanpingTiming,
    series: CanpingSeries | None,
    periods: list[CanpingRow] | None,
    clock: object,
) -> None:
    """Bind present numerical intervals to the actual same-run schedule.

    This checks retained facts, never solves another solar event or rebuilds a
    known event from its JSON receipt. The ordinary-label cap affects display;
    only the point coordinate defines schedule membership.
    """
    context = series.solar_context if series is not None else None
    if context is not None and timing.solar_year_context is not None:
        if not _known_facts_agree(
            context.model_dump(exclude_unset=True),
            timing.solar_year_context.model_dump(exclude_unset=True),
        ):
            raise ValueError("配运上下文与同次实际年序不一致。")
    if series is not None and (
        timing.comparison_policy is not None
        and series.comparison_policy is not None
        and timing.comparison_policy != series.comparison_policy
    ):
        raise ValueError("查询与年序的主点比较政策不一致。")
    birth_labels = [timing.birth_at]
    birth_labels.extend(
        value.birth_instant_utc
        for value in (context, timing.solar_year_context)
        if value is not None
    )
    if isinstance(clock, dict):
        birth_labels.append(
            clock.get("birth_instant_utc") or clock.get("civil_datetime")
        )
        zone = clock.get("timezone_spec")
        if zone is not None:
            for actual in (
                timing.timezone,
                context.timezone if context is not None else None,
            ):
                if actual is not None and actual != zone:
                    raise ValueError("配运时区与同次出生钟制不一致。")
    known_births = [
        ZonedCalendar.from_isoformat(label).utc.julian_day_exact()
        for label in birth_labels
        if isinstance(label, str)
    ]
    if known_births and any(day != known_births[0] for day in known_births[1:]):
        raise ValueError("配运出生裁剪与同次实际出生瞬间不一致。")
    if timing.birth_at is not None and context is not None:
        if context.origin_civil_year is not None:
            if ZonedCalendar.from_isoformat(timing.birth_at).local_parts[0] != (
                context.origin_civil_year
            ):
                raise ValueError("立春派生来源的出生民用年与实际钟面不一致。")
    if series is None:
        return
    period_by_index = {
        period.index: period for period in periods or [] if period.index is not None
    }
    if periods is not None and len(period_by_index) != len(
        [period for period in periods if period.index is not None]
    ):
        raise ValueError("实际大运序号重复。")
    for row in series.rows or []:
        for segment in row.segments or []:
            start = segment.start_point.known_day() if segment.start_point else None
            end = segment.end_point.known_day() if segment.end_point else None
            if segment.status == "not_started" and periods:
                first = periods[0].start_point
                first_day = first.known_day() if first is not None else None
                if first_day is not None and end is not None and end > first_day:
                    raise ValueError("未起运分段越过实际首运起点。")
            if segment.status != "active" or segment.dayun_index is None:
                continue
            period = period_by_index.get(segment.dayun_index)
            if period is None:
                if periods is not None and all(p.index is not None for p in periods):
                    raise ValueError("年内分段引用了不存在的实际大运。")
                continue
            for actual, expected in (
                (segment.dayunBranch, period.branch),
                (segment.dayun_pillar, period.pillar),
            ):
                if actual is not None and expected is not None and actual != expected:
                    raise ValueError("年内分段的大运身份与实际大运不一致。")
            lower = period.start_point.known_day() if period.start_point else None
            upper = period.end_point.known_day() if period.end_point else None
            if (start is not None and lower is not None and start < lower) or (
                end is not None and upper is not None and end > upper
            ):
                raise ValueError("活动分段超出所引实际大运的数值区间。")
        if row.segments is not None and len(row.segments) == 1:
            if not _known_facts_agree(
                row.model_dump(exclude_unset=True),
                row.segments[0].model_dump(exclude_unset=True),
            ):
                raise ValueError("单段年序摘要与实际分段不一致。")
    selected = timing.selected
    if selected is None:
        return
    boundaries = {
        boundary.year: boundary
        for boundary in series.year_boundaries or []
        if boundary.year is not None
    }
    if selected.year is not None:
        for selected_boundary, year in (
            (selected.year_start_boundary, selected.year),
            (selected.year_end_boundary, selected.year + 1),
        ):
            matching_boundary = boundaries.get(year)
            if selected_boundary is not None and matching_boundary is not None:
                if not _known_facts_agree(
                    selected_boundary.model_dump(exclude_unset=True),
                    matching_boundary.model_dump(exclude_unset=True),
                ):
                    raise ValueError("查询立春收据与同次实际年界不一致。")
    if selected.at is None or series.rows is None:
        return
    at = ZonedCalendar.from_isoformat(selected.at).utc.julian_day_exact()
    complete_rows = True
    match = None
    for row in series.rows:
        lower = row.start_point.known_day() if row.start_point else None
        upper = row.end_point.known_day() if row.end_point else None
        if lower is None or upper is None:
            complete_rows = False
        elif lower <= at < upper:
            match = row
            break
    if match is None:
        if complete_rows:
            raise ValueError("查询时刻不在同次实际年序的半开范围内。")
        return
    for selected_fact, matching_fact in (
        (selected.year, match.year),
        (selected.ganzhi, match.ganzhi),
    ):
        if (
            selected_fact is not None
            and matching_fact is not None
            and selected_fact != matching_fact
        ):
            raise ValueError("查询年份与数值时刻所属的实际年序不一致。")
    if match.segments is None:
        return
    complete_segments = True
    for segment in match.segments:
        lower = segment.start_point.known_day() if segment.start_point else None
        upper = segment.end_point.known_day() if segment.end_point else None
        if lower is None or upper is None:
            complete_segments = False
        elif lower <= at < upper:
            if not _known_facts_agree(
                selected.model_dump(exclude_unset=True),
                segment.model_dump(exclude_unset=True),
            ):
                raise ValueError("查询所选区间或条文与实际年内分段不一致。")
            return
    if complete_segments:
        raise ValueError("查询时刻没有对应的实际年内分段。")


def require_schedule_binding(
    result: dict,
    *,
    parsed: (
        tuple[CanpingTiming, CanpingSeries | None, list[CanpingRow] | None] | None
    ) = None,
) -> None:
    """Validate present receipts before transport projection can hide a conflict.

    Missing context in a partial library result remains unknown. Where the
    actual timing and birth clock are present, compare against those facts;
    internal agreement of a forged source map is insufficient.
    """

    timing = result.get("canping_timing")
    if not isinstance(timing, dict) or timing.get("schedule_basis") is None:
        return
    basis = timing["schedule_basis"]
    try:
        if not isinstance(basis, dict):
            raise ValueError("配运回执必须为对象。")
        profile = timing.get("profile_id")
        if (
            profile is not None
            and basis.get("profile_id") is not None
            and profile != basis["profile_id"]
        ):
            raise ValueError("配运回执的方法与同次计算不符。")
        rows = result.get("dayun")
        if (
            isinstance(rows, list)
            and not rows
            and any(
                timing.get(key) is not None for key in ("first_row", "first_period")
            )
        ):
            raise ValueError("实际配运序为空，不能保留非空首行或首运摘要。")
        if isinstance(rows, list) and rows:
            # Compare against the actual calculation, not just two internally
            # agreeing summaries. This also checks text, column, numbers, ages
            # and both boundaries before projection can remove the full rows.
            for key in ("first_row", "first_period"):
                if key not in timing:
                    continue
                expected_row = (
                    None if key == "first_period" and profile == LEGACY else rows[0]
                )
                if not same_value(timing[key], expected_row):
                    raise ValueError("首行或首运摘要与同次实际配运行不一致。")
        evidence = result.get("numerology_evidence")
        clock = evidence.get("birth_clock") if isinstance(evidence, dict) else None
        actual_series = result.get("liunian_series")
        if parsed is None:
            parsed_timing = CanpingTiming.model_validate(timing)
            series = (
                CanpingSeries.model_validate(actual_series)
                if actual_series is not None
                else None
            )
            periods = (
                [CanpingRow.model_validate(row) for row in rows]
                if isinstance(rows, list)
                else None
            )
        else:
            parsed_timing, series, periods = parsed
        _require_interval_binding(parsed_timing, series, periods, clock)
        mapping_keys = (
            {"calendar_scope"}
            if profile == LEGACY
            else {
                "calendar_policy",
                "reference_policy",
                "boundary_policy",
                "dst_policy",
            }
        )
        if (
            profile in APPLIED
            and isinstance(clock, dict)
            and mapping_keys <= timing.keys()
        ):
            expected = build_schedule_basis(profile, timing, clock)
            if not _registered_facts_match(basis, expected):
                raise ValueError("配运回执与同次实际政策或钟面不符。")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise NumerologySourceError(
            "runtime_canping_schedule_binding_conflict"
        ) from exc
