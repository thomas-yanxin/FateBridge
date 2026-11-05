"""Unrounded non-day stem budgets with current binding-only effects."""

from itertools import pairwise
from typing import Any, Mapping, Sequence, Tuple

from fatebridge.core.stem_order_review import stem_order_review_snapshot_line
from fatebridge.utils.data import STEM_ELEMENTS, Element

ORDER = ("year", "month", "day", "hour")
PAIRS = {frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")}


def evaluate_stem_effects(
    pillars: Mapping[str, Tuple[str, str]],
    factors: Mapping[Element, float],
    ledger: Sequence[Mapping[str, Any]],
    non_root_mass: Mapping[Element, float],
    *,
    floating_stem: float,
    rooted_stem: float,
    binding: float,
) -> dict[str, Any]:
    """Bind unique adjacent non-day pairs without changing any physical glyph."""
    names = [name for name in ORDER if name in pillars]
    roots = {
        element: sum(
            row["remaining_mass"] for row in ledger if row["element"] == element.value
        )
        for element in Element
    }
    links = [
        (left, right)
        for left, right in pairwise(names)
        if frozenset((pillars[left][0], pillars[right][0])) in PAIRS
    ]
    multipliers = {name: 1.0 for name in names if name != "day"}
    events = []
    for left, right in links:
        contested = (
            sum(left in pair for pair in links) > 1
            or sum(right in pair for pair in links) > 1
        )
        review = "day" in (left, right) or contested
        if not review:
            multipliers[left] = multipliers[right] = binding
        events.append(
            {
                "kind": "天干合",
                "positions": [left, right],
                "status": "day_master_or_contested_review" if review else "binding",
            }
        )
    rows = []
    revealed = []
    energies = {element.value: 0.0 for element in Element}
    for position, available in multipliers.items():
        stem = pillars[position][0]
        element = STEM_ELEMENTS[stem][0]
        activation = floating_stem + (rooted_stem - floating_stem) * min(
            1.0, roots[element]
        )
        energy = available * activation * factors[element]
        energies[element.value] += energy
        rows.append(
            {
                "pillar": position,
                "physical_stem": stem,
                "physical_element": element.value,
                "effective_element": element.value,
                "initial_budget": 1.0,
                "available_budget": available,
                "binding_multiplier": available,
                "activation_root_mass": roots[element],
                "activation": activation,
                "seasonal_factor": factors[element],
                "energy": energy,
                "quantity_kind": "non_day_stem_budget_weighted_energy",
            }
        )
        revealed.append(
            {
                "pillar": position,
                "stem": stem,
                "root_mass": round(roots[element], 6),
                "non_root_combination_mass": round(non_root_mass[element], 6),
                "root_activation_policy": "remaining_physical_hidden_stems_only_v1",
                "effective_element": element.value,
                "energy_element": element.value,
                "effective_root_mass": roots[element],
                "energy": round(energy, 6),
            }
        )
    return {
        "method_id": "non_day_stem_binding_v1",
        "arithmetic_policy": "unrounded_stem_energy_v1",
        "ledger": rows,
        "revealed_stems": revealed,
        "relations": events,
        "energies": energies,
        "scope": "每个非日干原字预算1；唯一邻合且不含日干者合绊，预算作用于未舍入能量。不计算局部成化或日主化气格。",
    }


def stem_energy_snapshot_lines(assessment: Mapping[str, Any]) -> list[str]:
    """Explain only supplied applied energy; do not calculate another chart."""
    receipt = assessment.get("stem_energy_accounting")
    if not receipt or not receipt.get("ledger"):
        return []
    names = {"year": "年干", "month": "月干", "hour": "时干"}
    details = [
        f"{names[r['pillar']]}{r['physical_stem']}：预算{r['available_budget']:g}"
        f"×根激活{r['activation']:.6f}×季相{r['seasonal_factor']:g}"
        f"＝{r['energy']:.6f}"
        for r in receipt["ledger"]
    ]
    lines = [
        "天干计力（工程量）："
        + "；".join(details)
        + "。计算用未取整值，以上仅作展示。",
        "本次五合采用既有合绊政策，未据此认定局部成化或日主化气格。",
    ]
    line = stem_order_review_snapshot_line(receipt.get("source_order_review") or {})
    if line:
        lines.append(line)
    return lines
