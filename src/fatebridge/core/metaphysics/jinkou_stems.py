"""Jingben daily stems, kept distinct from gods' inherent identities."""

from __future__ import annotations

from typing import Any

from ...utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from .common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    SIX_HARMONY_BRANCHES,
    sexagenary_index_for,
    stem_element_text,
    xun_head_for_ganzhi,
)
from .jinkou_sources import SCAN_SHA256, SCAN_URL

WUZI_DUN_START = dict(zip("甲乙丙丁戊己庚辛壬癸", "甲丙戊庚壬甲丙戊庚壬"))
STEM_PAIRS = (
    ("甲己", "土"),
    ("乙庚", "金"),
    ("丙辛", "水"),
    ("丁壬", "木"),
    ("戊癸", "火"),
)
RELATIONS = (
    ("god_generates_general", "神干生将干", "贵神", "将神", "生", None),
    ("general_generates_god", "将干生神干", "将神", "贵神", "生", None),
    ("god_controls_general", "神干克将干", "贵神", "将神", "克", "贼动同类"),
    ("general_controls_god", "将干克神干", "将神", "贵神", "克", "财动同类"),
)


def wuzidun_stem(day_stem: str, branch: str) -> str:
    """The established one-cycle Zi-to-Hai policy; not a continued next 子."""
    if day_stem not in WUZI_DUN_START or branch not in EARTHLY_BRANCHES:
        raise ValueError("五子元遁需要有效日干与地支")
    return HEAVENLY_STEMS[
        (
            HEAVENLY_STEMS.index(WUZI_DUN_START[day_stem])
            + EARTHLY_BRANCHES.index(branch)
        )
        % 10
    ]


def ganzhi_pair_facts(left: str, right: str) -> dict[str, Any]:
    for value in (left, right):
        try:
            sexagenary_index_for(value)
        except KeyError as exc:
            raise ValueError("干支配对需要有效六十甲子") from exc
    pair = next(
        (
            (p, e)
            for p, e in STEM_PAIRS
            if frozenset(p) == frozenset((left[0], right[0]))
        ),
        None,
    )
    stem_harmony = pair is not None
    branch_harmony = SIX_HARMONY_BRANCHES[left[1]] == right[1]
    left_xun, right_xun = xun_head_for_ganzhi(left), xun_head_for_ganzhi(right)
    return {
        "left_ganzhi": left,
        "right_ganzhi": right,
        "stem_harmony_matched": stem_harmony,
        "canonical_stem_pair": list(pair[0]) if pair else None,
        "candidate_element": pair[1] if pair else None,
        "branch_harmony_matched": branch_harmony,
        "both_harmonies_matched": stem_harmony and branch_harmony,
        "left_ganzhi_xun_head": left_xun,
        "right_ganzhi_xun_head": right_xun,
        "same_ganzhi_xun": left_xun == right_xun,
        "transformation_confirmed": None,
        "du_he": None,
    }


def build_stem_relations(
    *, day_stem: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if [r.get("label") for r in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("干元类需要按次序排列的四位")
    nodes = {}
    for row in rows[1:3]:
        branch = row["content"]
        expected = wuzidun_stem(day_stem, branch)
        if row.get("dun_stem") != expected:
            raise ValueError("神将当日遁干与日干、固有支不一致")
        nodes[row["label"]] = dict(
            position=row["label"],
            name=row["shenjiang"],
            branch=branch,
            branch_element=row["element"],
            dun_stem=expected,
            dun_ganzhi=expected + branch,
            dun_element=stem_element_text(expected),
            branch_xun_kong=row["xun_kong"],
            branch_si_da_kong=row["si_da_kong"],
        )
    intrinsic = rows[1].get("intrinsic_ganzhi")
    if (
        not isinstance(intrinsic, str)
        or len(intrinsic) != 2
        or intrinsic[1] != nodes["贵神"]["branch"]
    ):
        raise ValueError("贵神固有干支与本支不一致")
    evaluations = []
    relation = "两干比和"
    motion_analogue: str | None = None
    for rule_id, name, source, target, phase_relation, analogue in RELATIONS:
        a, b = nodes[source]["dun_element"], nodes[target]["dun_element"]
        matched = (ELEMENT_GENERATES if phase_relation == "生" else ELEMENT_CONTROLS)[
            a
        ] == b
        evaluations.append(
            dict(
                id=rule_id,
                relation=name,
                source_position=source,
                target_position=target,
                phase_relation=phase_relation,
                matched=matched,
                original_pdf_pages=[63],
            )
        )
        if matched:
            relation, motion_analogue = name, analogue
    return {
        "ruleset_id": "jinkou_jingben_dun_stem_relations_v1",
        "source_title": "校正京本金口诀·五子元遁、五合、干元类及五行气化（所选遁干事实）",
        "source_url": SCAN_URL,
        "source_sha256": SCAN_SHA256,
        "original_pdf_pages": [41, 44, 54, 55, 63, 64, 65, 74],
        "day_stem": day_stem,
        "dun_cycle_policy": "single_cycle_zi_to_hai",
        "god": nodes["贵神"],
        "general": nodes["将神"],
        "guishen_intrinsic_ganzhi": intrinsic,
        "relation": relation,
        "motion_analogue": motion_analogue,
        "rule_evaluations": evaluations,
        "pair_facts": ganzhi_pair_facts(
            nodes["贵神"]["dun_ganzhi"], nodes["将神"]["dun_ganzhi"]
        ),
        "fenzu_heju_status": "not_adjudicated",
        "named_wuhe_position_status": "not_adjudicated",
        "complete_classical_conformance": False,
        "scope": "按占日日干在子至亥一轮起神将当日遁干；干元类比较遁干五行，不用贵神固有干或支位五行替代。贼动同类、财动同类是本节干类，不改四位五动命中。天干五合、地支六合、干支俱合及两遁干支自身同旬分别列事实；自身旬不改占日旬首和空亡，天干合不要求地支同时六合。所列本支旬空、四大空亡沿用原四位本支和本五行，不换成遁干五行。配对只给候选五行，合化、妒合、分局合局及五种位置合的完整裁定未完成，不给实际应期或现实成败保证。",
    }
