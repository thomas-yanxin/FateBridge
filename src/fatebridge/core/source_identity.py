"""Exact documentary corrections, independent of all strength calculations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PARENT_SHA256 = "65c99d86d517f7e7daeeeb8b89d7afbf2f730dbcb0ff44ae02007b19f5feb6fe"
PLAN_SHA256 = "a1ea5243b412682fa09f9eb0e76193310acfa1fe5befeb76062a4e13161be65e"
PDF_SHA256 = "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620"
PUBLISHER_IMAGE_SHA256 = (
    "431ca7b415d6e72c4f1492b87df112f26e6f26c6a229a810baf37387bd53359c"
)
PUBLISHER_NOTE = "出版者标注已按同一书影书名页更正，旧登记另存，命式与强弱标签保持。"
NAME_NOTE = "原页所印姓名错配另已更正，旧编号保留；未认定历史人物身份。"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def build_identity_index(
    parent: dict[str, Any], plan: dict[str, Any], generator_sha256: str
) -> dict[str, Any]:
    """Apply all pinned corrections, rejecting any change in old claims."""
    if (
        plan["parent_index_sha256"] != PARENT_SHA256
        or plan["source_pdf_sha256"] != PDF_SHA256
        or len(plan["patches"]) != 58
        or plan["publisher_correction_count"] != 58
        or plan["name_correction_count"] != 2
        or len(parent["records"]) != 367
    ):
        raise ValueError("来源身份修订范围或父索引不一致")
    patches = {p["reference_id"]: p for p in plan["patches"]}
    if len(patches) != 58:
        raise ValueError("来源身份修订编号必须完整且唯一")
    result = deepcopy(parent)
    changed, names = set(), 0
    for index, before in enumerate(parent["records"]):
        patch = patches.get(before["reference_id"])
        if patch is None:
            continue
        if canonical_digest(before) != canonical_digest(patch["before"]):
            raise ValueError("来源身份修订原记录不一致")
        after = patch["after"]
        revision = after["source_identity_revision"]
        expected_reference = deepcopy(before["source_reference"])
        edition = expected_reference["edition"]
        if (
            expected_reference["whole_pdf_sha256"] != PDF_SHA256
            or "世界书局发行" not in edition
        ):
            raise ValueError("出版者更正必须对应同一已核书影")
        expected_reference["edition"] = edition.replace(
            "世界书局发行", "上海世界图书馆发行"
        )
        expected = deepcopy(before)
        expected["source_reference"] = expected_reference
        expected_revision = {
            "revision_id": "ziping_witness_identity_v1",
            "original_record_sha256": canonical_digest(before),
            "original_edition": edition,
            "publisher_as_printed": "上海世界圖書館發行",
            "source_pdf_page": 1,
            "source_image_sha256": PUBLISHER_IMAGE_SHA256,
            "source_strength_label_assigned_or_regraded": False,
            "independent_expert_review": "not_completed",
            "new_independent_validation_credit": 0,
        }
        if "name_correction" in revision:
            correction = revision["name_correction"]
            name = correction["name_as_printed"]
            valid_names = {
                "ZP-PROSPECTIVE-17-MAO-HEAVY": (
                    ["壬寅", "戊申", "壬辰", "壬寅"],
                    "茅状元",
                    "馬參政",
                ),
                "ZP-PROSPECTIVE-18-MA-LIGHT": (
                    ["己巳", "癸酉", "癸未", "庚申"],
                    "马参政",
                    "茅狀元",
                ),
            }
            valid = valid_names.get(before["case_id"])
            if (
                valid is None
                or (before["pillars"], correction["legacy_registered_name"], name)
                != valid
            ):
                raise ValueError("姓名更正必须对应已核原页的字面四柱")
            if (
                correction["source_pdf_page"] != 73
                or correction["legacy_case_identifier_retained"] is not True
                or correction["historical_person_identity_asserted"] is not False
            ):
                raise ValueError("姓名更正不得改编号或宣称历史身份已证实")
            expected_revision["name_correction"] = correction
            expected["name_as_printed"] = name
            names += 1
        expected["source_identity_revision"] = expected_revision
        if canonical_digest(after) != canonical_digest(expected):
            raise ValueError("来源身份修订不得变更命式、原典强弱、未知或其他字段")
        result["records"][index] = deepcopy(after)
        changed.add(before["reference_id"])
    if changed != patches.keys() or names != 2:
        raise ValueError("来源身份修订遗漏条目或姓名更正")
    result.update(
        parent_index_sha256=PARENT_SHA256,
        generator_sha256=generator_sha256,
        data_revision="source_annotations_v8_witness_identity",
        source_identity_plan_sha256=PLAN_SHA256,
        source_identity_revision_count=58,
        source_identity_name_revision_count=2,
        scope="保留全部367条登记、原编号、命式、强弱标签及未知；仅按同一书影更正58条出版者标注和2处姓名错配。旧索引另存，不新增计算、原典符合、独立审阅或现实预测信用。",
    )
    return result


def validate_identity_index(data: dict[str, Any], directory: Path) -> None:
    parent_raw = (directory / "bazi-source-annotations-v7.json").read_bytes()
    plan_raw = (directory / "bazi-source-witness-identity-v1.json").read_bytes()
    if (
        hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA256
        or hashlib.sha256(plan_raw).hexdigest() != PLAN_SHA256
    ):
        raise ValueError("来源身份修订父索引或固定方案散列不一致")
    expected = build_identity_index(
        json.loads(parent_raw), json.loads(plan_raw), data["generator_sha256"]
    )
    if canonical_digest(data) != canonical_digest(expected):
        raise ValueError("来源身份修订索引与固定方案不一致")
