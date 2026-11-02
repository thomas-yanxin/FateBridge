"""Qualify historical Kyoto selections with attributed image-layer readings."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_kyoto_layered_reading_v1.json"
)
FACTS_SHA256 = "fc61718cf810601bcbb1cd6785c03a8646ed49dd70b61b0348cb51f639ae5d8f"
ACCEPTANCE_FLAGS = {
    "independent_human_transcription_accepted",
    "complete_manuscript_collation",
    "unmodified_black_text_whole_span_certified",
    "taisho_base_or_ko_identity_established",
    "independent_textual_lineage_established",
    "leap_short_month_priority_established",
    "modern_clock_mapping_established",
    "algorithm_override_applied",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def qualify_kyoto_reference(
    primary: dict[str, Any], span: dict[str, Any], legacy_source_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retain old selections and explicitly qualify the active span claim.

    This adds source evidence, never a mansion or calendar policy. Both original
    objects and the actual source bytes must match the reviewed bindings.
    """
    loaded = load_source(SOURCE)
    data = loaded.data
    if _digest(data) != FACTS_SHA256:
        raise ValueError("京都字层事实或读录阶段改变，须重新核验")
    expected = data["expected_legacy"]
    if (
        expected["source_bundle_sha256"] != legacy_source_sha256
        or expected["selected_primary_canonical_sha256"] != _digest(primary)
        or expected["apparatus_span_canonical_sha256"] != _digest(span)
        or any(
            primary.get(key) != expected[key]
            for key in (
                "id",
                "image_sha256",
                "manifest_sha256",
                "canvas_index_one_based",
            )
        )
    ):
        raise ValueError("京都分层跟进与既有来源或校记身份不一致，须重新核验")
    if set(data["acceptance_flags"]) != ACCEPTANCE_FLAGS or any(
        value is not False for value in data["acceptance_flags"].values()
    ):
        raise ValueError("工作字层读录不能自动提升原典或历法验收状态")
    overwrite = data["middle_black_overwrite_and_side_writing"]
    if (
        any(row["accepted_literal"] is not None for row in data["unresolved_readings"])
        or any(
            row["black_accepted_literal"] is not None
            for row in data["corrected_number_positions"]
        )
        or data["span_scope_qualification"]["black_accepted_literal"] is not None
        or data["quotation_context"]["prefixed_glyph"]["accepted_literal"] is not None
        or data["quotation_context"]["following_condition_working_readings"][
            "accepted_literal"
        ]
        is not None
        or data["quotation_context"]["red_bracket_function_accepted"] is not None
        or overwrite["black_undertext_accepted_literal"] is not None
        or overwrite["insertion_order_accepted"] is not None
        or overwrite["annotator_identity_accepted"] is not None
        or any(
            row["accepted_literal"] is not None
            for row in overwrite["small_black_side_characters"]
        )
    ):
        raise ValueError("京都未决字层不能未经复核提升为统一定字")
    originals = {row["id"]: row for row in primary["observations"]}
    mapped = data["mapped_legacy_observations"]
    if (
        len(originals) != len(primary["observations"])
        or len(mapped) != len(originals)
        or {row["legacy_observation_id"] for row in mapped} != set(originals)
        or any(
            row["legacy_normalized_transcription"]
            != originals[row["legacy_observation_id"]]["normalized_transcription"]
            for row in mapped
        )
    ):
        raise ValueError("京都字位跟进不能省略或改写既有片段")
    controls = [row for row in primary["observations"] if "month" in row]
    followup_controls = data["clear_date_example_positions"]
    if len(controls) != len(followup_controls) or {
        (row["month"], row["day"], row["mansion"]) for row in controls
    } != {
        (row["lunar_month"], row["lunar_day"], row["legacy_mansion"])
        for row in followup_controls
    }:
        raise ValueError("京都改数字位不能代换三个日期例题")
    width, height = primary["image_dimensions"]
    if data["image_dimensions"] != [width, height]:
        raise ValueError("京都字位坐标与原图尺寸不一致")

    def box(row: dict[str, Any]) -> list[int]:
        value = row["region_xyxy"]
        if (
            len(value) != 4
            or any(type(part) is not int for part in value)
            or not 0 <= value[0] < value[2] <= width
            or not 0 <= value[1] < value[3] <= height
        ):
            raise ValueError("京都字位坐标超出原图或没有面积")
        return [int(part) for part in value]

    box(overwrite)
    if overwrite["image_sha256"] != primary["image_sha256"]:
        raise ValueError("京都中部覆写字位与原图身份不一致")
    for record in overwrite["source_working_records"]:
        box(record)
        if not any(
            record["task"] == source["task"]
            and record["raw_first_sha256"] == source["raw_first_sha256"]
            for source in data["source_readings"]
        ):
            raise ValueError("京都中部覆写工作读未绑定既有首读")
    for corrected in data["corrected_number_positions"]:
        left = box(corrected)
        for control in followup_controls:
            right = box(control)
            if max(left[0], right[0]) < min(left[2], right[2]) and max(
                left[1], right[1]
            ) < min(left[3], right[3]):
                raise ValueError("京都叠改数字的字位不能混同日期例题")
    qualification = data["span_scope_qualification"]
    if (
        qualification["legacy_scope"] != span["scope"]
        or qualification["normalized_candidate_span"]
        != span["normalized_candidate_span"]
        or qualification["candidate_character_count"] != span["character_count"]
    ):
        raise ValueError("京都分层说明不能改写原十六字候选")
    followup = {**data, "source_bundle_sha256": loaded.sha256}
    return (
        {**deepcopy(primary), "later_layered_reading": followup},
        {
            **deepcopy(span),
            "scope": qualification["current_scope"],
            "legacy_scope_before_layer_followup": span["scope"],
            "current_scope_qualification": {
                "followup_id": data["id"],
                "followup_source_bundle_sha256": loaded.sha256,
                "evidence_status": data["evidence_status"],
            },
        },
    )


