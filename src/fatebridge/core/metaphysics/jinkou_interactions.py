"""Ordered four-position facts under fourteen identified Jingben clauses.

Adjacent generation and separated control may coexist. None of these
predicates adjudicates strength, transformation or comprehensive use.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from .common import ELEMENT_CONTROLS, ELEMENT_GENERATES
from .jinkou_sources import SCAN_SHA256, SCAN_URL

POSITIONS = ("人元", "贵神", "将神", "地分")
# Each condition keeps its direction. The battle clauses permit either one;
# a chain/joint clause needs every condition, never just one matching edge.
RULES = (
    ("outer_battle", "外战", "any", ((0, 1, "克"), (1, 0, "克")), (71,)),
    ("inner_battle", "内战", "any", ((2, 3, "克"), (3, 2, "克")), (71,)),
    ("heju", "合局", "all", ((0, 1, "生"), (3, 2, "生")), (67,)),
    (
        "top_down_generation",
        "自上次第生下",
        "all",
        ((0, 1, "生"), (1, 2, "生"), (2, 3, "生")),
        (68,),
    ),
    (
        "bottom_up_generation",
        "自下重重生上",
        "all",
        ((3, 2, "生"), (2, 1, "生"), (1, 0, "生")),
        (68,),
    ),
    (
        "top_down_control",
        "自上次第克下",
        "all",
        ((0, 1, "克"), (1, 2, "克"), (2, 3, "克")),
        (72,),
    ),
    (
        "bottom_up_control",
        "自下次第克上",
        "all",
        ((3, 2, "克"), (2, 1, "克"), (1, 0, "克")),
        (71, 72),
    ),
    (
        "lower_pair_controls_god",
        "将方同克神",
        "all",
        ((2, 1, "克"), (3, 1, "克")),
        (68,),
    ),
    (
        "upper_pair_controls_general",
        "干神同克将",
        "all",
        ((0, 2, "克"), (1, 2, "克")),
        (68,),
    ),
    ("zheng_bi", "正比", "all", ((0, 3, "比和"),), (62,)),
    ("jin_bi", "近比", "all", ((0, 1, "比和"),), (62,)),
    ("yuan_bi", "远比", "all", ((3, 2, "比和"),), (62,)),
    ("ci_bi", "次比", "all", ((1, 2, "比和"),), (62,)),
    ("he_bi", "合比", "all", ((0, 1, "比和"), (1, 2, "比和"), (2, 3, "比和")), (62,)),
)


def position_interactions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if [r.get("label") for r in rows] != list(POSITIONS):
        raise ValueError("四位生克须按人元、贵神、将神、地分排列")
    if any(r.get("element") not in ELEMENT_CONTROLS for r in rows):
        raise ValueError("四位生克需要有效五行")
    pairs = []
    for i, j in combinations(range(4), 2):
        upper, lower = rows[i], rows[j]
        a, b = upper["element"], lower["element"]
        relation = (
            "比和"
            if a == b
            else (
                "上生下"
                if ELEMENT_GENERATES[a] == b
                else (
                    "下生上"
                    if ELEMENT_GENERATES[b] == a
                    else "上克下" if ELEMENT_CONTROLS[a] == b else "下克上"
                )
            )
        )
        pairs.append(
            dict(
                upper_position=upper["label"],
                lower_position=lower["label"],
                upper_element=a,
                lower_element=b,
                adjacent=j - i == 1,
                relation=relation,
            )
        )
    evaluations = []
    for rule_id, name, quantifier, edges, pages in RULES:
        checks = []
        for source, target, relation in edges:
            a, b = rows[source]["element"], rows[target]["element"]
            matched = (
                a == b
                if relation == "比和"
                else (
                    ELEMENT_GENERATES[a] == b
                    if relation == "生"
                    else ELEMENT_CONTROLS[a] == b
                )
            )
            checks.append(
                dict(
                    source_position=POSITIONS[source],
                    target_position=POSITIONS[target],
                    source_element=a,
                    target_element=b,
                    relation=relation,
                    matched=matched,
                )
            )
        values = [c["matched"] for c in checks]
        evaluations.append(
            dict(
                id=rule_id,
                name=name,
                quantifier=quantifier,
                matched=any(values) if quantifier == "any" else all(values),
                condition_checks=checks,
                original_pdf_pages=list(pages),
            )
        )
    return {
        "ruleset_id": "jinkou_jingben_position_interactions_v1",
        "source_title": "校正京本金口诀·五比同类、四位相生、四位相克、四爻生克颂",
        "source_url": SCAN_URL,
        "source_sha256": SCAN_SHA256,
        "original_pdf_pages": [62, 67, 68, 69, 70, 71, 72],
        "position_order": list(POSITIONS),
        "pairs": pairs,
        "source_rule_count": len(RULES),
        "rule_evaluations": evaluations,
        "matched_rule_ids": [r["id"] for r in evaluations if r["matched"]],
        "has_any_control": any(p["relation"] in {"上克下", "下克上"} for p in pairs),
        "complete_classical_conformance": False,
        "scope": "仅识别所列十四条位置结构，允许同时命中；逐位相生、合局仍可同时存在隔位相克，不等于四位俱无克。合局不等于三合成局或五行合化，合比不等于一类朝元。不裁定完整日下旺衰、旺神优先级或综合取用，不据结构保证人物意图、冲突或事件成败。",
    }
