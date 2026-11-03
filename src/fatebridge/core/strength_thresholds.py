"""Exact engineering threshold decisions, conditional on recorded relations.

This reconstructs budget arithmetic only. It does not decide whether a clash,
combination, root qualification or classical formation should be effective.
"""

from fractions import Fraction
from typing import Any, Mapping, Sequence

from fatebridge.core.root_budget import initial_hidden_budgets
from fatebridge.utils.data import (
    GENERATION_CYCLE,
    STEM_ELEMENTS,
    Element,
)

ORDER = ("year", "month", "day", "hour")


def exact_threshold_decision(
    pillars: Mapping[str, tuple[str, str]],
    phases: Mapping[str, str],
    phase_factors: Mapping[str, float],
    parameters: Mapping[str, float],
    relations: Sequence[Mapping[str, Any]],
    float_numerical_label: str,
    *,
    external_root_retention: Mapping[str, Mapping[Element, Fraction]] | None = None,
    external_stem_retention: Mapping[str, Fraction] | None = None,
    include_hidden_ledger: bool = False,
) -> dict[str, Any]:
    """Compare declared decimal coefficients without widening their thresholds."""
    q = {key: Fraction(str(value)) for key, value in parameters.items()}
    # Entries keep their original stem identity; None denotes synthetic budget.
    initial = initial_hidden_budgets(
        {name: pillars[name][1] for name in ORDER},
        {
            name: q["branch_budget"] * (q["month_multiplier"] if name == "month" else 1)
            for name in ORDER
        },
    )
    tokens: dict[str, list[list[Any]]] = {
        name: [list(row) for row in rows] for name, rows in initial.items()
    }
    losses = {name: {e: Fraction(1) for e in Element} for name in ORDER}

    for event in relations:
        kind, status = event["kind"], event["status"]
        positions = event["positions"]
        if kind in {"三会", "三合", "六合", "半合"}:
            if status in {"conditioned_transformation", "partial_tendency"}:
                target = Element(event["target"])
                transfer = q[
                    (
                        "transformation_transfer"
                        if status == "conditioned_transformation"
                        else "partial_transfer"
                    )
                ]
                for name in positions:
                    moved = Fraction(0)
                    for token in tokens[name]:
                        if token[1] != target:
                            amount = token[2] * transfer
                            token[2] -= amount
                            moved += amount
                    tokens[name].append([None, target, moved])
            elif status == "binding":
                for name in positions:
                    for element in Element:
                        losses[name][element] = min(losses[name][element], q["binding"])
        if kind == "六冲" and status == "active":
            for name, multiplier in event.get("root_multipliers", {}).items():
                for element in Element:
                    losses[name][element] = min(
                        losses[name][element], Fraction(str(multiplier))
                    )
        if "storage_effect" in event:
            for row in event["storage_effect"]["root_effects"]:
                name, element = row["pillar"], Element(row["element"])
                losses[name][element] = min(
                    losses[name][element],
                    Fraction(str(row["event_retention_multiplier"])),
                )
        elif status == "active" and kind in {"刑", "自刑"}:
            for name in positions:
                for element in Element:
                    losses[name][element] = min(losses[name][element], q["punishment"])

    if external_root_retention is not None:
        for name, elements in external_root_retention.items():
            for element, retention in elements.items():
                losses[name][element] = min(losses[name][element], retention)

    factors = {
        element: 1
        + (Fraction(str(phase_factors[phases[element.value]])) - 1)
        * q["seasonal_spread"]
        for element in Element
    }
    visible = {stem for stem, _ in pillars.values()}
    roots = {e: Fraction(0) for e in Element}
    energy = {e: Fraction(0) for e in Element}
    hidden_ledger = []
    for name, entries in tokens.items():
        for stem, element, mass in entries:
            remaining = mass * losses[name][element]
            if stem is not None:
                roots[element] += remaining
                if include_hidden_ledger:
                    hidden_ledger.append(
                        {
                            "pillar": name,
                            "stem": stem,
                            "element": element.value,
                            "remaining_mass_exact": str(remaining),
                        }
                    )
            energy[element] += (
                remaining
                * factors[element]
                * (q["reveal_multiplier"] if stem in visible else 1)
            )
    binding = {name: Fraction(1) for name in ORDER if name != "day"}
    for event in relations:
        if event["kind"] == "天干合" and event["status"] == "binding":
            for name in event["positions"]:
                binding[name] = q["binding"]
    if external_stem_retention is not None:
        for name, retention in external_stem_retention.items():
            binding[name] = min(binding[name], retention)
    for name, available in binding.items():
        element = STEM_ELEMENTS[pillars[name][0]][0]
        activation = q["floating_stem"] + (q["rooted_stem"] - q["floating_stem"]) * min(
            Fraction(1), roots[element]
        )
        energy[element] += available * activation * factors[element]
    body = STEM_ELEMENTS[pillars["day"][0]][0]
    parent = next(e for e, child in GENERATION_CYCLE.items() if child == body)
    support = energy[body] + energy[parent]
    weaken = sum(energy[e] for e in Element if e not in {body, parent})
    share = support / (support + weaken) if support + weaken else Fraction(1, 2)
    grade = (
        "强"
        if share > q["strong_share"]
        else "弱" if share < q["weak_share"] else "中和"
    )
    return {
        **({"hidden_ledger_exact": hidden_ledger} if include_hidden_ledger else {}),
        "method_id": "exact_rational_strength_thresholds_v1",
        "basis": "declared_decimal_policy_conditioned_on_recorded_relations",
        "day_element": body.value,
        "energies_exact": {
            element.value: str(value) for element, value in energy.items()
        },
        "physical_root_unit_comparison": {
            "masses_exact": {
                element.value: str(value) for element, value in roots.items()
            },
            "unit_threshold_exact": "1",
            "at_least_unit": {
                element.value: value >= 1 for element, value in roots.items()
            },
            "visible_non_day_elements": {
                name: STEM_ELEMENTS[pillars[name][0]][0].value
                for name in ("year", "month", "hour")
            },
            "comparison_basis": "exact_rational_physical_hidden_budget",
            "quantity_kind": "remaining_physical_hidden_stem_budget",
            "effective_classical_root_force": "not_adjudicated",
        },
        "support_exact": str(support),
        "weaken_exact": str(weaken),
        "share_exact": str(share),
        "weak_threshold_exact": str(q["weak_share"]),
        "strong_threshold_exact": str(q["strong_share"]),
        "support_above_half": share > Fraction(1, 2),
        "special_lower_threshold_exact": "3/20",
        "special_upper_threshold_exact": "17/20",
        "requires_special_structure_review": share < Fraction(3, 20)
        or share > Fraction(17, 20),
        "numerical_label": grade,
        "legacy_float_numerical_label": float_numerical_label,
        "float_comparison_differs": grade != float_numerical_label,
        "calculation_effect": "threshold_comparison_only",
        "scope": "既定十进制工程系数、几何藏干份额及实际藏干根预算单位门槛的精确比较；关系成立条件沿用同次记录。原浮点能量及份额另保留，不认证系数、根的有效力量、通关或现实精度。",
    }


