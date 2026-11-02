"""Attributed local context readings, separate from a normalized edition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_hinoo_context_v1.json"
FACTS_SHA256 = "882116d682f3daaddc8965db162772fc80db1c205f4ef90a6b583349c8a160cd"


def context_reference(
    previous: dict[str, Any], taisho: dict[str, Any]
) -> dict[str, Any]:
    """Attach later evidence only to the actual earlier and SAT references."""
    loaded = load_source(SOURCE)
    data = loaded.data
    canonical = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != FACTS_SHA256:
        raise ValueError("桧尾相邻语境、读录阶段或未定范围改变，须重新核验")
    if (
        previous.get("id") != data["previous_completion_id"]
        or previous.get("source_bundle_sha256")
        != data["previous_completion_bundle_sha256"]
    ):
        raise ValueError("桧尾相邻语境与此前原尺寸记录不一致，须重新核验")
    if any(taisho.get(key) != value for key, value in data["taisho_binding"].items()):
        raise ValueError("桧尾相邻语境与所用大正原文或校记不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def context_lines(reference: dict[str, Any]) -> list[str]:
    rows = {row["id"]: row for row in reference["qualified_comparisons"]}
    antecedent = rows["antecedent_month_34_column6"]
    ending = rows["intercalary_month_34_column8"]
    pair = rows["regular_and_intercalary_35_column1"]
    day30 = rows["day30_mansion_34_column8"]
    heading = rows["calendar_heading_34_column5"]
    upper = rows["half_upper_35_column4"]
    lower = rows["half_lower_35_column5"]
    return [
        f"桧尾相邻语境另据{reference['evidence_snapshot_as_of_utc']}冻结记录，"
        "非本次实时联网或重新读图：真福寺033至036原图的历法段及前后主题分别定位；"
        "033、036为新增相邻页，034、035复用此前原图，不加入原17张分母。"
        "相邻仪轨页没有逐字全录，局部未见交叠排序句不能外推全书没有。",
        f"真福寺035右首栏两角色工作读{pair['generator_first_working_reading']}；"
        f"主角色首读{pair['root_first_working_reading']}，受反馈后工作读改为"
        f"{pair['root_after_feedback_working_reading']}。原首录保持，反馈后更正不是独立首读；"
        f"SAT绑定文字{pair['SAT_bound_text']}另存，不归一化，也未建立普通第十三月。",
        f"两处034月数字须按部位区分：第6栏末其月数字，生成角色读"
        f"{antecedent['generator_first_working_reading']}、复核角色读"
        f"{antecedent['reviewer_first_working_reading']}；左末栏另处生成角色读"
        f"{ending['generator_first_working_reading']}、复核角色读"
        f"{ending['reviewer_first_working_reading']}，主角色由"
        f"{ending['root_first_working_reading']}改为受反馈后的"
        f"{ending['root_after_feedback_working_reading']}。未将分歧合并成所有月数字同读。",
        f"卅日宿字两角色工作读{day30['generator_first_working_reading']}，"
        f"SAT字面{day30['SAT_bound_text']}分别保存；算法相合不证明字形。题头生成角色读"
        f"{heading['generator_first_working_reading']}、复核角色读"
        f"{heading['reviewer_first_working_reading']}；旁写小字完整读法及归属未定。"
        "没有把工作读法接纳为规范原字、完整定本、作者或甲本身份。",
        "半后两处疑字分别保留：035第4栏生成角色候选"
        f"{'／'.join(upper['generator_candidates'])}、复核角色候选"
        f"{'／'.join(upper['reviewer_candidates'])}；第5栏生成角色候选"
        f"{'／'.join(lower['generator_candidates'])}、复核角色候选"
        f"{'／'.join(lower['reviewer_candidates'])}。没有先认定两处同字，未改成日或现代钟时。",
        "本局部仍可解释闰月沿用相应通常月、缺卅日分宿仍有安置、初一当日宿保留；"
        "这两例没有同时明说闰月且小月，叙述顺序不确立交叠执行优先。"
        "首次窄裁区切掉目标栏左部的不足与较宽裁区后续复核分别保留，"
        "像素对应成功不等于选区完整。共享角色历史、提供方、反馈及文件系统的限制继续存在；"
        "本次接入没有确定古代日界、半日端点、补配先后或改变历法计算。",
    ]
