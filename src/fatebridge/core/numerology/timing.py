"""Named Canping luck schedules with lazy Lichun evaluation and compact output."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from dateutil.relativedelta import relativedelta

from fatebridge.core.almanac import get_bazi_year, localize_datetime
from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.core.numerology.canping import _verses, _year_ganzhi, compute_number
from fatebridge.core.numerology.solar import (
    ResolvedProjectionBoundary,
    boundary_context,
    resolve_projection_boundary,
)
from fatebridge.utils.civil_time import (
    CivilPoint,
    UTCCalendar,
    ZonedCalendar,
    parse_civil_iso_clock,
    utc_calendar,
)
from fatebridge.utils.errors import NumerologySourceError, ParameterError
from fatebridge.utils.timezones import parse_timezone_name

APPENDIX = "bazi_appendix_v1"
CONTINUOUS = "bazi_continuous_v1"
LEGACY = "legacy_minggong_v1"

COLLATION_PATH = (
    Path(__file__).resolve().parents[2] / "data/canping/schedule-basis-v1.json"
)
POLICY_ID = "canping_schedule_source_mapping_v1"
APPLIED = {
    APPENDIX: ["appendix_month_order", "appendix_integer_rounding"],
    CONTINUOUS: ["appendix_month_order"],
    LEGACY: [],
}
SUMMARIES = MappingProxyType(
    {
        APPENDIX: "卷七月柱顺逆及三日整日借除；民用日差与半开区间映射。",
        CONTINUOUS: "月柱顺逆及现代连续折算。",
        LEGACY: "继承命宫顺排、一岁起运（仅年标签）。",
    }
)


def clause_role(profile: str, clause: dict[str, Any]) -> str:
    if clause["id"] in APPLIED[profile]:
        return "applied_rule"
    if clause["source_id"] == "sanming_nlc":
        return (
            "supplementary_ziping_background"
            if profile != LEGACY
            else "comparison_not_applied"
        )
    if profile == LEGACY:
        return "comparison_not_applied"
    if clause["kind"] in {"attribution", "method_distinction"}:
        return "source_context"
    return "comparison_not_applied"


def clock_policy_for_rules(rules: dict[str, Any]) -> str | None:
    database = rules.get("database")
    if database is None:
        return None
    if database == "explicit_fixed_offset":
        return "explicit_fixed_offset_assumption; no_regional_future_rules"
    if database == "pytz":
        return "pinned_regional_rules; subject_to_future_legislation"
    raise ValueError("参评时区规则提供方未登记。")


@lru_cache(maxsize=1)
def _schedule_collation() -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(COLLATION_PATH.read_bytes())
        return data
    except (OSError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_canping_schedule_collation") from exc


def source_readings() -> dict[str, Any]:
    return deepcopy(_schedule_collation())


def reading_source_citations(profile: str) -> list[dict[str, Any]]:
    if profile not in APPLIED:
        raise ValueError("未登记的参评配运方法。")
    data = _schedule_collation()
    result = []
    for source_id in data["sources"]:
        clauses = [c for c in data["clauses"] if c["source_id"] == source_id]
        result.append(
            {
                "source_id": source_id,
                "pdf_pages": sorted({c["pdf_page"] for c in clauses}),
                "roles": list(dict.fromkeys(clause_role(profile, c) for c in clauses)),
            }
        )
    return result


def date_mapping_statement(
    profile: str, future_clock_policy: str | None, timezone_spec: str | None
) -> str:
    if profile not in APPLIED:
        raise ValueError("未登记的参评配运方法。")
    if profile == LEGACY:
        return "旧命宫方案仅有年龄标签，无已核实际起止日期。"
    if not isinstance(timezone_spec, str) or not timezone_spec.strip():
        raise ValueError("日期条件需要同次实际时区记录。")
    if (
        future_clock_policy
        == "explicit_fixed_offset_assumption; no_regional_future_rules"
    ):
        return f"日期按显式固定偏移{timezone_spec}映射。"
    if future_clock_policy == "pinned_regional_rules; subject_to_future_legislation":
        return f"日期按封存的{timezone_spec}地区规则映射。"
    raise ValueError("日期条件缺少已登记的同次钟制政策。")


def build_reading_context(
    profile: str, future_clock_policy: str, timezone_spec: str
) -> dict[str, Any]:
    return {
        "profile_id": profile,
        "future_clock_policy": future_clock_policy,
        "timezone_spec": timezone_spec,
        "date_mapping_statement": date_mapping_statement(
            profile, future_clock_policy, timezone_spec
        ),
        "source_citations": reading_source_citations(profile),
    }


def build_schedule_basis(profile: str, timing: dict, clock: dict) -> dict[str, Any]:
    if profile not in APPLIED or timing.get("profile_id") != profile:
        raise NumerologySourceError("runtime_canping_schedule_profile_conflict")
    data = _schedule_collation()
    mapping = (
        {
            "calendar_policy": timing["calendar_policy"],
            "reference_policy": timing["reference_policy"],
            "boundary_policy": timing["boundary_policy"],
            "dst_policy": timing["dst_policy"],
        }
        if profile != LEGACY
        else {"calendar_policy": timing["calendar_scope"]}
    )
    try:
        clock_policy = clock_policy_for_rules(clock["timezone_rules"])
    except (TypeError, ValueError) as exc:
        raise NumerologySourceError(
            "runtime_canping_schedule_binding_conflict"
        ) from exc
    if clock_policy is None:
        raise NumerologySourceError("runtime_canping_schedule_binding_conflict")
    return {
        "policy_id": POLICY_ID,
        "profile_id": profile,
        "applied_clause_ids": list(APPLIED[profile]),
        "has_actual_date_mapping": profile != LEGACY,
        "actual_start_at": timing.get("start_at"),
        "timezone_spec": clock["timezone_spec"],
        "future_clock_policy": clock_policy,
    }


@dataclass(frozen=True)
class ResolvedCanpingInterval:
    """A numerical interval and its display labels."""

    start: CivilPoint
    end: CivilPoint
    start_label: ZonedCalendar
    end_label: ZonedCalendar
    year: int
    facts: dict[str, object]
    year_start_boundary: ResolvedProjectionBoundary
    year_end_boundary: ResolvedProjectionBoundary

    def to_record(self) -> dict[str, object]:
        return {
            "start_at": self.start_label.isoformat(),
            "end_at": self.end_label.isoformat(),
            **self.facts,
        }


@dataclass(frozen=True)
class ResolvedAnnualSeries:
    record: dict[str, object]
    intervals: tuple[ResolvedCanpingInterval, ...]


def _utc(moment: datetime) -> UTCCalendar:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("配运和查询必须使用带时区的时刻。")
    return utc_calendar(moment)


def appendix_age(
    birth: datetime, reference: datetime | ZonedCalendar
) -> dict[str, Any]:
    """Literal three-day grouping: remainder one discarded, remainder two lent."""
    birth_clock = ZonedCalendar.from_datetime(birth)
    reference_clock = (
        reference
        if isinstance(reference, ZonedCalendar)
        else ZonedCalendar.from_datetime(reference)
    )
    days = abs(
        ZonedCalendar(reference_clock.utc, birth_clock.zone).local_ordinal
        - birth.toordinal()
    )
    return {
        "civil_days_to_reference": days,
        "whole_years": (days + 1) // 3,
        "discarded_days": 1 if days % 3 == 1 else 0,
        "borrowed_days": 1 if days % 3 == 2 else 0,
        "policy": "civil_date_difference; remainder_1_discarded_remainder_2_borrowed",
    }


def luck_timeline(
    birth: datetime, gender: str, month_pillar: tuple[str, str], zone: str, method: str
) -> dict[str, Any]:
    if method not in {APPENDIX, CONTINUOUS}:
        raise ValueError("日期配运方法必须为bazi_appendix_v1或bazi_continuous_v1。")
    _utc(birth)
    if gender not in {"男", "女"}:
        raise ValueError("参评配运方向需要明确gender为男或女，不能默认性别。")
    birth = localize_datetime(birth, zone)
    if method == CONTINUOUS:
        timeline = TimingAnalysis.calculate_dayun_timeline(
            birth, gender, month_pillar, zone, periods=12
        )
        timeline["profile_id"] = method
        timeline.setdefault(
            "calendar_policy",
            "360_nominal_days_to_year_30_to_month_then_civil_addition",
        )
        timeline.setdefault(
            "reference_policy",
            "next_jie_strict_for_forward_previous_jie_inclusive_for_reverse",
        )
        timeline.setdefault("dst_policy", "fold_0_gap_forward")
        return timeline
    resolution = TimingAnalysis.resolve_dayun_start(birth, gender, zone)
    term = resolution.target_term
    if not term.has_defined_local_clock:
        raise ParameterError(
            f"参评附法需要{term.name}的当地日期，时区规则未定义该时点的当地钟时。",
            [
                {
                    "path": "request.dayun_method",
                    "code": "undefined_canping_reference_date",
                }
            ],
        )
    start_details = resolution.to_details()
    reference = term.calendar
    offset = appendix_age(birth, reference)
    details = {
        **{
            k: start_details[k]
            for k in (
                "forward_direction",
                "year_stem",
                "reference_term",
                "reference_term_resolution",
                "elapsed_seconds",
            )
        },
        "reference_at": reference.isoformat(),
        "start_age_years": offset["whole_years"],
        "within_day_fraction_used": False,
    }
    start_wall = birth.replace(tzinfo=None) + relativedelta(years=offset["whole_years"])
    periods = TimingAnalysis.calculate_dayun_sequence(
        *month_pillar,
        gender,
        details["year_stem"],
        periods=12,
        start_age=offset["whole_years"],
    )
    boundary, preserve_birth = TimingAnalysis._resolve_dayun_calendar_boundary(
        birth, start_wall, 0, zone
    )
    for index, row in enumerate(periods, start=1):
        row["start_at"] = boundary.isoformat()
        boundary, _ = TimingAnalysis._resolve_dayun_calendar_boundary(
            birth, start_wall, 10 * index, zone
        )
        row["end_at"] = boundary.isoformat()
    return {
        "profile_id": method,
        "method_id": "ziping_month_pillar_three_day_rounding_v1",
        "birth_at": birth.isoformat(),
        "timezone": zone,
        "start_at": periods[0]["start_at"],
        "calendar_offset": offset,
        "calendar_policy": offset["policy"]
        + "; integer_years_added_to_birth_civil_clock",
        "reference_policy": "next_jie_strict_for_forward_previous_jie_inclusive_for_reverse",
        "boundary_policy": "start_inclusive_end_exclusive",
        "dst_policy": (
            "fold_0_gap_forward_initial_birth_preserved"
            if preserve_birth
            else "fold_0_gap_forward"
        ),
        "periods": periods,
    }


def _active_segment(
    period: dict | None, element: str, taisui: str, *, include_verses: bool = True
) -> dict[str, object]:
    if period is None:
        return {"status": "not_started"}
    numbers = compute_number(taisui, period["branch"], element)
    data: dict[str, object] = {
        "status": "active",
        "dayun_index": period["index"],
        "dayunBranch": period["branch"],
        "dayun_pillar": period["pillar"],
        "numShun": numbers["numShun"],
        "numNi": numbers["numNi"],
    }
    if include_verses:
        data.update(numbers)
        data["verses"] = _verses(element, numbers, "luck", compact=True)
    return data


def _compact_liunian_rows(
    birth_year: int,
    periods: list[dict],
    element: str,
    horizon: int,
    birth_civil_year: int,
) -> list[dict[str, Any]]:
    """Build lightweight 120-year rows without solving 121 solar roots."""
    parsed_periods = [
        (
            ZonedCalendar.from_isoformat(p["start_at"]).local_parts[0],
            ZonedCalendar.from_isoformat(p["end_at"]).local_parts[0],
            p,
        )
        for p in periods
    ]
    rows: list[dict[str, Any]] = []
    for index in range(horizon):
        year = birth_year + index
        ganzhi = _year_ganzhi(year)
        period = next(
            (p for lo, hi, p in parsed_periods if lo <= year < hi),
            None,
        )
        row: dict[str, Any] = {
            "age": index + 1,
            "year": year,
            "ganzhi": ganzhi,
        }
        if period is None:
            row["status"] = "not_started"
        else:
            numbers = compute_number(ganzhi[1], period["branch"], element)
            row.update(
                {
                    "dayunBranch": period["branch"],
                    "numShun": numbers["numShun"],
                    "numNi": numbers["numNi"],
                }
            )
        rows.append(row)
    return rows


def resolve_annual_series(
    birth: datetime, zone: str, periods: list[dict], element: str, horizon: int = 120
) -> ResolvedAnnualSeries:
    """Resolve explicit Lichun intervals across the requested horizon."""
    if type(horizon) is not int or not 1 <= horizon <= 120:
        raise ValueError("年序范围须为1至120。")
    birth_year = get_bazi_year(birth, zone)
    birth_label = ZonedCalendar.from_datetime(birth)
    birth_point = CivilPoint(birth_label.utc.julian_day_exact())
    origin_year = ZonedCalendar(birth_label.utc, parse_timezone_name(zone)).local_parts[
        0
    ]
    boundaries = [
        resolve_projection_boundary(
            year,
            zone,
            origin_civil_year=origin_year,
            origin_bazi_year=birth_year,
            horizon=horizon,
        )
        for year in range(birth_year, birth_year + horizon + 1)
    ]
    resolved = [
        (
            CivilPoint(
                ZonedCalendar.from_isoformat(p["start_at"]).utc.julian_day_exact()
            ),
            ZonedCalendar.from_isoformat(p["start_at"]),
            CivilPoint(
                ZonedCalendar.from_isoformat(p["end_at"]).utc.julian_day_exact()
            ),
            ZonedCalendar.from_isoformat(p["end_at"]),
            p,
        )
        for p in periods
    ]
    rows = []
    intervals = []
    for index, year in enumerate(range(birth_year, birth_year + horizon)):
        previous, following = boundaries[index : index + 2]
        if birth_point.day >= previous.term.point.day:
            start, start_label = birth_point, birth_label
        else:
            start, start_label = previous.term.point, previous.term.calendar
        end, end_label = following.term.point, following.term.calendar
        cuts = {start.day: (start, start_label), end.day: (end, end_label)}
        for a, a_label, b, b_label, _ in resolved:
            if start.day < a.day < end.day:
                cuts[a.day] = (a, a_label)
            if start.day < b.day < end.day:
                cuts[b.day] = (b, b_label)
        ordered = [cuts[key] for key in sorted(cuts)]
        ganzhi = _year_ganzhi(year)
        segments = []
        for (a, a_label), (b, b_label) in zip(ordered, ordered[1:]):
            period = next(
                (p for lo, _, hi, _, p in resolved if lo.day <= a.day < hi.day),
                None,
            )
            if period is None and a.day >= resolved[0][0].day:
                raise ValueError("配运时间轴未覆盖请求年序；不能沿用最后一运。")
            interval = ResolvedCanpingInterval(
                a,
                b,
                a_label,
                b_label,
                year,
                _active_segment(period, element, ganzhi[1], include_verses=False),
                previous,
                following,
            )
            intervals.append(interval)
            segments.append(interval.to_record())
        row: dict[str, object] = {
            "age": year - birth_year + 1,
            "year": year,
            "ganzhi": ganzhi,
            "taisuiBranch": ganzhi[1],
            "start_at": start_label.isoformat(),
            "end_at": end_label.isoformat(),
            "status": "split" if len(segments) > 1 else segments[0]["status"],
        }
        if len(segments) == 1:
            row.update(
                {
                    k: v
                    for k, v in segments[0].items()
                    if k not in {"start_at", "end_at", "status"}
                }
            )
        else:
            row["segments"] = segments
        rows.append(row)
    record: dict[str, object] = {
        "element": element,
        "rows": rows,
        "year_boundary": "lichun",
        "birth_pillar_year": birth_year,
        "age_policy": "sexagenary_year_ordinal; not_elapsed_age_or_lunar_new_year_age",
        "solar_context": boundary_context(
            birth,
            zone,
            birth_year,
            horizon,
            [b.to_record() for b in boundaries],
        ),
    }
    return ResolvedAnnualSeries(record, tuple(intervals))


def _resolve_queried_interval(
    *,
    birth: datetime,
    zone: str,
    periods: list[dict],
    element: str,
    analysis_datetime: str,
    horizon: int = 120,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve Lichun boundaries lazily ONLY for the queried analysis_datetime year."""
    query = parse_civil_iso_clock(analysis_datetime.replace("Z", "+00:00"))
    if not isinstance(query, UTCCalendar):
        raise ValueError("analysis_datetime须为带时区的ISO时刻。")
    tz = parse_timezone_name(zone)
    query_clock = ZonedCalendar(query, tz)
    query_day = query_clock.utc.julian_day_exact()
    birth_label = ZonedCalendar.from_datetime(birth)
    birth_day = birth_label.utc.julian_day_exact()
    if query_day < birth_day:
        raise ValueError("查询时刻不能早于出生时刻。")

    birth_year = get_bazi_year(birth, zone)
    origin_year = ZonedCalendar(birth_label.utc, tz).local_parts[0]
    query_civil_year = query_clock.local_parts[0]

    # Determine which Lichun year [match_year, match_year+1) contains query_day.
    if not birth_year <= query_civil_year <= birth_year + horizon:
        if query_civil_year < birth_year:
            raise ValueError("查询时刻不能早于出生时刻。")
        raise ValueError("查询时刻超出本次年序范围；不外推。")

    # Solve Lichun for query_civil_year (1 boundary call) to tell before vs after Lichun.
    pivot = resolve_projection_boundary(
        query_civil_year,
        zone,
        origin_civil_year=origin_year,
        origin_bazi_year=birth_year,
        horizon=horizon,
    )
    if query_day < pivot.term.point.day:
        match_year = query_civil_year - 1
        end_boundary = pivot
        if not birth_year <= match_year < birth_year + horizon:
            raise ValueError("查询时刻超出本次年序范围；不外推。")
        start_boundary = resolve_projection_boundary(
            match_year,
            zone,
            origin_civil_year=origin_year,
            origin_bazi_year=birth_year,
            horizon=horizon,
        )
    else:
        match_year = query_civil_year
        start_boundary = pivot
        if not birth_year <= match_year < birth_year + horizon:
            raise ValueError("查询时刻超出本次年序范围；不外推。")
        end_boundary = resolve_projection_boundary(
            match_year + 1,
            zone,
            origin_civil_year=origin_year,
            origin_bazi_year=birth_year,
            horizon=horizon,
        )

    year_start_day = max(birth_day, start_boundary.term.point.day)
    year_start_label = (
        birth_label
        if birth_day >= start_boundary.term.point.day
        else start_boundary.term.calendar
    )
    year_end_day = end_boundary.term.point.day
    year_end_label = end_boundary.term.calendar

    resolved_periods = [
        (
            ZonedCalendar.from_isoformat(p["start_at"]).utc.julian_day_exact(),
            ZonedCalendar.from_isoformat(p["start_at"]),
            ZonedCalendar.from_isoformat(p["end_at"]).utc.julian_day_exact(),
            ZonedCalendar.from_isoformat(p["end_at"]),
            p,
        )
        for p in periods
    ]
    cuts = {
        year_start_day: year_start_label,
        year_end_day: year_end_label,
    }
    for a_day, a_lbl, b_day, b_lbl, _ in resolved_periods:
        if year_start_day < a_day < year_end_day:
            cuts[a_day] = a_lbl
        if year_start_day < b_day < year_end_day:
            cuts[b_day] = b_lbl
    ordered_days = sorted(cuts)
    seg_start_day = year_start_day
    seg_end_day = year_end_day
    for a_day, b_day in zip(ordered_days, ordered_days[1:]):
        if a_day <= query_day < b_day:
            seg_start_day, seg_end_day = a_day, b_day
            break

    period = next(
        (p for lo, _, hi, _, p in resolved_periods if lo <= seg_start_day < hi),
        None,
    )
    if period is None and seg_start_day >= resolved_periods[0][0]:
        raise ValueError("配运时间轴未覆盖请求年序；不能沿用最后一运。")

    ganzhi = _year_ganzhi(match_year)
    facts = _active_segment(period, element, ganzhi[1], include_verses=True)
    selected = {
        "at": query_clock.isoformat(),
        "year": match_year,
        "ganzhi": ganzhi,
        "start_at": cuts[seg_start_day].isoformat(),
        "end_at": cuts[seg_end_day].isoformat(),
        **facts,
        "year_start_boundary": start_boundary.to_record(),
        "year_end_boundary": end_boundary.to_record(),
    }
    solar_ctx = boundary_context(
        birth,
        zone,
        birth_year,
        horizon,
        [],
    )
    return selected, solar_ctx


