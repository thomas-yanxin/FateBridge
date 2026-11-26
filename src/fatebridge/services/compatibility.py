"""Compute both natal inputs once and publish their directional contacts."""

from typing import Literal

from pydantic import JsonValue

from fatebridge.core.bazi.bazi_evidence import cross_chart_relations
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, get_ten_god
from fatebridge.utils.elements import get_element_relationship
from fatebridge.utils.errors import calculation_guard


@calculation_guard("双人八字取证")
def calculate_compatibility_analysis(
    person1: PersonInfo,
    person2: PersonInfo,
    relationship_type: Literal[
        "general", "marriage", "friendship", "business", "family"
    ] = "general",
) -> dict[str, JsonValue]:
    """Publish both natal contexts and directed ten-god evidence."""
    contexts = {
        "person1": build_birth_computation_context(person1, field_prefix="person1_"),
        "person2": build_birth_computation_context(person2, field_prefix="person2_"),
    }
    natal_charts = {
        role: build_destiny_payload(context) for role, context in contexts.items()
    }
    directional_ten_gods: dict[str, JsonValue] = {}
    for source_role, target_role in (("person1", "person2"), ("person2", "person1")):
        target_day_stem = contexts[target_role].birth_pillars["day"][0]
        directional_ten_gods[f"{source_role}_to_{target_role}"] = {
            "source": source_role,
            "target": target_role,
            "target_day_stem": target_day_stem,
            "stars": [
                {
                    "pillar": position,
                    "stem": evidenced_stem,
                    "location": location,
                    "ten_god": get_ten_god(target_day_stem, evidenced_stem).value,
                }
                for position, (stem, branch) in contexts[
                    source_role
                ].birth_pillars.items()
                for evidenced_stem, location in (
                    (stem, "天干"),
                    *(
                        (hidden_stem, "地支藏干")
                        for hidden_stem in BRANCH_HIDDEN_STEMS[branch]
                    ),
                )
            ],
        }
    person1_element = natal_charts["person1"]["day_master"]["element"]
    person2_element = natal_charts["person2"]["day_master"]["element"]
    relation = get_element_relationship(person1_element, person2_element)
    result: dict[str, JsonValue] = {
        "relationship_type": relationship_type,
        "person_info": {
            role: {
                "name": chart["person_info"]["name"],
                "birth_datetime": chart["person_info"]["birth_datetime"],
            }
            for role, chart in natal_charts.items()
        },
        "natal_contexts": {
            role: {
                "four_pillars": chart["four_pillars"],
                "calendar_context": chart["calendar_context"],
                "element_distribution": chart["element_distribution"],
                "day_master": {
                    day_master_field: chart["day_master"][day_master_field]
                    for day_master_field in (
                        "stem",
                        "element",
                        "polarity",
                        "engineering_index",
                        "classical_adjudication",
                    )
                },
                "preference_assessment": {
                    preference_field: chart["structure_profile"][preference_field]
                    for preference_field in (
                        "resolution_policy",
                        "assessment_status",
                        "useful_elements",
                        "avoid_elements",
                        "conditional_elements",
                        "neutral_elements",
                    )
                },
            }
            for role, chart in natal_charts.items()
        },
        "element_relationship": {
            "person1_element": person1_element,
            "person2_element": person2_element,
            "relationship_type": relation["type"],
        },
        "cross_chart_relations": cross_chart_relations(
            contexts["person1"].birth_pillars, contexts["person2"].birth_pillars
        ),
        "directional_ten_gods": directional_ten_gods,
    }
    return result
