"""Bind later working readings without replacing the preserved first record."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_zentsuji_later_reading_v1.json"
)
ACCEPTANCE_FLAGS = {
    "independent_human_transcription_accepted",
    "complete_manuscript_collation",
    "physical_object_date_established",
    "taisho_base_or_ko_identity_established",
    "independent_textual_lineage_established",
    "leap_short_month_priority_established",
    "modern_clock_mapping_established",
    "algorithm_override_applied",
}


def later_reading_reference(
    legacy: dict[str, Any], legacy_source_sha256: str
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    expected = data["expected_legacy"]
    if expected["source_bundle_sha256"] != legacy_source_sha256 or any(
        legacy.get(key) != value
        for key, value in expected.items()
        if key != "source_bundle_sha256"
    ):
        raise ValueError("善通寺后续校读与既有来源身份不一致，须重新核验")
    if set(data["acceptance_flags"]) != ACCEPTANCE_FLAGS or any(
        value is not False for value in data["acceptance_flags"].values()
    ):
        raise ValueError("所选工作校读不能自动提升原典或历法验收状态")
    if any(
        row["accepted_literal"] is not None
        for row in data["unresolved_calendar_readings"]
    ):
        raise ValueError("后续未决字不能未经复核提升为统一定字")
    return {**data, "source_bundle_sha256": loaded.sha256}


def later_reading_lines(reference: dict[str, Any]) -> list[str]:
    colophon = reference["native_colophon_followup"]
    lines = [
        "善通寺后续校读与既有首录分层保留，旧转录片段不是已统一定字。",
        "善通寺第33帧后续已取得原尺寸图"
        f"{colophon['image_dimensions'][0]}×{colophon['image_dimensions'][1]}，"
        f"指纹{colophon['image_sha256']}；旧预览和取得失败不回写。",
        f"题记长栏工作读{colophon['long_column_working']}；"
        f"另栏署记{colophon['separate_signature_working']}分别保留，"
        "未补写讫日数，未据版面唯一决定抄者、校者关系。",
    ]
    for row in reference["unresolved_calendar_readings"]:
        lines.append(
            f"善通寺后续未决字{row['location_zh']}：旧首录{row['legacy_selected']}，"
            f"后续工作读{row['later_working']}，当前统一定字仍未接纳。"
        )
    lines.extend(
        [
            "历法段保留12栏连续工作原串及跨栏無日；不凭通顺、算法相合或模型多数定字。",
            "第8、14帧所选時字处于结印、持诵、请召或主伴语境；遍数不是现代时段。",
            "上述均为有限模型工作读录，未获独立人工验收或全书校勘；"
            "题记自述未确定现存物年代、独立谱系、大正底本或甲本身份，"
            "也未确定古代日界、桧尾半日钟时或闰小月补配优先，未改变配宿算法。",
        ]
    )
    return lines
