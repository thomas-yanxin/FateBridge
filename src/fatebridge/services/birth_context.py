"""Shared birth primitives independent of any analysis response renderer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from fatebridge.core.almanac import (
    build_calendar_context,
    get_lunar_context,
    get_solar_terms_for_year,
)
from fatebridge.core.batch_cache import batch_cached, freeze_cache_value
from fatebridge.core.bazi.calendar import (
    BaZiCalendar,
    ChangshengSchool,
    DutyProfile,
    ZiHourPolicy,
    resolve_month_duty,
)
from fatebridge.core.bazi.strength import analyze_elements_and_structure
from fatebridge.utils.birth_clock import birth_clock_input_receipt
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.data import Element
from fatebridge.utils.solar_time import NormalizedBirthTime, normalize_birth_time


@dataclass(frozen=True)
class BirthComputationContext:
    """Shared deterministic birth-computation primitives for downstream services."""

    person: PersonInfo
    normalized_birth_time: NormalizedBirthTime
    birth_pillars: dict[str, tuple[str, str]]
    birth_calendar_context: dict[str, Any]
    element_analysis: dict[str, Any]
    original_element_counts: dict[Element, float]
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23"
    changsheng_school: ChangshengSchool = "fire_earth_same_palace"
    duty_profile: DutyProfile = "sanming"
    intra_month_duty: dict[str, Any] | None = None


def build_unknown_hour_coverage(
    birth_date_obj: date,
    timezone_name: str,
    *,
    mode: Literal["three_pillars_hour_unknown", "date_only_hour_unknown"],
    omitted_components: list[str],
) -> dict[str, Any]:
    """Build honest coverage and solar-term / lunar-new-year boundary warnings."""
    boundary_warnings: list[str] = []
    jie_names = {
        "立春",
        "惊蛰",
        "清明",
        "立夏",
        "芒种",
        "小暑",
        "立秋",
        "白露",
        "寒露",
        "立冬",
        "大雪",
        "小寒",
    }
    for term in get_solar_terms_for_year(birth_date_obj.year, timezone_name):
        if not term.has_defined_local_clock:
            continue
        if term.moment.date() == birth_date_obj and term.name in jie_names:
            boundary_warnings.append(
                f"出生公历日 {birth_date_obj.isoformat()} 当日交节「{term.name}」（{term.moment.strftime('%H:%M:%S')}），"
                f"因出生时辰未知，{'年/月柱' if term.name == '立春' else '月柱'}归属存在跨节边界敏感性。"
            )
    if mode == "date_only_hour_unknown":
        lunar = get_lunar_context(
            datetime(
                birth_date_obj.year, birth_date_obj.month, birth_date_obj.day, 12, 0
            ),
            timezone_name=timezone_name,
        )
        if (
            isinstance(lunar, dict)
            and lunar.get("month") == 1
            and lunar.get("day") == 1
        ):
            boundary_warnings.append(
                f"出生公历日 {birth_date_obj.isoformat()} 为农历正月初一，时辰/零点换日临界处农历年份需核对出生时段。"
            )
    return {
        "mode": mode,
        "known_pillars": (
            ["year", "month", "day"] if mode == "three_pillars_hour_unknown" else []
        ),
        "omitted_components": omitted_components,
        "reference_clock_policy": "civil_noon_12_00_anchor_for_calendar_lookup_only",
        "boundary_warnings": boundary_warnings,
    }


def _birth_context_cache_key(
    person: PersonInfo,
    *,
    field_prefix: str = "",
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> tuple[object, ...]:
    return (
        freeze_cache_value(person.model_dump(mode="json")),
        field_prefix,
        zi_hour_policy,
        changsheng_school,
        duty_profile,
    )


@batch_cached(
    "bazi.build_birth_computation_context",
    _birth_context_cache_key,
    copy_result=True,
)
def build_birth_computation_context(
    person: PersonInfo,
    *,
    field_prefix: str = "",
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    changsheng_school: ChangshengSchool = "fire_earth_same_palace",
    duty_profile: DutyProfile = "sanming",
) -> BirthComputationContext:
    """Build the shared birth context once so downstream services can reuse it."""
    normalized_birth_time = normalize_birth_time(person, field_prefix=field_prefix)
    corrected_birth_datetime = normalized_birth_time.corrected_datetime
    raw_pillars = BaZiCalendar.get_four_pillars(
        corrected_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        civil_datetime=normalized_birth_time.input_datetime,
        zi_hour_policy=zi_hour_policy,
    )
    birth_pillars = (
        {k: v for k, v in raw_pillars.items() if k != "hour"}
        if getattr(person, "birth_time_unknown", False)
        else raw_pillars
    )
    birth_calendar_context = build_calendar_context(
        corrected_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        pillars=raw_pillars,
        civil_datetime=normalized_birth_time.input_datetime,
    )
    birth_calendar_context["birth_time_input"] = birth_clock_input_receipt(
        person, normalized_birth_time
    )
    element_analysis = analyze_elements_and_structure(
        birth_pillars, changsheng_school=changsheng_school
    )
    raw_counts = element_analysis["element_distribution_raw"]
    month_boundary = birth_calendar_context["bazi_month_boundary"]
    duty = resolve_month_duty(
        birth_pillars["month"][1],
        month_boundary.get("days_since_start"),
        day_stem=birth_pillars["day"][0],
        profile=duty_profile,
    )

    return BirthComputationContext(
        person=person,
        normalized_birth_time=normalized_birth_time,
        birth_pillars=birth_pillars,
        birth_calendar_context=birth_calendar_context,
        element_analysis=element_analysis,
        original_element_counts={
            element: float(raw_counts.get(element.value, 0.0)) for element in Element
        },
        zi_hour_policy=zi_hour_policy,
        changsheng_school=changsheng_school,
        duty_profile=duty_profile,
        intra_month_duty=duty,
    )