def threshold_snapshot_lines(assessment: Mapping[str, Any]) -> list[str]:
    """Explain the supplied difference without recalculating another chart."""
    receipt = assessment.get("threshold_arithmetic") or {}
    lines = []
    if receipt.get("float_comparison_differs"):
        lines.append(
            f"旺衰阈值算术：既定工程预算的精确份额为{receipt['share_exact']}，"
            f"数值档为{receipt['numerical_label']}；浮点比较原为"
            f"{receipt['legacy_float_numerical_label']}，该偏差已纠正。"
            "结构规则另审；此处不增加原典或现实准确率。"
        )
    if (
        "requires_special_structure_review" in receipt
        and "support_share" in assessment
        and receipt["requires_special_structure_review"]
        != (assessment["support_share"] < 0.15 or assessment["support_share"] > 0.85)
    ):
        lines.append(
            f"特殊结构复核阈值：精确份额{receipt['share_exact']}，采用严格小于3/20或大于17/20；"
            f"同次复核标记为{receipt['requires_special_structure_review']}，已纠正浮点边界误报。"
            "这是工程筛查标记，不裁定从格、化格或原典身印力量。"
        )
    roots = receipt.get("physical_root_unit_comparison") or {}
    if (
        roots.get("rooted_controller_stems") is not None
        and roots.get("legacy_float_rooted_controller_stems") is not None
        and (
            roots["rooted_controller_stems"]
            != roots["legacy_float_rooted_controller_stems"]
            or roots.get("rooted_wealth_visible")
            != roots.get("legacy_float_rooted_wealth_visible")
        )
    ):
        lines.append(
            "财官根量的工程比较已按精确预算更正："
            f"官杀有根透干数由{roots['legacy_float_rooted_controller_stems']}"
            f"改为{roots['rooted_controller_stems']}，"
            f"财有根标记由{roots.get('legacy_float_rooted_wealth_visible')}"
            f"改为{roots.get('rooted_wealth_visible')}。"
            "这只修正既定单位门槛的比较，不裁定原典有效根力或通关成立。"
        )
    return lines
