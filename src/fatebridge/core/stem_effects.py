"""Unrounded, budgeted local stem effects; original chart identities stay intact.

Local non-day-stem conversion is distinct from day-master 化氣格 and from
殺生印's generating passage. The conservative readiness conditions below
are an explicit engineering formalization, not a complete source verdict.
"""

from copy import deepcopy
from itertools import pairwise
from typing import Any, Mapping, Sequence, Tuple

from fatebridge.core.classical_roots import classify_classical_root
from fatebridge.core.stem_order_review import stem_order_review_snapshot_line
from fatebridge.utils.data import (
    BRANCH_ELEMENTS,
    DESTRUCTION_CYCLE,
    STEM_ELEMENTS,
    Element,
)

ORDER = ("year", "month", "day", "hour")
PAIRS = {
    frozenset(p): Element(e)
    for p, e in (
        ("甲己", "土"),
        ("乙庚", "金"),
        ("丙辛", "水"),
        ("丁壬", "木"),
        ("戊癸", "火"),
    )
}
SOURCE = {
    "id": "ditian_ren_local_stem_conversion_v1",
    "title": "任注滴天髓闡微·天干、官殺、化象及合局",
    "author": "任鐵樵增注，李雨田校訂兼發行",
    "edition": "上海大東書局經售，1947年4月初版",
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
    "pdf_pages": [76, 209, 210, 214, 374, 375, 376, 412],
    "scope": "选任注，不混用其所驳原注的秋冬一概可化说。化神衰旺与能否成化分别记录；本方法只处理唯一邻合且不含日干的局部作用，不认证日主化气格、合去成败或整个原典。",
}


def _opposes(a: Element, b: Element) -> bool:
    return DESTRUCTION_CYCLE[a] == b or DESTRUCTION_CYCLE[b] == a


