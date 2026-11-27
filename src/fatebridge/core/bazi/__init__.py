"""Cohesive BaZi core engine: calendar, relations, strength, shensha, timing, compatibility, sources."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fatebridge.core.bazi.calendar import (
        CHANGSHENG_SCHOOLS,
        DUTY_PROFILES,
        LATE_ZI_HOUR,
        TWELVE_STAGES,
        ZI_HOUR_POLICIES,
        BaZiCalendar,
        ChangshengSchool,
        DutyProfile,
        ZiHourPolicy,
        build_taixi,
        build_three_origins,
        life_stages_for_pillars,
        resolve_bazi_effective_date,
        resolve_month_duty,
        twelve_life_stage,
    )
    from fatebridge.core.bazi.compatibility import (
        analyze_cross_shensha,
        analyze_day_pillar_synergy,
        analyze_element_complementarity,
        analyze_nayin_compatibility,
        compute_directional_ten_gods,
        cross_chart_relations,
    )
    from fatebridge.core.bazi.relations import (
        BRANCH_BREAKS,
        BRANCH_HIDDEN_COMBINATIONS,
        check_clash_patterns,
        check_harmony_patterns,
        check_hidden_patterns,
        check_pillar_pair_patterns,
        check_pillar_patterns,
        check_stem_patterns,
        classify_triple_members,
        collect_target_branch_relations,
        group_relations,
        pair_relations,
    )
    from fatebridge.core.bazi.shensha import build_shensha_profile, timing_shensha
    from fatebridge.core.bazi.strength import (
        DEFAULT_POLICY,
        StrengthPolicy,
        analyze_elements_and_structure,
        build_sensitivity_report,
        convert_to_percentage,
        count_elements,
        evaluate_strength_policy,
        seasonal_climate_god,
        seasonal_phases,
    )
    from fatebridge.core.bazi.timing import (
        TimingAnalysis,
        analyze_timing_interactions,
        calculate_dayun_sequence,
        calculate_xiaoyun_pillar,
        calculate_xiaoyun_timeline,
        dayun_is_forward,
    )

_EXPORTS: dict[str, tuple[str, str]] = {
    "CHANGSHENG_SCHOOLS": ("fatebridge.core.bazi.calendar", "CHANGSHENG_SCHOOLS"),
    "DUTY_PROFILES": ("fatebridge.core.bazi.calendar", "DUTY_PROFILES"),
    "LATE_ZI_HOUR": ("fatebridge.core.bazi.calendar", "LATE_ZI_HOUR"),
    "TWELVE_STAGES": ("fatebridge.core.bazi.calendar", "TWELVE_STAGES"),
    "ZI_HOUR_POLICIES": ("fatebridge.core.bazi.calendar", "ZI_HOUR_POLICIES"),
    "BaZiCalendar": ("fatebridge.core.bazi.calendar", "BaZiCalendar"),
    "ChangshengSchool": ("fatebridge.core.bazi.policies", "ChangshengSchool"),
    "DutyProfile": ("fatebridge.core.bazi.policies", "DutyProfile"),
    "ZiHourPolicy": ("fatebridge.core.bazi.policies", "ZiHourPolicy"),
    "build_taixi": ("fatebridge.core.bazi.calendar", "build_taixi"),
    "build_three_origins": ("fatebridge.core.bazi.calendar", "build_three_origins"),
    "life_stages_for_pillars": (
        "fatebridge.core.bazi.calendar",
        "life_stages_for_pillars",
    ),
    "resolve_bazi_effective_date": (
        "fatebridge.core.bazi.calendar",
        "resolve_bazi_effective_date",
    ),
    "resolve_month_duty": ("fatebridge.core.bazi.calendar", "resolve_month_duty"),
    "twelve_life_stage": ("fatebridge.core.bazi.calendar", "twelve_life_stage"),
    "analyze_cross_shensha": (
        "fatebridge.core.bazi.compatibility",
        "analyze_cross_shensha",
    ),
    "analyze_day_pillar_synergy": (
        "fatebridge.core.bazi.compatibility",
        "analyze_day_pillar_synergy",
    ),
    "analyze_element_complementarity": (
        "fatebridge.core.bazi.compatibility",
        "analyze_element_complementarity",
    ),
    "analyze_nayin_compatibility": (
        "fatebridge.core.bazi.compatibility",
        "analyze_nayin_compatibility",
    ),
    "compute_directional_ten_gods": (
        "fatebridge.core.bazi.compatibility",
        "compute_directional_ten_gods",
    ),
    "cross_chart_relations": (
        "fatebridge.core.bazi.compatibility",
        "cross_chart_relations",
    ),
    "BRANCH_BREAKS": ("fatebridge.core.bazi.relations", "BRANCH_BREAKS"),
    "BRANCH_HIDDEN_COMBINATIONS": (
        "fatebridge.core.bazi.relations",
        "BRANCH_HIDDEN_COMBINATIONS",
    ),
    "check_clash_patterns": (
        "fatebridge.core.bazi.relations",
        "check_clash_patterns",
    ),
    "check_harmony_patterns": (
        "fatebridge.core.bazi.relations",
        "check_harmony_patterns",
    ),
    "check_hidden_patterns": (
        "fatebridge.core.bazi.relations",
        "check_hidden_patterns",
    ),
    "check_pillar_pair_patterns": (
        "fatebridge.core.bazi.relations",
        "check_pillar_pair_patterns",
    ),
    "check_pillar_patterns": (
        "fatebridge.core.bazi.relations",
        "check_pillar_patterns",
    ),
    "check_stem_patterns": ("fatebridge.core.bazi.relations", "check_stem_patterns"),
    "classify_triple_members": (
        "fatebridge.core.bazi.relations",
        "classify_triple_members",
    ),
    "collect_target_branch_relations": (
        "fatebridge.core.bazi.relations",
        "collect_target_branch_relations",
    ),
    "group_relations": ("fatebridge.core.bazi.relations", "group_relations"),
    "pair_relations": ("fatebridge.core.bazi.relations", "pair_relations"),
    "build_shensha_profile": ("fatebridge.core.bazi.shensha", "build_shensha_profile"),
    "timing_shensha": ("fatebridge.core.bazi.shensha", "timing_shensha"),
    "DEFAULT_POLICY": ("fatebridge.core.bazi.strength", "DEFAULT_POLICY"),
    "StrengthPolicy": ("fatebridge.core.bazi.strength", "StrengthPolicy"),
    "analyze_elements_and_structure": (
        "fatebridge.core.bazi.strength",
        "analyze_elements_and_structure",
    ),
    "build_sensitivity_report": (
        "fatebridge.core.bazi.strength",
        "build_sensitivity_report",
    ),
    "convert_to_percentage": ("fatebridge.core.bazi.strength", "convert_to_percentage"),
    "count_elements": ("fatebridge.core.bazi.strength", "count_elements"),
    "evaluate_strength_policy": (
        "fatebridge.core.bazi.strength",
        "evaluate_strength_policy",
    ),
    "seasonal_climate_god": ("fatebridge.core.bazi.strength", "seasonal_climate_god"),
    "seasonal_phases": ("fatebridge.core.bazi.strength", "seasonal_phases"),
    "TimingAnalysis": ("fatebridge.core.bazi.timing", "TimingAnalysis"),
    "analyze_timing_interactions": (
        "fatebridge.core.bazi.timing",
        "analyze_timing_interactions",
    ),
    "calculate_dayun_sequence": (
        "fatebridge.core.bazi.timing",
        "calculate_dayun_sequence",
    ),
    "calculate_xiaoyun_pillar": (
        "fatebridge.core.bazi.timing",
        "calculate_xiaoyun_pillar",
    ),
    "calculate_xiaoyun_timeline": (
        "fatebridge.core.bazi.timing",
        "calculate_xiaoyun_timeline",
    ),
    "dayun_is_forward": ("fatebridge.core.bazi.timing", "dayun_is_forward"),
}

__all__ = [
    "BRANCH_BREAKS",
    "BRANCH_HIDDEN_COMBINATIONS",
    "CHANGSHENG_SCHOOLS",
    "DEFAULT_POLICY",
    "DUTY_PROFILES",
    "LATE_ZI_HOUR",
    "TWELVE_STAGES",
    "ZI_HOUR_POLICIES",
    "BaZiCalendar",
    "ChangshengSchool",
    "DutyProfile",
    "StrengthPolicy",
    "TimingAnalysis",
    "ZiHourPolicy",
    "analyze_cross_shensha",
    "analyze_day_pillar_synergy",
    "analyze_element_complementarity",
    "analyze_elements_and_structure",
    "analyze_nayin_compatibility",
    "analyze_timing_interactions",
    "build_sensitivity_report",
    "build_shensha_profile",
    "build_taixi",
    "build_three_origins",
    "calculate_dayun_sequence",
    "calculate_xiaoyun_pillar",
    "calculate_xiaoyun_timeline",
    "check_clash_patterns",
    "check_harmony_patterns",
    "check_hidden_patterns",
    "check_pillar_pair_patterns",
    "check_pillar_patterns",
    "check_stem_patterns",
    "classify_triple_members",
    "collect_target_branch_relations",
    "compute_directional_ten_gods",
    "convert_to_percentage",
    "count_elements",
    "cross_chart_relations",
    "dayun_is_forward",
    "evaluate_strength_policy",
    "group_relations",
    "life_stages_for_pillars",
    "pair_relations",
    "resolve_bazi_effective_date",
    "resolve_month_duty",
    "seasonal_climate_god",
    "seasonal_phases",
    "timing_shensha",
    "twelve_life_stage",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is not None:
        module_name, attr_name = target
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
