"""Account for supplied engineering energy without rerunning a chart calculation."""

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping, TypeGuard

ELEMENTS = "木火土金水"
ROLES = ("body", "seal", "output", "wealth", "officer_killer")
PARTS = ("physical_hidden", "synthetic_branch", "non_day_visible")


def role_elements(day_element: str) -> dict[str, str]:
    index = ELEMENTS.index(day_element)
    return dict(
        zip(
            ROLES,
            (
                ELEMENTS[index],
                ELEMENTS[(index - 1) % 5],
                ELEMENTS[(index + 1) % 5],
                ELEMENTS[(index + 2) % 5],
                ELEMENTS[(index - 2) % 5],
            ),
        )
    )


def _native(value: object) -> TypeGuard[int | float]:
    return (
        (type(value) is int or type(value) is float) and isfinite(value) and value >= 0
    )


def ledger_parts(rows: Any, kind: str) -> dict[str, dict[str, Any]]:
    """A known empty ledger is zero; an unclassifiable row makes totals unknown."""
    result: dict[str, dict[str, Any]] = {
        e: {"status": "not_supplied", "energy_unrounded": None, "refs": None}
        for e in ELEMENTS
    }
    if not isinstance(rows, list):
        return result
    element_key = "effective_element" if kind == "non_day_visible" else "element"
    energy_key = {
        "physical_hidden": "engineering_energy",
        "synthetic_branch": "energy_unrounded",
        "non_day_visible": "energy",
    }[kind]
    sums = {e: 0.0 for e in ELEMENTS}
    refs: dict[str, list[str]] = {e: [] for e in ELEMENTS}
    complete, seen = True, set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            complete = False
            continue
        element, energy, pillar = (
            row.get(element_key),
            row.get(energy_key),
            row.get("pillar"),
        )
        if kind == "physical_hidden":
            stem = row.get("stem")
            identity = f"hidden_stem_ledger:{pillar}:{row.get('stem')}"
            valid_identity = (
                pillar in ("year", "month", "day", "hour")
                and isinstance(stem, str)
                and len(stem) == 1
                and stem in "甲乙丙丁戊己庚辛壬癸"
            )
        elif kind == "synthetic_branch":
            identity = f"combination_contributions:{i}"
            valid_identity = pillar in ("year", "month", "day", "hour")
        else:
            identity = f"stem_energy_accounting.ledger:{pillar}"
            valid_identity = pillar in ("year", "month", "hour")
        if (
            element not in set(ELEMENTS)
            or not valid_identity
            or identity in seen
            or not _native(energy)
        ):
            complete = False
            continue
        seen.add(identity)
        sums[element] += energy
        refs[element].append(identity)
    for element in ELEMENTS:
        result[element] = {
            "status": "complete" if complete else "partial",
            "energy_unrounded": sums[element] if complete else None,
            "refs": refs[element],
        }
    return result


def build_energy_provenance(
    assessment: Mapping[str, Any], day_element: str
) -> dict[str, Any]:
    """Copy native receipts; never substitute rounded energy or infer missing rows."""
    synthetic = assessment.get("combination_contributions")
    stem = assessment.get("stem_energy_accounting")
    ledgers = (
        assessment.get("hidden_stem_ledger"),
        synthetic,
        stem.get("ledger") if isinstance(stem, dict) else None,
    )
    parts = {kind: ledger_parts(rows, kind) for kind, rows in zip(PARTS, ledgers)}
    totals = assessment.get("effective_elements_unrounded")
    totals = totals if isinstance(totals, dict) else {}
    fronts: dict[str, dict[str, Any]] = {}
    for role, element in role_elements(day_element).items():
        front: dict[str, Any] = {
            "element": element,
            **{kind: parts[kind][element] for kind in PARTS},
        }
        total = totals.get(element)
        front["total_energy_unrounded"] = total if _native(total) else None
        complete_parts = all(front[k]["status"] == "complete" for k in PARTS)
        attributed = (
            sum(front[k]["energy_unrounded"] for k in PARTS) if complete_parts else None
        )
        residual = (
            total - attributed if attributed is not None and _native(total) else None
        )
        front.update(
            attributed_energy_unrounded=attributed,
            residual=residual,
            status=(
                "complete"
                if residual is not None and abs(residual) <= 1e-12
                else "not_closed" if residual is not None else "partial"
            ),
        )
        fronts[role] = front
    return {
        "method_id": "same_assessment_energy_sources_v1",
        "strength_method_id": assessment.get("method_id"),
        "day_element": day_element,
        "quantity_kind": "uncalibrated_engineering_energy",
        "status": (
            "complete"
            if all(f["status"] == "complete" for f in fronts.values())
            else "partial"
        ),
        "fronts": fronts,
        "synthetic_contributions": (
            deepcopy(synthetic) if isinstance(synthetic, list) else None
        ),
        "scope": "同次未舍入工程能量分为真实藏干、支合成贡献、非日干天干三项；闭合只认证计算来源。合成贡献不是物理根，也不独立认证月令司令、通关成立或原典身印轻重。缺失或仅有展示值的账本保留未知，不重算盘。",
    }