def build_canping_timing(
    *,
    birth: datetime,
    zone: str,
    gender: str,
    month_pillar: tuple[str, str],
    calculation: dict,
    method: str = APPENDIX,
    analysis_datetime: str | None = None,
) -> tuple[dict, list[dict], dict]:
    timeline = luck_timeline(birth, gender, month_pillar, zone, method)
    element = calculation["element"]
    periods = []
    for i, p in enumerate(timeline["periods"]):
        numbers = compute_number(calculation["dayPalaceBranch"], p["branch"], element)
        periods.append(
            {
                "index": i,
                "branch": p["branch"],
                "pillar": p["pillar"],
                "start_at": p["start_at"],
                "end_at": p["end_at"],
                "start_age": p["age_range"]["start"],
                "end_age": p["age_range"]["end"],
                "numShun": numbers["numShun"],
                "numNi": numbers["numNi"],
                "verses": _verses(element, numbers, "luck", compact=True),
            }
        )
    birth_year = get_bazi_year(birth, zone)
    birth_label = ZonedCalendar.from_datetime(birth)
    origin_year = ZonedCalendar(birth_label.utc, parse_timezone_name(zone)).local_parts[
        0
    ]
    horizon = 120

    if analysis_datetime is not None:
        selected, solar_ctx = _resolve_queried_interval(
            birth=birth,
            zone=zone,
            periods=periods,
            element=element,
            analysis_datetime=analysis_datetime,
            horizon=horizon,
        )
    else:
        selected = None
        solar_ctx = boundary_context(birth, zone, birth_year, horizon, [])

    rows = _compact_liunian_rows(birth_year, periods, element, horizon, origin_year)
    series: dict[str, Any] = {
        "element": element,
        "rows": rows,
        "year_boundary": "lichun",
        "birth_pillar_year": birth_year,
        "age_policy": "sexagenary_year_ordinal; not_elapsed_age_or_lunar_new_year_age",
        "solar_context": solar_ctx,
    }
    details = {k: v for k, v in timeline.items() if k != "periods"}
    details.update(
        {
            "ruleset_id": "canping_ziping_appendix_bridge_v1",
            "ruleset_version": "1.0.0",
            "source_title": "河洛理數 史應選校訂 卷六及卷七附子平起運法",
            "source_status": "named_appendix_schedule",
            "selected": selected,
            "solar_year_context": solar_ctx,
        }
    )
    return details, periods, series
