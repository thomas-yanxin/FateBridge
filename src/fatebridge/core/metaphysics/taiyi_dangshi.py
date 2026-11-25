"""Compare an actual Ren noble start with both Jinjing source editions.

The editions disagree. Table equality is neither a reconstructed morning/
evening boundary nor a license to replace the actual twelve-god board.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_SHA256 = "6ba03f108abd0e490079e434c2d1718ec15fbf40c2cc919c03ae255d18df94bb"


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-dangshi-nobles-v1.json"
    )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("太乙当时法贵人来源目录指纹不符")
    result: dict[str, Any] = json.loads(raw)
    return result


def noble_source_assessment(
    day_stem: str, liureng: dict[str, Any], *, taiyi_mode: str
) -> dict[str, Any]:
    """Read the same run's trace, not a recomputed or inferred noble position."""
    catalog = _catalog()
    result: dict[str, Any] = {
        "status": "not_assessed",
        "ruleset_id": catalog["id"],
        "ruleset_version": catalog["version"],
        "source_freeze_sha256": catalog["source_freeze_sha256"],
        "scope": catalog["scope"],
        "taiyi_mode": taiyi_mode,
        "applicability": (
            "hour_method_noble_start_comparison"
            if taiyi_mode == "hour"
            else "cross_time_scope_table_comparison_only"
        ),
        "source_morning_evening_boundary_adjudicated": False,
        "whole_dangshi_method_acceptance_passed": False,
        "comparisons": [],
    }
    if day_stem not in tuple("甲乙丙丁戊己庚辛壬癸"):
        return {**result, "reason": "实际日干未提供或无效，不猜贵人本位。"}
    traces = [
        (i, t.get("result"))
        for i, t in enumerate(liureng.get("rule_trace", []))
        if isinstance(t, dict) and t.get("rule_id") == "liuren.guiren_start"
    ]
    meta = liureng.get("meta") or {}
    if len(traces) != 1:
        return {**result, "reason": "缺少唯一的同盘贵人起点算路，不能借地盘位置反推。"}
    index, trace = traces[0]
    if not isinstance(trace, dict):
        return {**result, "reason": "缺少唯一的同盘贵人起点算路，不能借地盘位置反推。"}
    start, is_day = trace.get("start_branch"), trace.get("is_diurnal")
    if (
        start not in tuple("子丑寅卯辰巳午未申酉戌亥")
        or type(is_day) is not bool
        or trace.get("profile") not in ("liuren_common_v1", "tanyuan_xieji_v1")
        or trace.get("profile") != meta.get("guiren_profile")
        or type(meta.get("is_diurnal")) is not bool
        or meta["is_diurnal"] != is_day
    ):
        return {**result, "reason": "同盘贵人算路与配置／昼夜回执不完整或不一致。"}
    comparisons = []
    for table in catalog["tables"]:
        row = next(r for r in table["rows"] if r["stem"] == day_stem)
        expected = row["morning_branch" if is_day else "evening_branch"]
        comparisons.append(
            {
                "source_id": table["id"],
                "source_edition": table["edition"],
                "source_url": table["url"],
                "facsimile_page": table["page"],
                "facsimile_sha256": table["facsimile_sha256"],
                "source_branch": expected,
                "matches": start == expected,
            }
        )
    result.update(
        status="compared_noble_start_only",
        day_stem=day_stem,
        day_stem_path="subresults.liureng_gods.four_pillars.day.stem",
        is_diurnal=is_day,
        actual_profile=trace["profile"],
        actual_start_branch=start,
        actual_trace_index=index,
        actual_start_path=f"liureng.rule_trace.{index}.result.start_branch",
        actual_diurnal_path=f"liureng.rule_trace.{index}.result.is_diurnal",
        diurnal_basis=meta.get("diurnal_basis", "未提供"),
        diurnal_evidence_path="liureng.meta.diurnal_evidence",
        comparisons=comparisons,
        boundary_scope="仅在同盘已选昼／夜对应朝／暮的明示假设下对照；不认证古朝暮判界，也不以起贵本位冒充贵人地盘落支。",
    )
    return result


def noble_source_text(assessment: dict[str, Any]) -> str:
    if assessment["status"] != "compared_noble_start_only":
        return f"贵人来源未评估：{assessment['reason']}"
    lines = [
        f"六壬实际配置{assessment['actual_profile']}；日干{assessment['day_stem']}；"
        f"所选{'昼' if assessment['is_diurnal'] else '夜'}贵起于{assessment['actual_start_branch']}。",
        assessment["boundary_scope"],
    ]
    for row in assessment["comparisons"]:
        lines.append(
            f"{row['source_edition']}当时法同一朝暮读法为{row['source_branch']}："
            + ("本位相符。" if row["matches"] else "本位不同，保留实际盘，不替换。")
        )
    lines.append(assessment["scope"])
    if assessment["taiyi_mode"] != "hour":
        lines.append(
            "本次太乙非时计；这里只对照贵人表，不把跨时间层对应当作当时法验收。"
        )
    return "\n".join(lines)
