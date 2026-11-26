"""Printed break-pair membership, kept separate from effective break judgments."""

from __future__ import annotations

import json
from pathlib import Path

from fatebridge.utils.data import EARTHLY_BRANCHES

BREAK_WITNESSES_PATH = (
    Path(__file__).resolve().parents[2] / "data/jinkou_break_pair_witnesses.json"
)


def break_pair_witnesses() -> dict[str, object]:
    """Load break pair textual witnesses from data."""
    result = json.loads(BREAK_WITNESSES_PATH.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("破支见证资料须为对象")
    return result


# The scan also prints 寅破巳, omitted by the online transcription.
WRITTEN_PAIRS = ("申巳", "戌未", "亥寅", "寅巳", "丑辰", "午卯", "酉子")
POSITIONS = ("贵神", "将神", "地分")
CONTEXTS = (
    ("god_general", 0, 1),
    ("god_ground", 0, 2),
    ("general_ground", 1, 2),
)
RULE = "jinkou.printed_break_pairs"


def metadata() -> dict[str, object]:
    return dict(
        ruleset_id="jinkou_jingben_printed_break_pairs_v1",
        source_title="校正京本金口诀·月破休囚（所列支对事实）",
        original_pdf_page=113,
        written_pairs=[list(p) for p in WRITTEN_PAIRS],
        transcription_written_pairs=[list(p) for p in WRITTEN_PAIRS if p != "寅巳"],
        scan_extra_pairs=[["寅", "巳"]],
        extra_pair_author_intent=None,
        witness_evidence=break_pair_witnesses(),
        membership_policy="both_members_of_a_printed_pair_regardless_of_position_order",
        effect_direction=None,
        effective_break=None,
        complete_classical_conformance=False,
        scope=(
            "仅比较贵神固有支、将神本支、地分三组内部支对是否包含原文所列两支，"
            "书写次序另列，不表示已裁定相互作用、破局有效性或现实损坏。"
            "书影较网页多列寅破巳，七组原字保留；额外支对的作者原意未裁，不按通行六破删字。"
            "不将人元干换成寄宫支，不以贵神落地位置代替固有支，不增加年月日时接触；"
            "不改月建六冲的month_break、旺衰、五动或综合取用。"
        ),
    )


def pair_facts(left: str, right: str) -> dict[str, object]:
    if left not in EARTHLY_BRANCHES or right not in EARTHLY_BRANCHES:
        raise ValueError("京本破支配对须使用单个有效地支")
    written = next((p for p in WRITTEN_PAIRS if set(left + right) == set(p)), None)
    return dict(
        left_branch=left,
        right_branch=right,
        source_pair_present=written is not None,
        source_written_pair=list(written) if written else None,
        source_order=(
            ("left_then_right" if left + right == written else "right_then_left")
            if written
            else None
        ),
        effective_break=None,
        effect_direction=None,
    )


def branch_breaks(god: str, general: str, ground: str) -> dict[str, object]:
    branches = (god, general, ground)
    if any(b not in EARTHLY_BRANCHES for b in branches):
        raise ValueError("京本破支配对须使用贵神、将神、地分的实际本支")
    rows = [
        dict(
            id=identifier,
            left_position=POSITIONS[i],
            right_position=POSITIONS[j],
            **pair_facts(branches[i], branches[j]),
        )
        for identifier, i, j in CONTEXTS
    ]
    return dict(**metadata(), rows=rows)


def branch_breaks_trace(value: dict[str, object]) -> dict[str, object]:
    return dict(
        rule_id=RULE,
        source_section="卷上·月破休囚（所列七组支对，含寅巳异文）",
        result=value,
    )