def evaluate_stem_effects(
    pillars: Mapping[str, Tuple[str, str]],
    phases: Mapping[str, str],
    factors: Mapping[Element, float],
    ledger: Sequence[Mapping[str, Any]],
    non_root_mass: Mapping[Element, float],
    *,
    floating_stem: float,
    rooted_stem: float,
    binding: float,
    minimum_retention: float,
    enable_transformation: bool,
) -> dict[str, Any]:
    """Assign each original non-day stem one budget, then activate its effect.

    A categorical conversion changes only the applied element. Its original
    glyph, ten-god occurrence, branch roots and revelation facts are preserved.
    Root activation uses actual hidden roots of that applied element, never
    synthetic branch/stem contributions. Seasonal energy need not be conserved;
    the conserved unit is the original stem budget, not weighted force.
    """
    names = [n for n in ORDER if n in pillars]
    roots = {
        e: sum(r["remaining_mass"] for r in ledger if r["element"] == e.value)
        for e in Element
    }
    visible = {STEM_ELEMENTS[pillars[n][0]][0] for n in names}
    month = BRANCH_ELEMENTS[pillars["month"][1]][0]
    links = [
        (a, b)
        for a, b in pairwise(names)
        if frozenset((pillars[a][0], pillars[b][0])) in PAIRS
    ]
    applied = {n: STEM_ELEMENTS[pillars[n][0]][0] for n in names if n != "day"}
    multipliers = {n: 1.0 for n in applied}
    decisions = []
    events = []
    for a, b in links:
        target = PAIRS[frozenset((pillars[a][0], pillars[b][0]))]
        contested = sum(a in p for p in links) > 1 or sum(b in p for p in links) > 1
        outside = "day" in (a, b) or contested
        blockers = []
        for position in (a, b):
            stem = pillars[position][0]
            original = STEM_ELEMENTS[stem][0]
            if not _opposes(original, target):
                continue
            for root_position in names:
                branch = pillars[root_position][1]
                category = classify_classical_root(stem, branch)
                anchored = (
                    BRANCH_ELEMENTS[branch][0] == original
                    or category["source_weight_class"] == "heavy"
                )
                rows = [
                    r
                    for r in ledger
                    if r["pillar"] == root_position and r["element"] == original.value
                ]
                initial = sum(r["initial_mass"] for r in rows)
                remaining = sum(r["remaining_mass"] for r in rows)
                if (
                    anchored
                    and initial > 0
                    and remaining >= initial * minimum_retention
                ):
                    blockers.append(
                        {
                            "stem_pillar": position,
                            "stem": stem,
                            "root_pillar": root_position,
                            "branch": branch,
                            "initial_mass": initial,
                            "remaining_mass": remaining,
                            "retention_fraction": remaining / initial,
                            "kind": category["kind"],
                            "source_weight_class": category["source_weight_class"],
                        }
                    )
        conditions = {
            "unique_adjacent_non_day_pair": not outside,
            "target_physically_revealed": target in visible,
            "target_has_actual_hidden_roots": roots[target] > 0,
            "month_principal_not_opposed_to_target": not _opposes(month, target),
            "no_surviving_anchored_opposing_partner_root": not blockers,
        }
        converted = enable_transformation and all(conditions.values())
        status = (
            "day_master_or_contested_review"
            if outside
            else "conditioned_transformation" if converted else "binding"
        )
        if not outside:
            for position in (a, b):
                if converted:
                    applied[position] = target
                else:
                    multipliers[position] = binding
        decisions.append(
            {
                "positions": [a, b],
                "physical_stems": [pillars[a][0], pillars[b][0]],
                "target": target.value,
                "status": status,
                "conditions": conditions,
                "anchored_opposing_roots": blockers,
                "target_seasonal_phase": phases[target.value],
                "transformation_enabled": enable_transformation,
                "source_ref": SOURCE["id"],
                "classical_formation": "not_adjudicated",
            }
        )
        events.append(
            {
                "kind": "天干合",
                "positions": [a, b],
                "status": status,
                "target": target.value,
                "source_id": SOURCE["id"],
                "scope": "局部作用元素，不改原柱字与藏干，不认证日主化气格。",
            }
        )
    rows = []
    revealed = []
    energies = {e.value: 0.0 for e in Element}
    for position, effective in applied.items():
        stem = pillars[position][0]
        physical = STEM_ELEMENTS[stem][0]
        activation = floating_stem + (rooted_stem - floating_stem) * min(
            1.0, roots[effective]
        )
        available = multipliers[position]  # original budget is exactly one
        energy = available * activation * factors[effective]
        energies[effective.value] += energy
        rows.append(
            {
                "pillar": position,
                "physical_stem": stem,
                "physical_element": physical.value,
                "effective_element": effective.value,
                "initial_budget": 1.0,
                "available_budget": available,
                "binding_multiplier": multipliers[position],
                "activation_root_mass": roots[effective],
                "activation": activation,
                "seasonal_factor": factors[effective],
                "energy": energy,
                "quantity_kind": "non_day_stem_budget_weighted_energy",
            }
        )
        revealed.append(
            {
                "pillar": position,
                "stem": stem,
                "root_mass": round(roots[physical], 6),
                "non_root_combination_mass": round(non_root_mass[physical], 6),
                "root_activation_policy": "effective_element_actual_hidden_roots_v1",
                "effective_element": effective.value,
                "energy_element": effective.value,
                "effective_root_mass": roots[effective],
                "energy": round(energy, 6),
            }
        )
    return {
        "method_id": "local_non_day_stem_effects_v1",
        "arithmetic_policy": "unrounded_stem_energy_v1",
        "transformation_enabled": enable_transformation,
        "source": deepcopy(SOURCE),
        "decisions": decisions,
        "ledger": rows,
        "revealed_stems": revealed,
        "relations": events,
        "energies": energies,
        "parameters": {
            "floating_stem": floating_stem,
            "rooted_stem": rooted_stem,
            "binding": binding,
            "minimum_anchored_retention": minimum_retention,
        },
        "scope": "每个非日干预算1，原字与作用元素分开，成化按新元素的真实根与季相求作用能量；守恒指天干预算，不是季节加权能量。没有新增藏干或透出之字；原局实数不改。条件为工程形式化，未认证原典完整成化、喜忌或日主化气格。",
    }


def stem_energy_snapshot_lines(assessment: Mapping[str, Any]) -> list[str]:
    """Explain only supplied applied energy; never run the conversion prototype."""
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