def layered_reading_lines(reference: dict[str, Any]) -> list[str]:
    image = reference["expected_legacy"]
    lines = [
        f"京都后期字层跟进仍据同一第{image['canvas_index_one_based']}帧原图，"
        f"指纹{image['image_sha256']}，原尺寸"
        f"{reference['image_dimensions'][0]}×{reference['image_dimensions'][1]}；"
        "以下为各记录时点的模型工作读，不冒称本次请求重新看图或独立人工验收。",
        "十二月初一、十五、三十日三个例题与后段被改数字是不同字位；"
        "例题相合只比较既有选录值和宿主算法，不代表全文校勘通过。",
    ]
    for row in reference["corrected_number_positions"]:
        lines.append(
            f"京都{row['id']}位于{row['local_context']}，原图矩形"
            f"{row['region_xyxy']}：黑底候选{'／'.join(row['black_candidates'])}，"
            f"旁朱工作读{row['red_working_reading']}；未接纳底字，"
            "不把朱笔读法反填成未改黑正文，也不外推到三个例题。"
        )
    lines.append(reference["span_scope_qualification"]["current_scope"])
    overwrite = reference["middle_black_overwrite_and_side_writing"]
    lines.append(
        f"京都中部浓黑覆盖及小黑旁字位于原图矩形{overwrite['region_xyxy']}，"
        "与半后覆黑是不同字位：上旁字工作候选雖／雜，下旁字工作读失；"
        "较重知、较细黑字与朱可分别保留来源层，不接纳覆盖底字、"
        "旁字插入范围或先后，不由字色和粗细认证书手、注者或年代。"
    )
    for row in reference["unresolved_readings"]:
        lines.append(
            f"京都后期未决字{row['location_zh']}：候选"
            f"{'／'.join(row['candidates'])}，统一定字未接纳；旧选录及各时点首读分别保留。"
        )
    context = reference["quotation_context"]
    lines.extend(
        [
            f"京都右页旁小字工作读{context['side_note']['working_reading']}，"
            f"双小行工作读{context['inline_note']['working_reading']}；"
            "大小字和朱线分别交付，不合成T1299逐字正文。",
            "宿曜经句前接字勘仅为工作候选；后续条件句的時与一時读录仍有差别。"
            "具体引本、引用起讫、旁记者、朱线功能及全部改写时序未定。",
            "本跟进没有确定古代日界、现代半日或闰小月优先，"
            "不增加独立古本、历史观察或真实预测样本，未改变配宿算法。",
        ]
    )
    return lines
