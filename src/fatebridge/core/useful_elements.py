"""Resolve rule references without collapsing every non-useful element into 忌.

This is a conservative conflict policy, not a new classical scoring system.
Seasonal lookup and pattern presence remain conditional references.
"""

from typing import Any, Dict, List, Tuple

from ..utils.data import (
    BRANCH_HIDDEN_STEMS,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    Element,
)
from .classical import seasonal_climate_god


def resolve_useful_elements(
    pillars: Dict[str, Tuple[str, str]],
    element_analysis: Dict[str, Any],
    structures: List[Dict[str, Any]],
) -> Dict[str, Any]:
    day_stem = pillars["day"][0]
    day_element = STEM_ELEMENTS[day_stem][0]
    strength = element_analysis["day_master"]["strength_level"]
    baseline = list(element_analysis.get("favorable_elements", []))
    supporters = [day_element.value] + [
        element.value
        for element, generated in GENERATION_CYCLE.items()
        if generated == day_element
    ]
    assessment = element_analysis["day_master"].get("assessment", {})
    if (
        assessment.get("requires_special_structure_review")
        or assessment.get("status") == "boundary_sensitive"
    ):
        baseline_avoid = []
    elif strength == "强":
        baseline_avoid = supporters
    elif strength == "弱":
        baseline_avoid = [e.value for e in Element if e.value not in supporters]
    else:
        baseline_avoid = []
    layers = [
        {
            "source": "扶抑",
            "status": "heuristic",
            "useful_elements": baseline,
            "avoid_elements": baseline_avoid,
        }
    ]
    for structure in structures:
        layers.append(
            {
                "source": structure["key"],
                "status": "pattern_candidate",
                "useful_elements": list(structure.get("useful_elements", [])),
                "avoid_elements": list(structure.get("avoid_elements", [])),
            }
        )
    climate = seasonal_climate_god(day_stem, pillars["month"][1])
    stems = [climate["primary"]] + climate["secondary"] if climate["available"] else []
    climate_elements = list(
        dict.fromkeys(STEM_ELEMENTS[stem][0].value for stem in stems)
    )
    layers.append(
        {
            "source": "调候简表",
            "status": "reference_only",
            "useful_elements": climate_elements,
            "avoid_elements": [],
            "stems": [
                {
                    "stem": stem,
                    "priority": "primary" if index == 0 else "secondary",
                    "visible_in": [
                        name
                        for name, (visible, _) in pillars.items()
                        if visible == stem
                    ],
                    "hidden_in": [
                        name
                        for name, (_, branch) in pillars.items()
                        if stem in BRANCH_HIDDEN_STEMS[branch]
                    ],
                }
                for index, stem in enumerate(stems)
            ],
            "limitations": [
                "日干与月支简表；未判断原局剂量、寒暖是否已调和或是否需要新增。"
            ],
        }
    )
    primary = set(baseline)
    if structures:
        primary.update(structures[0].get("useful_elements", []))
    useful, avoid, conditional, neutral, conflicts = [], [], [], [], []
    for element in Element:
        value = element.value
        positive = [
            layer["source"] for layer in layers if value in layer["useful_elements"]
        ]
        negative = [
            layer["source"] for layer in layers if value in layer["avoid_elements"]
        ]
        if positive and negative:
            conditional.append(value)
            conflicts.append(
                {
                    "element": value,
                    "supporting_sources": positive,
                    "opposing_sources": negative,
                }
            )
        elif positive and value in primary:
            useful.append(value)
        elif positive:
            conditional.append(value)
        elif negative:
            avoid.append(value)
        else:
            neutral.append(value)
    return {
        "resolution_policy": "layered_conflict_review_v1",
        "assessment_status": "conditional",
        "useful_elements": useful,
        "avoid_elements": avoid,
        "conditional_elements": conditional,
        "neutral_elements": neutral,
        "layers": layers,
        "conflicts": conflicts,
        "limitations": [
            "喜忌为规则参考，非补充元素或行动处方；中和不默认喜日主本五行。",
            "格局按十神共现识别为候选，未验证成格、制化力度和破格条件。",
            "全局喜用仅保留主格局或扶抑支持且无反向规则的候选；调候与次格局独立保留。",
        ],
    }
