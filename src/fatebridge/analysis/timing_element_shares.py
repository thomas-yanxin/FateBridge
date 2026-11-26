"""Calculate changes in structural element shares for timed pillars."""

from fractions import Fraction
from typing import Literal, TypedDict

from fatebridge.core.elements import ElementAnalysis
from fatebridge.utils.data import Element


class ElementShareChange(TypedDict):
    original: float
    new: float
    change: float
    change_type: Literal["占比上升", "占比下降", "占比不变"]


class ElementShareCountingBasis(TypedDict):
    visible_stem: float
    branch_element: float
    each_hidden_stem: float
    timing_layer_weights: Literal["equal"]
    meaning: Literal["structural_token_counts_not_effective_strength"]


class TimingElementEffects(TypedDict):
    method_id: Literal["structural_element_share_v1"]
    counting_basis: ElementShareCountingBasis
    interpretation_scope: str
    original_distribution: dict[str, float]
    new_distribution: dict[str, float]
    element_changes: dict[str, ElementShareChange]
    overall_effect: str


def analyze_element_strength_changes(
    original_pillars: dict[str, tuple[str, str]],
    timing_pillars: dict[str, dict[str, str]],
    original_element_counts: dict[Element, float] | None = None,
) -> TimingElementEffects:
    """计算时运叠加前后的结构占比与百分点差。"""
    source_counts = original_element_counts or ElementAnalysis.count_elements(
        original_pillars
    )
    original_counts = {
        element: Fraction(source_counts.get(element, 0.0)) for element in Element
    }
    timing_counts = ElementAnalysis.count_elements(
        {
            key: (pillar["stem"], pillar["branch"])
            for key, pillar in timing_pillars.items()
        }
    )
    combined_counts = {
        element: original_counts[element] + Fraction(timing_counts.get(element, 0.0))
        for element in Element
    }
    original_total = sum(original_counts.values())
    combined_total = sum(combined_counts.values())

    original_distribution = {}
    new_distribution = {}
    element_changes: dict[str, ElementShareChange] = {}
    for element in Element:
        element_name = element.value
        original_share = (
            100 * original_counts[element] / original_total if original_total else 0
        )
        new_share = (
            100 * combined_counts[element] / combined_total if combined_total else 0
        )
        # note (elements): Keep half-unit counts exact until percent shares are serialized.
        change = new_share - original_share
        original_distribution[element_name] = float(original_share)
        new_distribution[element_name] = float(new_share)

        element_changes[element_name] = {
            "original": original_distribution[element_name],
            "new": new_distribution[element_name],
            "change": float(change),
            "change_type": (
                "占比上升" if change > 0 else "占比下降" if change < 0 else "占比不变"
            ),
        }

    return {
        "method_id": "structural_element_share_v1",
        "counting_basis": {
            "visible_stem": 1.0,
            "branch_element": 1.0,
            "each_hidden_stem": 0.5,
            "timing_layer_weights": "equal",
            "meaning": "structural_token_counts_not_effective_strength",
        },
        "interpretation_scope": "干支与藏干的结构计数占比；未计算行运后有效旺衰、合化和喜忌，不是吉凶评分或成功概率。",
        "original_distribution": original_distribution,
        "new_distribution": new_distribution,
        "element_changes": element_changes,
        "overall_effect": (
            "五行结构占比发生变化（不代表旺衰或吉凶）"
            if any(change["change"] for change in element_changes.values())
            else "五行结构占比不变（不代表力量不变）"
        ),
    }
