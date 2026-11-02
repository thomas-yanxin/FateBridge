"""Distinguish daily assignment from inferred use for a natal mansion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_hinoo_natal_scope_v1.json"
FACTS_SHA256 = "7b8a3d822d21b0eff3b31822297f43f40700fdbcd4e7257bc3c468c281c2e62a"


def natal_scope_reference(
    meanings: dict[str, Any], taisho: dict[str, Any]
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != FACTS_SHA256:
        raise ValueError("桧尾本命适用推论、学术归属或未定范围改变，须重新核验")
    if meanings.get("source_bundle_sha256") != data["meaning_reference_bundle_sha256"]:
        raise ValueError("桧尾本命适用推论与当前句义参考不一致，须重新核验")
    if any(taisho.get(key) != value for key, value in data["primary_binding"].items()):
        raise ValueError("桧尾本命适用推论与大正原文或校记不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def natal_scope_lines(reference: dict[str, Any]) -> list[str]:
    scholar = reference["scholarship"]
    application = reference["application"]
    return [
        f"本命适用另须分层：{scholar['author']} {scholar['year']}年莱顿大学论文"
        f"第{scholar['printed_page']}页把分半日用于出生者本命宿表述为推测，"
        "并说明没有明文说明；所选T2465条文讲缺日分宿，没有直接明说按出生前／后半判本命。"
        "这项学术推论不是新增古代见证，不抹去日分宿条文本身可解释的含义。",
        f"当前{application['calendar_profile']}研究档案在已声明条件下沿用该本命适用推论。"
        "显式日序半日下的computed说明档案内计算确定，不证明古代本命用法已获原典明文认证；"
        "已定宿与条件候选继续交付，未改变宿值或补造现代钟点、半日端点、古代日界与闰小月先后。",
    ]
