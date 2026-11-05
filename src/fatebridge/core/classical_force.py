"""Separate body, seal and other fronts without inventing classical strength.

The selected text explicitly distinguishes 身重印轻 and 身轻印重 (PDF73).
An engineering sum of body + seal cannot adjudicate those independent labels.
Reuse the supplied calculation; never recompute a missing assessment here.
"""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from math import isfinite
from typing import Any, Mapping, Tuple

from fatebridge.core.classical_roots import SOURCE as ROOT_SOURCE
from fatebridge.core.classical_roots import classify_classical_root
from fatebridge.core.classical_stages import STAGE_PROFILE_ID
from fatebridge.core.energy_provenance import build_energy_provenance
from fatebridge.utils.data import (
    BRANCH_CONFLICTS,
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
)

ORDER = ("year", "month", "day", "hour")
SOURCE = {
    **ROOT_SOURCE,
    "id": "ziping_body_seal_distinction_v1",
    "title": "秘本子平真诠·论印绶（身重印轻与身轻印重）",
    "pdf_pages": [73, 74],
    "printed_pages": [64, 65],
}
GODS = {
    "body": ("比肩", "劫财"),
    "seal": ("正印", "偏印"),
    "output": ("食神", "伤官"),
    "wealth": ("正财", "偏财"),
    "officer_killer": ("正官", "七杀"),
}


