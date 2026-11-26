"""Shared birth primitives independent of any analysis response renderer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fatebridge.core.almanac import build_calendar_context
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
    birth_pillars = BaZiCalendar.get_four_pillars(
        corrected_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        civil_datetime=normalized_birth_time.input_datetime,
        zi_hour_policy=zi_hour_policy,
    )
    birth_calendar_context = build_calendar_context(
        corrected_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        pillars=birth_pillars,
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
