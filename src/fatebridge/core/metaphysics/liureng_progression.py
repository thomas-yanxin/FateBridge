"""探原连茹／间断支序及支神本空假设下的条件释读。"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from .common import SEXAGENARY_INDEX, kongwang_for_ganzhi

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
SCOPE = (
    "依探原PDF110–111识别三传连茹、间断及原文进退条件。旬空只按三传支神本空列事实，"
    "不以坐空或天将天空替换；条件释读明确假设支神本空适用。太岁、月建、月将、日干寄宫、"
    "年命及救制等仍须合看，综合有效空亡和实际进退未裁；不改九宗门三传，不据此断现实成败或应期。"
)


def transmission_progression(day_ganzhi: str, branches: list[str]) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("三传进退需要有效日干支")
    if (
        not isinstance(branches, list)
        or len(branches) != 3
        or any(
            not isinstance(b, str) or len(b) != 1 or b not in BRANCHES for b in branches
        )
    ):
        raise ValueError("三传进退需要按初中末排列的三个地支")
    indices = [BRANCHES.index(b) for b in branches]
    steps = [(b - a) % 12 for a, b in zip(indices, indices[1:])]
    step = steps[0] if steps[0] == steps[1] else None
    kind = "连茹" if step in (1, 11) else "间断" if step in (2, 10) else None
    direction = ("进" if step in (1, 2) else "退") if kind else None
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    flags = [b in empty for b in branches]
    reading = None
    conditional = direction
    if kind == "连茹":
        if flags[0]:
            reading, conditional = "初空进退受阻", None
        elif flags[2]:
            reading = "末空以退论" if direction == "进" else "末空以进言"
            conditional = "退" if direction == "进" else "进"
        else:
            reading = "按支序进读" if direction == "进" else "按支序退读"
    elif kind == "间断":
        if any(flags):
            reading, conditional = "见空不拘原进退说", None
        else:
            reading = "前进多阻" if direction == "进" else "后退有妨"
    return dict(
        ruleset_id="tanyuan_transmission_progression_v1",
        source_title="袁树珊《大六壬探原》卷下集说篇·课体纲要·三传连茹",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[110, 111],
        day_ganzhi=day_ganzhi,
        branches=list(branches),
        steps=steps,
        kind=kind,
        structure_matched=kind is not None,
        sequence_direction=direction,
        empty_branches=list(empty),
        branch_xun_kong=flags,
        raw_branch_empty_conditional_reading=reading,
        raw_branch_empty_conditional_direction=conditional,
        empty_assumption="仅三传支神本空，不代表综合有效空亡已裁定",
        effective_direction=None,
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope=SCOPE,
    )


def progression_trace(evidence: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="liuren.transmission_progression",
        source_url=evidence["source_url"],
        source_section=evidence["source_title"],
        result={
            k: evidence[k]
            for k in [
                "kind",
                "sequence_direction",
                "branch_xun_kong",
                "raw_branch_empty_conditional_reading",
                "effective_direction",
            ]
        },
    )
