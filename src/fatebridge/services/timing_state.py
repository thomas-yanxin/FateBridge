"""Shared timing-layer computation from one birth context."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.analysis.timing_element_shares import (
    ElementShareChange,
    ElementShareCountingBasis,
    TimingElementEffects,
)
from fatebridge.core.bazi.policies import YearBoundaryPolicy
from fatebridge.core.bazi.timing import TimingAnalysis, analyze_timing_interactions
from fatebridge.services.birth_context import BirthComputationContext


def calculate_analysis_age(
    birth_datetime: datetime,
    analysis_date: datetime,
    explicit_age: int | None = None,
) -> int:
    if explicit_age is not None:
        return explicit_age
    age = analysis_date.year - birth_datetime.year
    if (analysis_date.month, analysis_date.day) < (
        birth_datetime.month,
        birth_datetime.day,
    ):
        age -= 1
    return age


class SerializedTimingElementEffects(TypedDict):
    overall_effect: str
    element_changes: dict[str, ElementShareChange]
    counting_basis: ElementShareCountingBasis


def serialize_element_effects(
    element_effects: TimingElementEffects,
) -> SerializedTimingElementEffects:
    return {
        "overall_effect": element_effects["overall_effect"],
        "element_changes": {
            element: change.copy()
            for element, change in element_effects["element_changes"].items()
            if change["change"] != 0
        },
        "counting_basis": element_effects["counting_basis"],
    }


def build_current_timing_state(
    birth_context: BirthComputationContext,
    *,
    analysis_date: datetime,
    analysis_age: int | None = None,
    include_interactions: bool = True,
    year_boundary_policy: YearBoundaryPolicy = "lichun",
) -> dict[str, Any]:
    """Build current Dayun/小运, 流年, 流月, 流日, 流时 and full interactions."""
    timezone_name = birth_context.normalized_birth_time.timezone
    zi_hour_policy = birth_context.zi_hour_policy
    current_age = calculate_analysis_age(
        birth_context.normalized_birth_time.input_datetime,
        analysis_date,
        explicit_age=analysis_age,
    )
    liuyue_info = TimingAnalysis.calculate_liuyue(
        analysis_date.year,
        analysis_date.month,
        target_day=analysis_date.day,
        timezone_name=timezone_name,
        target_date=analysis_date,
    )
    liuri_info = TimingAnalysis.calculate_liuri(
        analysis_date,
        timezone_name=timezone_name,
        zi_hour_policy=zi_hour_policy,
    )
    liushi_info = TimingAnalysis.calculate_liushi(
        analysis_date,
        timezone_name=timezone_name,
        zi_hour_policy=zi_hour_policy,
    )
    dayun_analysis = TimingEffectsAnalysis.analyze_dayun_effects(
        birth_context.birth_pillars,
        birth_context.normalized_birth_time.input_datetime,
        birth_context.person.gender,
        current_age,
        timezone_name=timezone_name,
        original_element_counts=birth_context.original_element_counts,
        analysis_moment=analysis_date if analysis_age is None else None,
        allow_missing_gender=True,
    )
    liunian_analysis = TimingEffectsAnalysis.analyze_liunian_effects(
        birth_context.birth_pillars,
        analysis_date.year,
        original_element_counts=birth_context.original_element_counts,
        moment=analysis_date,
        timezone_name=timezone_name,
        year_boundary_policy=year_boundary_policy,
    )
    liuyue_analysis = TimingEffectsAnalysis.analyze_liuyue_effects(
        birth_context.birth_pillars,
        analysis_date.year,
        analysis_date.month,
        target_day=analysis_date.day,
        timezone_name=timezone_name,
        target_date=analysis_date,
        liuyue_info=liuyue_info,
        original_element_counts=birth_context.original_element_counts,
    )
    liuri_analysis = TimingEffectsAnalysis.analyze_liuri_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=timezone_name,
        liuri_info=liuri_info,
        original_element_counts=birth_context.original_element_counts,
        zi_hour_policy=zi_hour_policy,
    )
    liushi_analysis = TimingEffectsAnalysis.analyze_liushi_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=timezone_name,
        liushi_info=liushi_info,
        original_element_counts=birth_context.original_element_counts,
        zi_hour_policy=zi_hour_policy,
    )

    combined_timing_pillars: dict[str, dict[str, str]] = {}
    if "dayun_info" in dayun_analysis:
        combined_timing_pillars["dayun"] = {
            "stem": dayun_analysis["dayun_info"]["stem"],
            "branch": dayun_analysis["dayun_info"]["branch"],
        }
    elif "xiaoyun_info" in dayun_analysis:
        combined_timing_pillars["xiaoyun"] = {
            "stem": dayun_analysis["xiaoyun_info"]["stem"],
            "branch": dayun_analysis["xiaoyun_info"]["branch"],
        }
    combined_timing_pillars["liunian"] = {
        "stem": liunian_analysis["liunian_info"]["stem"],
        "branch": liunian_analysis["liunian_info"]["branch"],
    }
    combined_timing_pillars["liuyue"] = {
        "stem": liuyue_analysis["liuyue_info"]["stem"],
        "branch": liuyue_analysis["liuyue_info"]["branch"],
    }
    combined_timing_pillars["liuri"] = {
        "stem": liuri_analysis["liuri_info"]["stem"],
        "branch": liuri_analysis["liuri_info"]["branch"],
    }
    combined_timing_pillars["liushi"] = {
        "stem": liushi_analysis["liushi_info"]["stem"],
        "branch": liushi_analysis["liushi_info"]["branch"],
    }

    combined_effects = TimingEffectsAnalysis.analyze_element_strength_changes(
        birth_context.birth_pillars,
        combined_timing_pillars,
        original_element_counts=birth_context.original_element_counts,
    )

    state: dict[str, Any] = {
        "analysis_date": analysis_date,
        "current_age": current_age,
        "dayun_analysis": dayun_analysis,
        "liunian_analysis": liunian_analysis,
        "liuyue_analysis": liuyue_analysis,
        "liuri_analysis": liuri_analysis,
        "liushi_analysis": liushi_analysis,
        "combined_effects": combined_effects,
    }
    if include_interactions:
        state["interaction_analysis"] = analyze_timing_interactions(
            birth_context.birth_pillars,
            combined_timing_pillars,
        )
    return state


def enrich_liuyue_timeline(
    birth_context: BirthComputationContext,
    *,
    target_year: int,
) -> list[dict[str, Any]]:
    timezone_name = birth_context.normalized_birth_time.timezone
    liuyue_timeline = TimingAnalysis.calculate_liuyue_timeline(
        target_year, timezone_name=timezone_name
    )
    for item in liuyue_timeline:
        if "analysis_anchor" not in item:
            continue
        anchor = datetime.strptime(item["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
        liuyue_effect = TimingEffectsAnalysis.analyze_liuyue_effects(
            birth_context.birth_pillars,
            anchor.year,
            anchor.month,
            target_day=anchor.day,
            timezone_name=timezone_name,
            target_date=anchor,
            liuyue_info=item["liuyue"],
            original_element_counts=birth_context.original_element_counts,
        )
        item["overall_effect"] = liuyue_effect["element_effects"]["overall_effect"]
    return liuyue_timeline


def enrich_jieqi_timeline(
    birth_context: BirthComputationContext,
    *,
    target_year: int,
) -> list[dict[str, Any]]:
    timezone_name = birth_context.normalized_birth_time.timezone
    jieqi_timeline = TimingAnalysis.calculate_jieqi_transition_timeline(
        target_year, timezone_name=timezone_name
    )
    for item in jieqi_timeline:
        if "analysis_anchor" not in item:
            continue
        liuyue_pillar = item["liuyue"]
        liuri_pillar = item["liuri"]
        node_effect = TimingEffectsAnalysis.analyze_element_strength_changes(
            birth_context.birth_pillars,
            {
                "liuyue": {
                    "stem": liuyue_pillar["stem"],
                    "branch": liuyue_pillar["branch"],
                },
                "liuri": {
                    "stem": liuri_pillar["stem"],
                    "branch": liuri_pillar["branch"],
                },
            },
            original_element_counts=birth_context.original_element_counts,
        )
        item["overall_effect"] = node_effect["overall_effect"]
    return jieqi_timeline
