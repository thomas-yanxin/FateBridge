"""Jingben trine membership, waiting symbols and separately visible conditions.

Three branches are an observed structure, not proof of completed transformation.
The excerpt's disruptive-branch lists need context: 辰 and 巳 are also members
of their own water/metal trines, so presence alone must never break those trines.
"""

from __future__ import annotations

from typing import Any

from ...utils.data import HEAVENLY_STEMS
from .common import ELEMENT_CONTROLS, ELEMENT_GENERATES, SIX_CLASH_BRANCHES
from .jinkou_relations import SOURCE_SHA256, SOURCE_URL

TRINES = (
    ("寅午戌", "炎上课", "炎上破体课", "火", "亥子"),
    ("亥卯未", "曲直课", "曲直破体课", "木", "申酉"),
    ("申子辰", "润下课", "润下破体课", "水", "辰戌"),
    ("巳酉丑", "从革课", "从革破体课", "金", "巳午"),
)
STEM_ELEMENTS = dict(zip(HEAVENLY_STEMS, "木木火火土土金金水水"))


def human_relation(human: str, trine: str) -> str:
    if human == trine:
        return "同局五行"
    if ELEMENT_CONTROLS[trine] == human:
        return "局克人元"
    if ELEMENT_GENERATES[human] == trine:
        return "人元生局"
    if ELEMENT_CONTROLS[human] == trine:
        return "人元克局"
    return "局生人元"


def trine_evidence(
    rows: list[dict[str, Any]], *, day_branch: str, month_branch: str
) -> dict[str, Any]:
    if [r["label"] for r in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("三合条件需要按次序排列的四位")
    if rows[0]["content"] not in STEM_ELEMENTS or any(
        b not in SIX_CLASH_BRANCHES
        for b in (day_branch, month_branch, *(r["content"] for r in rows[1:]))
    ):
        raise ValueError("三合条件需要有效干支")
    if any(r.get("dun_stem") not in (None, *HEAVENLY_STEMS) for r in rows[1:3]):
        raise ValueError("神将遁干无效")
    human = STEM_ELEMENTS[rows[0]["content"]]
    observed = {r["content"] for r in rows[1:]}
    trines = []
    for branches, name, partial_name, element, disruptors in TRINES:
        present = [b for b in branches if b in observed]
        missing = [b for b in branches if b not in observed]
        status = (
            "branches_complete_requires_adjudication"
            if len(present) == 3
            else (
                "missing_one_requires_adjudication"
                if len(present) == 2
                else "insufficient_members"
            )
        )
        members = [
            {
                "position": r["label"],
                "branch": r["content"],
                "day_clash": r["content"] == SIX_CLASH_BRANCHES[day_branch],
                "month_break": r["content"] == SIX_CLASH_BRANCHES[month_branch],
                "xun_kong": r["xun_kong"],
                "si_da_kong": r["si_da_kong"],
            }
            for r in rows[1:]
            if r["content"] in branches
        ]
        controlling_stems = [
            {
                "position": r["label"],
                "stem": r["dun_stem"],
                "element": STEM_ELEMENTS[r["dun_stem"]],
                "trine_element": element,
                "explicit_fire_clause": element == "火",
            }
            for r in rows[1:3]
            if len(present) >= 2
            and r.get("dun_stem")
            and ELEMENT_CONTROLS[STEM_ELEMENTS[r["dun_stem"]]] == element
        ]
        trines.append(
            {
                "name": name,
                "partial_name": partial_name,
                "element": element,
                "branches": list(branches),
                "present_branches": present,
                "missing_branches": missing,
                "structural_status": status,
                "human_stem_relation": (
                    human_relation(human, element) if len(present) >= 2 else None
                ),
                "member_conditions": members,
                "controlling_dun_stems": controlling_stems,
                "source_listed_disruptors": list(disruptors),
                "disruptor_application": "context_unadjudicated_not_presence_rule",
                "du_he": None,
                "transformation_confirmed": None,
                "waiting_branch": missing[0] if len(present) == 2 else None,
                "calendar_candidates": None,
                "original_pdf_pages": [56, 57, 58],
                "basis": (
                    f"神、将、地分实见{'、'.join(present) or '无本组三合支'}；"
                    f"{'支齐' if not missing else '缺' + '、'.join(missing)}；"
                    + (
                        f"按候选结构{element}五行，人元{rows[0]['content']}{human}与局为{human_relation(human, element)}，尚未裁定合化。"
                        if len(present) >= 2
                        else "成员不足两支，未比较人元与局或神将遁干克局。"
                    )
                ),
            }
        )
    return {
        "ruleset_id": "jinkou_jingben_trine_conditions_v1",
        "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "source_section": "卷上·三合全身 / 虚一待用",
        "day_branch": day_branch,
        "month_branch": month_branch,
        "trines": trines,
        "textual_variants": [
            {
                "original_pdf_page": 58,
                "scan_reading": "申子辰虚一位为润下破体课",
                "transcription_reading": "申子辰虚一位为炎上破体课",
            }
        ],
        "scope": (
            "仅四位三支的齐缺、人元五行关系、成员日冲月破空亡及神将遁干克局事实；"
            "神将带壬癸水克火局为原文明例，其余克局仅列五行关系。"
            "成员不足两支时不推导人元与局关系或克局条件。"
            "所忌支的适用条件、妒合及完整合化未裁定；辰、巳既是成员又见于忌表，不因自身出现自动破局。"
            "虚一支只是待用符号，未选择实际年月日时，不作必然应期或成败判断。"
        ),
    }
