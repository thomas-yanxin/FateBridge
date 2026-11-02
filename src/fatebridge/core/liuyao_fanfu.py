"""Keep original-scan body examples, region comparisons and line actions apart."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-fanfu-v6.json")
    .read_text(encoding="utf-8")
)
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def branch_relation(original: str, changed: str) -> str:
    if original == changed:
        return "伏吟"
    if (BRANCHES.index(original) - BRANCHES.index(changed)) % 12 == 6:
        return "反吟"
    return "其他纳支关系"


def build_fanfu_evidence(
    *,
    current_code: str,
    changed_code: str,
    base_branches: list[str],
    changed_chart_branches: list[str],
) -> dict[str, Any]:
    source = PROFILE["source"]["url"]
    moving = [i + 1 for i in range(6) if current_code[i] != changed_code[i]]
    relations = [
        {
            "position": p,
            "original_branch": base_branches[p - 1],
            "changed_branch": changed_chart_branches[p - 1],
            "nazhi_relation": branch_relation(
                base_branches[p - 1], changed_chart_branches[p - 1]
            ),
        }
        for p in moving
    ]
    regions = []
    for name, start in (("inner", 0), ("outer", 3)):
        original, changed = (
            current_code[start : start + 3],
            changed_code[start : start + 3],
        )
        old, new = (
            base_branches[start : start + 3],
            changed_chart_branches[start : start + 3],
        )
        comparisons = [branch_relation(a, b) for a, b in zip(old, new)]
        nazhi = (
            "未动"
            if original == changed
            else comparisons[0] if len(set(comparisons)) == 1 else "其他纳支关系"
        )
        regions.append(
            {
                "region": name,
                "base_trigram_code": original,
                "changed_trigram_code": changed,
                "trigram_changed": original != changed,
                "base_branches": old,
                "changed_chart_branches": new,
                "nazhi_relation": nazhi,
                "moving_positions": [p for p in moving if start < p <= start + 3],
                "static_comparison_positions": [
                    p for p in range(start + 1, start + 4) if p not in moving
                ],
                "source_url": source + ("#page=91" if nazhi == "伏吟" else "#page=89"),
                "scope": "三爻纳支是本变卦盘结构比较；静爻位置的变卦盘纳支不是静爻的变支，不构成生克作用边。",
            }
        )
    explicit = next(
        (
            deepcopy(e)
            for e in PROFILE["explicit_hexagram_examples"]
            if (e["base_code"], e["changed_code"]) == (current_code, changed_code)
        ),
        None,
    )
    if explicit:
        explicit["source_url"] = source + f"#page={explicit['pdf_page']}"
        explicit["basis"] = "指定底本明列的卦体例；不由纳支相冲推得，也不外推完整卦体表"
    return {
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": source + "#page=88",
        "source_sha256": PROFILE["source"]["sha256"],
        "regions": regions,
        "moving_line_relations": relations,
        "explicit_body_example": explicit,
        "body_classification": (
            "source_explicit_example"
            if explicit
            else ("no_change" if not moving else "outside_explicit_example_table")
        ),
        "efficacy": "requires_focus_strength_and_back_control",
        "textual_issues": deepcopy(PROFILE["textual_issues"]),
        "scope": "分别列卦体明例、内外卦纳支结构与实际动爻反伏；静卦不因支相同而算伏吟。指定章未给完整卦体表，未列不能读成已排除反伏；须用神旺衰与回头冲克，不据格局断现实成败。",
    }
