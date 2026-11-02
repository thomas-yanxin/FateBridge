"""Three literal ordered transmission clauses from 探原, PDF114–115."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES

PATTERNS = (
    ("zhuolun", "斫轮", "卯戌巳"),
    ("zhuyin", "铸印", "巳戌卯"),
    ("xuangai", "轩盖", "午卯子"),
)
SCOPE = (
    "只按探原课体纲要三条明文比较初、中、末传顺序；同支集合、倒序及相同初传不能代替完整传序。"
    "本层不更改九宗门取传，不导入课名后的官职、吉凶或现实结果判辞，不认证全书课体或其他版本。"
)


def ordered_transmission_patterns(branches: list[str]) -> dict[str, Any]:
    if (
        not isinstance(branches, list)
        or len(branches) != 3
        or any(
            not isinstance(b, str) or len(b) != 1 or b not in EARTHLY_BRANCHES
            for b in branches
        )
    ):
        raise ValueError("传序课体需要按初中末排列的三个有效地支")
    evaluations = [
        dict(
            id=key,
            name=name,
            required_branches=list(order),
            matched=branches == list(order),
        )
        for key, name, order in PATTERNS
    ]
    return dict(
        ruleset_id="tanyuan_ordered_transmission_patterns_v1",
        source_title="大六壬探原·卷下集说篇·课体纲要",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[114, 115],
        branches=list(branches),
        evaluations=evaluations,
        matched_ids=[r["id"] for r in evaluations if r["matched"]],
        complete_classical_conformance=False,
        scope=SCOPE,
    )


def ordered_patterns_trace(evidence: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="liuren.ordered_transmission_patterns",
        source_url=evidence["source_url"],
        source_section=evidence["source_title"],
        result=evidence,
    )
