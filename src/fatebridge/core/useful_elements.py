"""Resolve rule references without collapsing every non-useful element into 忌.

This is a conservative conflict policy, not a new classical scoring system.
Seasonal lookup and pattern presence remain conditional references.
"""

from typing import Any, Dict, List, Literal, Tuple, TypedDict

from typing_extensions import NotRequired

from ..utils.data import (
    BRANCH_HIDDEN_STEMS,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    Element,
)
from .classical import seasonal_climate_god
from .classical_from_child import build_from_child_reference


class ClimateStemReference(TypedDict):
    stem: str
    priority: str
    visible_in: list[str]
    hidden_in: list[str]


class PreferenceLayer(TypedDict):
    source: str
    status: str
    useful_elements: list[str]
    avoid_elements: list[str]
    source_adjudication_used: NotRequired[Literal[False]]
    selection_status: NotRequired[str]
    scope: NotRequired[str]
    stems: NotRequired[list[ClimateStemReference]]
    limitations: NotRequired[list[str]]


def resolve_useful_elements(
    pillars: Dict[str, Tuple[str, str]],
    element_analysis: Dict[str, Any],
    structures: List[Dict[str, Any]],
) -> Dict[str, Any]:
    day_stem = pillars["day"][0]
    day_element = STEM_ELEMENTS[day_stem][0]
    day_master = element_analysis["day_master"]
    strength = day_master["engineering_index"]["strength_level"]
    baseline = list(element_analysis["engineering_favorable_elements"])
    adjudication = day_master["classical_adjudication"]
    supporters = [day_element.value] + [
        element.value
        for element, generated in GENERATION_CYCLE.items()
        if generated == day_element
    ]
    assessment = day_master["assessment"]
    from_child = build_from_child_reference(pillars)
    from_child_review = from_child["ordinary_fuyi_requires_review"]
    if (
        assessment.get("ordinary_fuyi_requires_review")
        or assessment.get("requires_special_structure_review")
        or assessment.get("status") == "boundary_sensitive"
    ):
        baseline_avoid = []
    elif strength == "强":
        baseline_avoid = supporters
    elif strength == "弱":
        baseline_avoid = [e.value for e in Element if e.value not in supporters]
    else:
        baseline_avoid = []
    layers: list[PreferenceLayer] = [
        {
            "source": "扶抑",
            "status": "requires_structure_review" if from_child_review else "heuristic",
            "useful_elements": baseline,
            "avoid_elements": baseline_avoid,
            "source_adjudication_used": False,
        }
    ]
    if from_child_review:
        directions = from_child["conditional_direction"]["if_route_is_formed"]
        layers.append(
            {
                "source": from_child["source"]["id"],
                "status": "conditional_source_route",
                "selection_status": "requires_force_adjudication",
                "useful_elements": directions["useful_elements"],
                "avoid_elements": directions["avoid_elements"],
                "scope": "仅在从儿成立时采用；普通扶抑和从儿条件方向均未提升为全局已定喜忌。",
            }
        )
    for structure in structures:
        layers.append(
            {
                "source": structure["key"],
                "status": "pattern_candidate",
                "selection_status": "unadjudicated_legacy_reference",
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
    primary = set(baseline) if not from_child_review else set()
    primary_avoid = set(baseline_avoid) if not from_child_review else set()
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
        elif negative and value in primary_avoid:
            avoid.append(value)
        elif negative:
            conditional.append(value)
        else:
            neutral.append(value)
    engineering_reference = {
        "resolution_policy": "source_conditions_before_preference_v3",
        "assessment_status": "conditional",
        "quantity_kind": "conditional_engineering_preference",
        "source_adjudication_used": False,
        "useful_elements": useful,
        "avoid_elements": avoid,
        "conditional_elements": conditional,
        "neutral_elements": neutral,
        "scope": "沿用原工程扶抑、候选冲突与调候消解政策，仅供具名工程评分；不是原典已定喜忌。",
    }
    source_ready = (
        adjudication["status"] == "adjudicated"
        and adjudication["ordinary_fuyi_applicable"] is True
        and adjudication["body_strength"] is not None
    )
    source_useful, source_avoid = [], []
    source_conditional = [e.value for e in Element]
    source_neutral = []
    if source_ready:
        source_useful = list(element_analysis["favorable_elements"])
        source_avoid = (
            list(supporters)
            if adjudication["body_strength"] == "强"
            else (
                [e.value for e in Element if e.value not in supporters]
                if adjudication["body_strength"] == "弱"
                else []
            )
        )
        source_conditional = []
        source_neutral = [
            e.value
            for e in Element
            if e.value not in source_useful and e.value not in source_avoid
        ]
    return {
        "resolution_policy": "source_force_before_preference_v4",
        "from_child_reference": from_child,
        "assessment_status": "conditional" if source_ready else "not_adjudicated",
        "useful_elements": source_useful,
        "avoid_elements": source_avoid,
        "conditional_elements": source_conditional,
        "neutral_elements": source_neutral,
        "engineering_reference": engineering_reference,
        "classical_adjudication": adjudication,
        "layers": layers,
        "conflicts": conflicts,
        "limitations": [
            "喜忌为规则参考，非补充元素或行动处方；中和不默认喜日主本五行。",
            "格局按十神共现识别为候选，未验证成格、制化力度和破格条件。",
            "原典路径须先判相对力量、位置与救应；旧共现优先级不直接提升为已选取用路径。",
            "全局喜忌须有同次原典力量裁定及普通扶抑适用结论；未知时空列表表示未裁定，不表示没有有利或不利五行。工程参考不回填来源结论。",
            "任注从儿候选符合可观察筛选时，普通扶抑保留为条件层；不得因身弱直接取印比，也不据候选直接认证从儿成立。",
        ],
    }
