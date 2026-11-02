"""Explain the bound Hinoo clauses without choosing clocks or rule precedence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_hinoo_clause_meanings_v1.json"
)
FACTS_SHA256 = "99e89ec15ce6c8be94700f9c453d0754d987b8115a43093b1acb2b1f938e26b2"


def calendar_clause_meanings(taisho: dict[str, Any]) -> dict[str, Any]:
    """Reject source drift rather than inheriting meanings from another text."""
    loaded = load_source(SOURCE)
    data = loaded.data
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != FACTS_SHA256:
        raise ValueError("桧尾句义、出处或解释范围改变，须重新核验")
    if any(taisho.get(key) != value for key, value in data["primary_binding"].items()):
        raise ValueError("桧尾句义与本次原文或校记不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def calendar_clause_meaning_lines(reference: dict[str, Any]) -> list[str]:
    relative = reference["relative_month"]
    example = reference["short_month_example"]
    scholar = reference["textual_halves"]["scholarly_interpretation"]
    return [
        f"闰月条{relative['locator']}的其正月指{relative['meaning']}；"
        "原文用正十二月与傍十二月对举，不能读成所有闰月都复用农历一月。",
        f"小月条{example['locator']}的假令正月则具体举农历一月小、缺三十日的例子，"
        "接到二月初一分宿；这是两处正月的不同语境。缺日分宿仍有安置，"
        "初一当日宿也保留，未把初一全天改成前月缺日宿。",
        f"本档案把半已上／半已下称为前半／后半，采用Kotyk {scholar['year']}"
        f"第{scholar['printed_page']}页对此段的翻译解释："
        f"前半为{scholar['first_half']}，后半为{scholar['second_half']}。"
        "这项学术解释与原文字面、校记分别保留，不是现代12:00或平明钟时换算；"
        "此处是历日分宿的名义分配，不能当作观测月球在该宿的停留时长。",
        "闰月复用与小月分宿是不同条文；段落先后不构成已经确定的程序优先级。"
        "两种现代重建不冒称原典明定的两套算法，原有条件候选与已定部分分别交付，"
        "本次句义说明没有改变数值计算、古代日界或半日政策。",
    ]
