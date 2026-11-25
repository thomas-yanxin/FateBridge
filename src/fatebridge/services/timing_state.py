"""Shared timing-layer computation and timeline enrichment from one birth context."""

from datetime import datetime
from typing import Any, TypedDict

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.analysis.timing_element_shares import (
    ElementShareChange,
    ElementShareCountingBasis,
    TimingElementEffects,
)
from fatebridge.core.timing import TimingAnalysis
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.core.timing_strength import StrengthProjectionBaseline
from fatebridge.services.birth_context import BirthComputationContext


def calculate_analysis_age(
    birth_datetime: datetime,
    analysis_date: datetime,
    explicit_age: int | None = None,
) -> int:
    if explicit_age is not None:
        return explicit_age
    else:
        pass

    age = analysis_date.year - birth_datetime.year
    if (analysis_date.month, analysis_date.day) < (
        birth_datetime.month,
        birth_datetime.day,
    ):
        age -= 1
    else:
        pass
    return age


class SerializedTimingElementEffects(TypedDict):
    overall_effect: str
    element_changes: dict[str, ElementShareChange]
    method_id: str
    interpretation_scope: str
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
        "method_id": element_effects["method_id"],
        "interpretation_scope": element_effects["interpretation_scope"],
        "counting_basis": element_effects["counting_basis"],
    }


def build_current_timing_state(
    birth_context: BirthComputationContext,
    *,
    analysis_date: datetime,
    analysis_age: int | None = None,
) -> dict[str, Any]:
    """Build the current timing analyses once from shared birth context."""
    timezone_name = birth_context.normalized_birth_time.timezone
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
    )
    liushi_info = TimingAnalysis.calculate_liushi(
        analysis_date,
        timezone_name=timezone_name,
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
    )
    liushi_analysis = TimingEffectsAnalysis.analyze_liushi_effects(
        birth_context.birth_pillars,
        analysis_date,
        timezone_name=timezone_name,
        liushi_info=liushi_info,
        original_element_counts=birth_context.original_element_counts,
    )

    combined_timing_pillars: dict[str, dict[str, str]] = {}
    if "dayun_info" in dayun_analysis:
        combined_timing_pillars["dayun"] = {
            "stem": dayun_analysis["dayun_info"]["stem"],
            "branch": dayun_analysis["dayun_info"]["branch"],
        }
    else:
        pass
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
    natal_assessment = birth_context.element_analysis["day_master"]["assessment"]

    return {
        "analysis_date": analysis_date,
        "current_age": current_age,
        "dayun_analysis": dayun_analysis,
        "liunian_analysis": liunian_analysis,
        "liuyue_analysis": liuyue_analysis,
        "liuri_analysis": liuri_analysis,
        "liushi_analysis": liushi_analysis,
        "combined_effects": combined_effects,
        "interaction_analysis": analyze_timing_interactions(
            birth_context.birth_pillars,
            combined_timing_pillars,
            strength_baseline=StrengthProjectionBaseline(
                method_id=natal_assessment["method_id"],
                strength_level=birth_context.element_analysis["day_master"][
                    "engineering_index"
                ]["strength_level"],
                numerical_label=natal_assessment["threshold_arithmetic"][
                    "numerical_label"
                ],
                support_share_exact=natal_assessment["threshold_arithmetic"][
                    "share_exact"
                ],
                energies_exact=natal_assessment["threshold_arithmetic"][
                    "energies_exact"
                ],
                parameters=natal_assessment["parameters"],
                seasonal_phases=natal_assessment["seasonal_phases"],
                seasonal_factors=natal_assessment["seasonal_factors"],
                relations=natal_assessment["relations"],
            ),
        ),
        "comprehensive_summary": TimingEffectsAnalysis._generate_comprehensive_summary(
            dayun_analysis,
            liunian_analysis,
            liuyue_analysis,
            liuri_analysis,
            combined_effects,
            liushi_analysis=liushi_analysis,
        ),
    }


def enrich_liuyue_timeline(
    birth_context: BirthComputationContext,
    *,
    target_year: int,
) -> list[dict[str, Any]]:
    timezone_name = birth_context.normalized_birth_time.timezone
    liuyue_timeline = TimingAnalysis.calculate_liuyue_timeline(
        target_year,
        timezone_name=timezone_name,
    )
    for item in liuyue_timeline:
        if "analysis_anchor" not in item:
            continue
        else:
            pass
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
        item["summary"] = liuyue_effect["enhanced_summary"]
    return liuyue_timeline


def enrich_jieqi_timeline(
    birth_context: BirthComputationContext,
    *,
    target_year: int,
) -> list[dict[str, Any]]:
    timezone_name = birth_context.normalized_birth_time.timezone
    jieqi_timeline = TimingAnalysis.calculate_jieqi_transition_timeline(
        target_year,
        timezone_name=timezone_name,
    )
    for item in jieqi_timeline:
        if "analysis_anchor" not in item:
            continue
        else:
            pass
        anchor = datetime.strptime(item["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
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
        liuri_effect = TimingEffectsAnalysis.analyze_liuri_effects(
            birth_context.birth_pillars,
            anchor,
            timezone_name=timezone_name,
            liuri_info=liuri_pillar,
            original_element_counts=birth_context.original_element_counts,
        )
        item["overall_effect"] = node_effect["overall_effect"]
        item["liuri_summary"] = liuri_effect["enhanced_summary"]
        item["summary"] = (
            f"{item['jieqi']['name']}节点，流月{liuyue_pillar['pillar']}，"
            f"流日{liuri_pillar['pillar']}，{node_effect['overall_effect']}"
        )
    return jieqi_timeline
