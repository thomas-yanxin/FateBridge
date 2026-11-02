"""A named later commentary is evidence, not a new Hinoo calendar policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_seibunkan_1900_v1.json"
FACTS_SHA256 = "2d925518e5f58a206b2b480e3cd2e2a92c5319d86b26a3d2fff48b6677966fae"


def seibunkan_reference(
    meanings: dict[str, Any], taisho: dict[str, Any]
) -> dict[str, Any]:
    """Keep the selected later print and the actual comparison source bound."""
    loaded = load_source(SOURCE)
    data = loaded.data
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != FACTS_SHA256:
        raise ValueError("近代注释对照的原字、归属或未定范围改变，须重新核验")
    if any(
        meanings.get(key) != value
        for key, value in data["calendar_meanings_binding"].items()
    ) or any(taisho.get(key) != value for key, value in data["taisho_binding"].items()):
        raise ValueError("近代注释对照与本次桧尾原文及句义绑定不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def seibunkan_lines(reference: dict[str, Any]) -> list[str]:
    leap = reference["leap_month"]
    example = reference["natal_example"]
    return [
        "具名近代注释对照：NDL760661／760662《二十八宿詳解：真言秘密》，"
        f"目录登记{reference['catalogue_publication_date']}；"
        f"凡例二作“{leap['literal_working_excerpt']}”，"
        "说明该书闰月复用本月朔宿。这是该版凡例，不是桧尾交叠次序的新原文。",
        "该书上卷34至37页月表含牛宿，下卷21页注者仅推测某图可能后插，"
        "该图与上卷月表同一性未定；23至24页本命例为二月十七日，"
        f"{example['lunar_day']}加{example['added_number']}得{example['printed_sum']}、"
        f"除{example['cycle_length']}余{example['remainder']}，"
        f"印字工作读{example['literal_result_mansion']}宿，"
        f"现代标识{example['modern_mansion_label_for_comparison']}另列，不按数值改印字。",
        "下卷65页保留平明与明日晓时交接、昼夜各八时；"
        "汉文酉后成／戌及另读西戌、日文西成／西戌按角色和部位分列，"
        "均未接纳为规范原字。所选27帧未确立现代钟点、桧尾半日或闰小月先后，"
        "未更换本次日期、宿名或候选；目录日期不冒充已读刊记，"
        "角色复用不等于独立人工校勘。",
    ]
