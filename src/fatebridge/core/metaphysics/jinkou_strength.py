"""A bounded inference from the online witness's twelve 贵神休旺所主 cases.

The excerpt resolves a single phase that receives no 克 within the four
positions. Multiple such phases are deliberately left unresolved; neither
seasonal ranking nor frequency is an independently attested tie breaker.
"""

from __future__ import annotations

from typing import Any

from .common import ELEMENT_CONTROLS, ELEMENT_GENERATES, status_against_anchor
from .jinkou_sources import strength_sources


def internal_strength(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 4 or {r["label"] for r in rows} != {"人元", "贵神", "将神", "地分"}:
        raise ValueError("课内旺衰需要四个不同的四位")
    if any(row["element"] not in ELEMENT_CONTROLS for row in rows):
        raise ValueError("四位五行无效")
    elements = list(dict.fromkeys(row["element"] for row in rows))
    relations = []
    for i, left in enumerate(rows):
        for j, right in enumerate(rows):
            if i == j:
                continue
            a, b = left["element"], right["element"]
            relation = (
                "克"
                if ELEMENT_CONTROLS[a] == b
                else (
                    "生"
                    if ELEMENT_GENERATES[a] == b
                    else "比和" if a == b and i < j else None
                )
            )
            if relation:
                relations.append(
                    {
                        "source_position": left["label"],
                        "target_position": right["label"],
                        "source_element": a,
                        "target_element": b,
                        "relation": relation,
                    }
                )
    candidates = [
        e
        for e in elements
        if not any(ELEMENT_CONTROLS[other] == e for other in elements)
    ]
    anchor = candidates[0] if len(candidates) == 1 else None
    return {
        "method": "guben_uncontrolled_phase_excerpt_v1",
        "status": "resolved_excerpt" if anchor else "ambiguous_excerpt",
        "anchor_element": anchor,
        "candidate_elements": candidates,
        "candidate_positions": [r["label"] for r in rows if r["element"] in candidates],
        "has_control": any(r["relation"] == "克" for r in relations),
        "relations": relations,
        "powers": {
            r["label"]: status_against_anchor(anchor, r["element"]) if anchor else None
            for r in rows
        },
        "basis": (
            "四位内仅此五行不受其余五行克制；按所选网上转录贵神休旺所主十二例共有关系推导位内旺神。"
            if anchor
            else "四位内不受克五行不唯一；所选原文例不足以裁定，不以数量或季节分数强排。"
        ),
        "source_evidence": strength_sources(),
        "scope": "仅课内旺衰；不替代四季、日下旺衰及综合取用裁决",
    }
