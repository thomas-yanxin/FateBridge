"""Qualify locator counts without treating every TEI relation as an ID link."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_zhidu_pointer_scope_v1.json"
FACTS_SHA256 = "0a9a93d7ed71e6d3778dcf7d80eb13d4766b5f97fba826d1d54f9ac3ff637a03"
INTERPRETATION_FLAGS = {
    "all_TEI_associations_semantically_verified",
    "independent_manuscript_identity_certified",
    "ancient_day_boundary_established",
    "modern_clock_mapping_established",
    "hinoo_half_clock_established",
    "leap_short_month_priority_established",
    "calendar_or_mansion_override_applied",
    "real_prediction_efficacy_established",
}


def strict_reference_equal(actual: Any, expected: Any) -> bool:
    """Compare the JSON value and its types; bool is never a nominal integer."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            strict_reference_equal(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            strict_reference_equal(left, right) for left, right in zip(actual, expected)
        )
    return isinstance(expected, (str, int, bool, type(None))) and actual == expected


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def pointer_count_scope(
    legacy: dict[str, Any], legacy_source_sha256: str
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    if _digest(data) != FACTS_SHA256:
        raise ValueError("校记定位口径或关联诊断改变，须重新核验")
    expected = data["expected_legacy"]
    if (
        expected["raw_source_sha256"] != legacy_source_sha256
        or expected["canonical_facts_sha256"] != _digest(legacy)
        or expected["source_data_id"] != legacy["id"]
    ):
        raise ValueError("校记定位口径与原有来源身份不一致")
    policy = data["counting_policy"]
    if (
        policy["locating_attributes"] != ["target", "from", "to"]
        or policy["record_tags"] != ["note", "app"]
        or policy["resolution_basis"] != "exact xml:id in the complete frozen XML"
        or policy["zero_unresolved_applies_only_to_declared_locating_scope"] is not True
        or set(data["interpretation_flags"]) != INTERPRETATION_FLAGS
        or any(value is not False for value in data["interpretation_flags"].values())
    ):
        raise ValueError("定位指针核对不能提升为全部关联或古代历法验收")
    if set(data["sources"]) != {"T1509", "T2122"}:
        raise ValueError("校记定位口径必须保留两部已登记来源")
    for work, source in data["sources"].items():
        original = legacy["sources"][work]
        if (
            source["source_sha256"] != original["sha256"]
            or source["source_bytes"] != original["bytes"]
            or not strict_reference_equal(
                source["legacy_counts_snapshot"], original["apparatus_counts"]
            )
        ):
            raise ValueError("校记定位范围不能替换原计数或源文")
        integer_keys = [
            "all_back_note_app_records",
            "records_with_own_local_locating_tokens",
            "records_without_own_local_locating_tokens",
            "own_local_locating_tokens",
            "own_unresolved_exact_xml_id",
            "own_tokens_outside_body_ids",
        ]
        if any(
            type(source[key]) is not int or source[key] < 0 for key in integer_keys
        ) or any(
            type(value) is not int or value < 0
            for value in source["own_tokens_by_attribute"].values()
        ):
            raise ValueError("校记记录数和token数必须是整数，不能以布尔值代替")
        counts = original["apparatus_counts"]
        if (
            source["all_back_note_app_records"]
            != source["records_with_own_local_locating_tokens"]
            + source["records_without_own_local_locating_tokens"]
            or source["all_back_note_app_records"]
            != counts["all_back_note_app_records"]
            or source["own_local_locating_tokens"] != counts["all_pointer_tokens"]
            or source["own_local_locating_tokens"]
            != sum(source["own_tokens_by_attribute"].values())
            or source["own_unresolved_exact_xml_id"] != counts["unresolved"]
            or set(source["own_tokens_by_attribute"]) != {"target", "from", "to"}
        ):
            raise ValueError("校记定位计数口径与原始记录不一致")
    reuse = data["sources"]["T1509"]["selected_reuse"]
    if (
        reuse["own_range_matches_exact_xml_ids"] is not True
        or reuse["corresp_matches_exact_xml_id"] is not False
        or reuse["corresp"] != "#0409025"
    ):
        raise ValueError("编号式校记复用不能冒充同名xml:id已解析")
    return {**data, "source_bundle_sha256": loaded.sha256}


def pointer_scope_lines(reference: dict[str, Any]) -> list[str]:
    left, right = (reference["sources"][work] for work in ["T1509", "T2122"])
    return [
        "校记定位口径另列：《大智度论》《法苑珠林》后置note/app各"
        f"{left['all_back_note_app_records']}、{right['all_back_note_app_records']}条，"
        "含没有自身定位属性的记录；仅自身target/from/to中的本地#定位token各"
        f"{left['own_local_locating_tokens']}、{right['own_local_locating_tokens']}个"
        "按xml:id解析为零未匹配。这个分母不含corresp等关联属性，"
        "不能读成所有TEI关联均已认证。",
        "原论0409c03复用的corresp=#0409025没有同名xml:id；"
        "两处app自身字位仍有可解析起讫，原注、改注按同编号、星号及内容关联。"
        "严格ID解析与编号式关联分别保留，未将后者判作坏链接，"
        "也未据此改月名、月长、古代钟界或补配优先。",
    ]
