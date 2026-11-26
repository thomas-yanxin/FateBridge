"""Compute both natal inputs once and publish cross-chart relations, 纳音, 鸳鸯合, 喜用互补, 神煞互照."""

from __future__ import annotations

from typing import Literal

from pydantic import JsonValue

from fatebridge.core.bazi.calendar import ZiHourPolicy
from fatebridge.core.bazi.compatibility import (
    analyze_cross_shensha,
    analyze_day_pillar_synergy,
    analyze_element_complementarity,
    analyze_nayin_compatibility,
    compute_directional_ten_gods,
    cross_chart_relations,
)
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.elements import get_element_relationship
from fatebridge.utils.errors import calculation_guard


@calculation_guard("双人八字合婚/关系分析")
def calculate_compatibility_analysis(
    person1: PersonInfo,
    person2: PersonInfo,
    relationship_type: Literal[
        "general", "marriage", "friendship", "business", "family"
    ] = "general",
    *,
    person1_zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    person2_zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
) -> dict[str, JsonValue]:
    """Build both natal charts once and compute full compatibility facts."""
    contexts = {
        "person1": build_birth_computation_context(
            person1,
            field_prefix="person1_",
            zi_hour_policy=person1_zi_hour_policy,
        ),
        "person2": build_birth_computation_context(
            person2,
            field_prefix="person2_",
            zi_hour_policy=person2_zi_hour_policy,
        ),
    }
    natal_charts = {
        role: build_destiny_payload(context) for role, context in contexts.items()
    }
    p1_pillars = contexts["person1"].birth_pillars
    p2_pillars = contexts["person2"].birth_pillars

    p1_element = natal_charts["person1"]["day_master"]["element"]
    p2_element = natal_charts["person2"]["day_master"]["element"]
    relation = get_element_relationship(p1_element, p2_element)

    p1_sp = natal_charts["person1"]["structure_profile"]
    p2_sp = natal_charts["person2"]["structure_profile"]

    return {
        "relationship_type": relationship_type,
        "person_info": {
            role: {
                "name": chart["person_info"]["name"],
                "birth_datetime": chart["person_info"]["birth_datetime"],
                "normalized_birth_datetime": chart["person_info"][
                    "normalized_birth_datetime"
                ],
                "gender": chart["person_info"]["gender"],
            }
            for role, chart in natal_charts.items()
        },
        "natal_contexts": {
            role: {
                "four_pillars": chart["four_pillars"],
                "calendar_context": chart["calendar_context"],
                "element_distribution": chart["element_distribution"],
                "day_master": chart["day_master"],
                "preference_assessment": {
                    "assessment_status": chart["structure_profile"][
                        "assessment_status"
                    ],
                    "dominant_structure": chart["structure_profile"][
                        "dominant_structure"
                    ]["label"],
                    "useful_elements": chart["structure_profile"]["useful_elements"],
                    "avoid_elements": chart["structure_profile"]["avoid_elements"],
                    "neutral_elements": chart["structure_profile"]["neutral_elements"],
                },
            }
            for role, chart in natal_charts.items()
        },
        "element_relationship": {
            "person1_element": p1_element,
            "person2_element": p2_element,
            "relationship_type": relation["type"],
        },
        "nayin_comparison": analyze_nayin_compatibility(p1_pillars, p2_pillars),
        "day_pillar_synergy": analyze_day_pillar_synergy(p1_pillars, p2_pillars),
        "element_complementarity": analyze_element_complementarity(
            p1_sp["useful_elements"],
            p1_sp["avoid_elements"],
            natal_charts["person1"]["element_distribution"],
            p2_sp["useful_elements"],
            p2_sp["avoid_elements"],
            natal_charts["person2"]["element_distribution"],
        ),
        "cross_shensha": analyze_cross_shensha(p1_pillars, p2_pillars),
        "cross_chart_relations": cross_chart_relations(p1_pillars, p2_pillars),
        "directional_ten_gods": compute_directional_ten_gods(p1_pillars, p2_pillars),
    }
