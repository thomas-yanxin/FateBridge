"""Lower-volume individual mansion clauses and lunar-conjunction doctrine.

The doctrine classifies a mansion name in a text. It does not move a physical
Moon, infer an angular offset or replace a declared astronomical boundary.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, Optional, Sequence, cast

from fatebridge.core.sukuyo_documentary import with_text_layers
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_lower_mansions.json"
SukuyoActivityDetail = Literal[
    "tailoring_garments",
    "making_garments",
    "repairing_garments",
    "wearing_garments",
    "wearing_new_garments",
    "royal_wearer",
    "sale",
    "borrowing",
    "lending",
    "long_distance_journey",
    "journey_abroad",
    "personal_departure",
    "private_journey",
    "royal_or_official_traveler",
    "long_distance_traveler_entering_residence",
    "southbound_journey",
    "northbound_journey",
    "eastbound_journey",
    "westbound_journey",
    "skill_learning",
    "earning_money",
    "sale_lactating_livestock",
    "sale_livestock",
    "spending_property",
    "receiving_property",
    "returning_property",
    "wealth_competition",
    "founding_school",
    "beginning_study",
    "learning_with_teacher",
    "purchase",
    "business_operation",
    "collecting_debt",
    "repaying_debt",
    "religious_learning",
    "monastic_dharma_request",
    "teaching_classics",
    "riding_training",
    "water_journey",
    "diplomatic_mission",
    "purchase_precious_goods",
    "purchase_livestock",
    "land_purchase",
    "land_sale",
    "social_gathering",
    "forming_friendship",
    "classical_text_study",
    "debate_learning",
]
DETAIL_TOPICS = {
    **dict.fromkeys(
        [
            "tailoring_garments",
            "making_garments",
            "repairing_garments",
            "wearing_garments",
            "wearing_new_garments",
            "royal_wearer",
        ],
        "clothing",
    ),
    **dict.fromkeys(
        [
            "sale",
            "borrowing",
            "lending",
            "earning_money",
            "sale_lactating_livestock",
            "sale_livestock",
            "spending_property",
            "receiving_property",
            "returning_property",
            "wealth_competition",
            "purchase",
            "business_operation",
            "collecting_debt",
            "repaying_debt",
            "purchase_precious_goods",
            "purchase_livestock",
            "land_purchase",
            "land_sale",
        ],
        "commerce",
    ),
    **dict.fromkeys(
        [
            "long_distance_journey",
            "journey_abroad",
            "personal_departure",
            "private_journey",
            "royal_or_official_traveler",
            "long_distance_traveler_entering_residence",
            "southbound_journey",
            "northbound_journey",
            "eastbound_journey",
            "westbound_journey",
            "water_journey",
            "diplomatic_mission",
        ],
        "travel",
    ),
    "skill_learning": "study",
    "founding_school": "study",
    "beginning_study": "study",
    "learning_with_teacher": "study",
    "religious_learning": "study",
    "monastic_dharma_request": "study",
    "teaching_classics": "study",
    "riding_training": "study",
    "social_gathering": "social",
    "forming_friendship": "social",
    "classical_text_study": "study",
    "debate_learning": "study",
}

# A declared subtype establishes its broader action class, not unrelated facts
# such as distance, purpose, official status, payment method, cash flow or
# whether study is newly begun. Going somewhere does not establish private
# purpose; attending a gathering does not establish forming a new friendship.
DETAIL_PARENTS = {
    "tailoring_garments": ("making_garments",),
    "wearing_new_garments": ("wearing_garments",),
    "purchase_precious_goods": ("purchase",),
    "purchase_livestock": ("purchase",),
    "land_purchase": ("purchase",),
    "land_sale": ("sale",),
    "sale_lactating_livestock": ("sale_livestock",),
    "sale_livestock": ("sale",),
    "riding_training": ("skill_learning",),
    "monastic_dharma_request": ("religious_learning",),
}


def activity_detail_closure(details: Sequence[str]) -> tuple[list[str], list[dict]]:
    effective = list(dict.fromkeys(details))
    inferences = []
    for child in effective:
        for parent in DETAIL_PARENTS.get(child, ()):
            if parent not in effective:
                effective.append(parent)
                inferences.append({"from_detail": child, "implied_detail": parent})
    return effective, inferences


def validate_activity_details(activity: Optional[str], details: Sequence[str]) -> None:
    if isinstance(details, (str, bytes)):
        raise ValueError("activity_details必须为明确条件的列表")
    for detail in details:
        if not isinstance(detail, str) or detail not in DETAIL_TOPICS:
            raise ValueError("未知的宿占事项细节")
        if activity != DETAIL_TOPICS[detail]:
            raise ValueError(f"事项细节{detail}只适用于{DETAIL_TOPICS[detail]}")


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def source_digest() -> str:
    return load_source(SOURCE).sha256


def lower_mansion_evidence(mansion: Optional[str]) -> dict[str, Any]:
    bundle = source_bundle()
    record = next((r for r in bundle["records"] if r["mansion"] == mansion), None)
    if mansion is not None and record is None:
        raise ValueError("下卷逐宿证据只支持27宿（不含牛）")
    return {
        "status": "source_record_available" if record else "not_evaluated",
        "mansion": mansion,
        "ruleset_id": bundle["id"],
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "locator": record["locator"] if record else None,
        "topic_rules": (
            [
                {**with_text_layers(rule), "source_url": bundle["source_url"]}
                for rule in bundle["rules"]
                if mansion in rule["selectors"]
            ]
            if record
            else []
        ),
        "textual_issues": deepcopy(record["textual_issues"]) if record else [],
        "mapping_notes": deepcopy(record["mapping_notes"]) if record else [],
        "scope": "下卷逐宿条文的六类服务事项摘录；不是本命人格、全天判断或现实结果保证。条件条款缺具体行为时另列，不代入确定宜忌。修宅不自动当迁居；未输出医疗、寿命或伤害操作。",
    }


def conjunction_doctrine(
    mansion: Optional[str], candidates: Sequence[str] = ()
) -> dict[str, Any]:
    bundle = source_bundle()
    doctrine = bundle["conjunction_doctrine"]

    def group_for(name: str) -> dict[str, Any]:
        group = next((g for g in doctrine["groups"] if name in g["members"]), None)
        if group is None:
            raise ValueError("宿月配合分类只支持27宿（不含牛）")
        return deepcopy(cast(dict[str, Any], group))

    return {
        "ruleset_id": doctrine["id"],
        "status": "classified_name_reference" if mansion else "candidate_only",
        "mansion": mansion,
        "selected_group": group_for(mansion) if mansion else None,
        "candidate_groups": (
            [
                {"mansion": name, "group": group_for(name), "applied_to_primary": False}
                for name in dict.fromkeys(candidates)
            ]
            if mansion is None
            else []
        ),
        "basis": "textual_classification_of_calendrical_mansion_name",
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "locator": doctrine["locator"],
        "angular_offset_degrees": None,
        "physical_evaluation_status": "not_computed_no_declared_angular_model",
        "applied_to_physical_moon": False,
        "scope": doctrine["scope"],
    }
