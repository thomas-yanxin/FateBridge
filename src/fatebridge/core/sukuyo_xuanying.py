"""A standalone Xuanying passage, distinct from its later day-boundary gloss."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_rizang import (
    named_rizang_reference,
    rizang_comparison_lines,
)
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_xuanying_source_chain.json"


def standalone_reference(commentarial: dict[str, Any]) -> dict[str, Any]:
    """Bind a named edition to the actual later quotation without choosing a clock."""
    loaded = load_source(SOURCE)
    data = loaded.data
    cited = next(row for row in commentarial["sources"] if row["id"] == "T2216")
    if data["T2216_context"]["publisher_capture_sha256"] != cited["capture_sha256"]:
        raise ValueError("玄应条目与本次注疏来源不一致，须重新核验")
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "applied_to_calendar_or_clock": False,
        "named_rizang_comparison": named_rizang_reference(data),
    }


def source_chain_lines(reference: dict[str, Any]) -> list[str]:
    literal = reference["selected_literal"]
    return [
        f"直接音义条目：已取得{reference['source_edition']}"
        "具名C1163《一切经音义》卷八沸星条"
        f"（{reference['selected_locator']}），原录为「{literal}」。"
        "本条并列二月八日鬼宿合时与所引日藏分经二月九日曙夜分属九日，"
        "未写寅、卯钟界；不能把后疏转引的寅卯解释补进本条。"
        "这里只说明所选条目，不断言全书没有相关文字。",
        "来源层次：T2216先直接引音义，再转引《章實紳鏡鈔》的寅时、卯时与昼分解释；"
        "C1163作佛星，T2216此处作弗星，分别保留。"
        "C1163卷八与T2216行内九之十七左的卷页差别尚未核定，"
        "未将新取得的具名版本认定为其实际引用本；章實等原本仍未取得。"
        "中研院公开的弘教書院排印之高麗藏本影印，PDF第92页、所加庄本页号383，"
        "所选片段可见八日、九日及夜分属九日；"
        "该影印、C1163中华版和T2216实际引用本尚未认证为同一实物，也未证明谱系独立。"
        "夜字前一字的原图唯一字形未接纳，不依电子本补字。"
        "这些选段和影印核看没有认证古代平明、现代钟点、桧尾半日或闰小月补配优先，"
        "未移动历日或主宿，也不增加独立历史观察或现实样本。",
        *rizang_comparison_lines(reference["named_rizang_comparison"]),
    ]
