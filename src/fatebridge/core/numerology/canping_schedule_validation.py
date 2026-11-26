"""Shared schedule validation for Canping outputs."""

from __future__ import annotations

from pydantic import ValidationError

from fatebridge.core.contracts.output_chinese import (
    CanpingRow,
    CanpingSeries,
    CanpingTiming,
)
from fatebridge.core.numerology.timing import (
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
    if actual is None or expected is None:
        return True
    if isinstance(actual, dict) and isinstance(expected, dict):
        return all(
            _known_facts_agree(actual[key], expected[key])
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
    """Bind present schedule facts without requiring legacy Fraction/year_boundaries."""
    context = series.solar_context if series is not None else None
    if context is not None and timing.solar_year_context is not None:
        if not _known_facts_agree(
            context.model_dump(exclude_unset=True),
            timing.solar_year_context.model_dump(exclude_unset=True),
        ):
            raise ValueError("配运上下文与同次实际年序不一致。")
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
        if row.status == "active" and row.dayun_index is not None:
            period = period_by_index.get(row.dayun_index)
            if period is None:
                if periods is not None and all(p.index is not None for p in periods):
                    raise ValueError("年内分段引用了不存在的实际大运。")
                continue
            for actual, expected in (
                (row.dayunBranch, period.branch),
                (row.dayun_pillar, period.pillar),
            ):
                if actual is not None and expected is not None and actual != expected:
                    raise ValueError("年序大运身份与实际大运不一致。")
    selected = timing.selected
    if selected is None or selected.at is None:
        return
    at = ZonedCalendar.from_isoformat(selected.at).utc.julian_day_exact()
    if selected.start_at is not None:
        if at < ZonedCalendar.from_isoformat(selected.start_at).utc.julian_day_exact():
            raise ValueError("查询时刻早于所选区间起点。")
    if selected.end_at is not None:
        if at >= ZonedCalendar.from_isoformat(selected.end_at).utc.julian_day_exact():
            raise ValueError("查询时刻不早于所选区间终点。")
    if selected.year is not None and series.rows:
        match_row = next((r for r in series.rows if r.year == selected.year), None)
        if (
            match_row is not None
            and selected.ganzhi is not None
            and match_row.ganzhi is not None
        ):
            if selected.ganzhi != match_row.ganzhi:
                raise ValueError("查询年份与实际年序干支不一致。")


def require_schedule_binding(
    result: dict,
    *,
    parsed: (
        tuple[CanpingTiming, CanpingSeries | None, list[CanpingRow] | None] | None
    ) = None,
) -> None:
    """Validate present receipts before transport projection."""
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