def _source_roots_by_stem(
    pillars: Mapping[str, Tuple[str, str]], elements: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Classify actual visible/hidden stems without inferring effective force."""
    observed = {stem for stem, _ in pillars.values()} | {
        stem for _, branch in pillars.values() for stem in BRANCH_HIDDEN_STEMS[branch]
    }
    roles = {element: role for role, element in elements.items()}
    result = []
    for stem in "甲乙丙丁戊己庚辛壬癸":
        if stem not in observed:
            continue
        roots = []
        for position in ORDER:
            branch = pillars[position][1]
            root = classify_classical_root(stem, branch)
            roots.append(
                {
                    "pillar": position,
                    **{
                        key: root[key]
                        for key in (
                            "stem",
                            "branch",
                            "life_stage",
                            "kind",
                            "hidden_element_present",
                            "matching_hidden_stems",
                            "source_weight_class",
                        )
                    },
                    "clash_partners": [
                        other
                        for other in ORDER
                        if other != position
                        and BRANCH_CONFLICTS[branch] == pillars[other][1]
                    ],
                }
            )
        result.append(
            {
                "stem": stem,
                "role": roles[STEM_ELEMENTS[stem][0]],
                "is_day_master": stem == pillars["day"][0],
                "visible_positions": [p for p in ORDER if pillars[p][0] == stem],
                "roots": roots,
                "force_status": "not_adjudicated",
            }
        )
    return result


def build_force_components(
    pillars: Mapping[str, Tuple[str, str]],
    assessment: Mapping[str, Any],
    stars: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Keep physical root facts and engineering energies in separate fields."""
    body = STEM_ELEMENTS[pillars["day"][0]][0]
    seal = next(e for e, child in GENERATION_CYCLE.items() if child == body)
    officer = next(e for e, target in DESTRUCTION_CYCLE.items() if target == body)
    elements = {
        "body": body,
        "seal": seal,
        "output": GENERATION_CYCLE[body],
        "wealth": DESTRUCTION_CYCLE[body],
        "officer_killer": officer,
    }
    raw_energies = assessment.get("effective_elements")
    energies: dict[str, Any] = raw_energies if isinstance(raw_energies, dict) else {}
    available = all(e.value in energies for e in elements.values())
    raw_precise = assessment.get("effective_elements_unrounded")
    precise = raw_precise if isinstance(raw_precise, dict) else {}
    exact_available = all(
        type(precise.get(e.value)) in (int, float)
        and isfinite(precise[e.value])
        and precise[e.value] >= 0
        for e in elements.values()
    )
    supplied_ledger = assessment.get("hidden_stem_ledger")
    components: dict[str, dict[str, Any]] = {}
    for role, element in elements.items():
        components[role] = {
            "element": element.value,
            "ten_gods": list(GODS[role]),
            "physical_hidden_roots": [
                {
                    "pillar": n,
                    "branch": pillars[n][1],
                    "stem": s,
                    "hidden_rank": rank,
                }
                for n in ORDER
                for rank, s in enumerate(BRANCH_HIDDEN_STEMS[pillars[n][1]])
                if STEM_ELEMENTS[s][0] == element
            ],
            "revealed_positions": [
                n
                for n in ORDER
                if n != "day" and STEM_ELEMENTS[pillars[n][0]][0] == element
            ],
            "source_star_refs": [
                s["evidence_id"] for god in GODS[role] for s in stars.get(god, [])
            ],
            "engineering_energy": energies[element.value] if available else None,
            "engineering_energy_unrounded": (
                precise[element.value] if exact_available else None
            ),
            "remaining_hidden_roots": (
                [
                    deepcopy(row)
                    for row in supplied_ledger
                    if row["element"] == element.value
                ]
                if isinstance(supplied_ledger, list)
                else None
            ),
        }
    basis = "unrounded_same_assessment" if exact_available else "not_supplied"
    energy_key = "engineering_energy_unrounded"
    body_energy = components["body"][energy_key]
    seal_energy = components["seal"][energy_key]
    relation = "not_supplied"
    body_share = None
    if exact_available:
        relation = (
            "body_greater"
            if body_energy > seal_energy
            else "seal_greater" if seal_energy > body_energy else "equal"
        )
        if body_energy + seal_energy > 0:
            body_share = body_energy / (body_energy + seal_energy)
    float_relation = relation
    receipt = assessment.get("threshold_arithmetic") or {}
    rational = receipt.get("energies_exact")
    rational_energy = {}
    # Consume only a complete, correctly identified same-assessment receipt.
    # Partial evidence never causes an unrequested recalculation.
    if isinstance(rational, dict) and receipt.get("day_element") == body.value:
        try:
            rational_energy = {
                e.value: Fraction(rational[e.value]) for e in elements.values()
            }
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            rational_energy = {}
        if any(value < 0 for value in rational_energy.values()):
            rational_energy = {}
    comparison_basis = basis
    body_share_exact = None
    if rational_energy:
        body_exact, seal_exact = (
            rational_energy[body.value],
            rational_energy[seal.value],
        )
        relation = (
            "body_greater"
            if body_exact > seal_exact
            else "seal_greater" if seal_exact > body_exact else "equal"
        )
        comparison_basis = "exact_rational_same_assessment"
        if body_exact + seal_exact:
            body_share_exact = str(body_exact / (body_exact + seal_exact))
    return {
        "method_id": "body_seal_force_components_v1",
        "source": deepcopy(SOURCE),
        "components": components,
        "energy_provenance": build_energy_provenance(assessment, body.value),
        "source_root_observations": {
            "method_id": "observed_stem_root_categories_v1",
            "life_stage_profile_id": STAGE_PROFILE_ID,
            "source": deepcopy(ROOT_SOURCE),
            "stems": _source_roots_by_stem(pillars, elements),
            "scope": "逐干列原局根类，区分身、印及其他角色；非日干的禄刃是该干根位，不认证命主月刃格。天干位置含日干但不增加支持票，藏干出现不冒作透干。冲只列对应位置，不自动删除根；未裁定根损、有效力量、合化或全局身印轻重。",
        },
        "engineering_composition": {
            "status": (
                "supplied_calculation"
                if exact_available or available
                else "not_supplied"
            ),
            "ratio_basis": basis,
            "strength_method_id": assessment.get("method_id"),
            "strength_level": assessment.get("strength_level"),
            "support_share": assessment.get("support_share") if available else None,
            "body_within_support_share": body_share,
            "body_seal_energy_relation": relation,
            "comparison_basis": comparison_basis,
            "float_body_seal_energy_relation": float_relation,
            "body_within_support_exact": body_share_exact,
            "body_energy_exact": (
                str(rational_energy[body.value]) if rational_energy else None
            ),
            "seal_energy_exact": (
                str(rational_energy[seal.value]) if rational_energy else None
            ),
            "quantity_kind": "uncalibrated_engineering_energy",
        },
        "classical_adjudication": {
            "body_strength": "not_adjudicated",
            "seal_weight": "not_adjudicated",
            "body_seal_relation": "not_adjudicated",
        },
        "scope": "原典区分身与印的力量；本表分别列事实与现有工程能量，不由身印总量判身重印重，不把身轻等同印轻或把印重等同身强。",
        "limitations": [
            "engineering_energy保留六位展示值；身印比较优先用同次完整energies_exact，comparison_basis另标。原浮点比较与占比保留，ratio_basis不改；旧回执依现有未取整或展示值比较，不补算缺失分量。精确预算相等不等于原典身印力量相等。",
            "physical_hidden_roots列原局成分；remaining_hidden_roots复制同次工程作用后的预算。二者都不独立裁定原典有效根力。",
            "能量与占比沿用同次工程模型，不是原典系数、现实概率或独立验收标签。",
            "日干是被评对象，不作额外透干支持票；身印各自轻重及身食财相对力量仍未裁定。",
        ],
    }
