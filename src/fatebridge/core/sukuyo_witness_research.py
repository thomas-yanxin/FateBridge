"""Qualified capture records and attributed readings, without a policy override."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "data/sukuyo_selected_witness_research_v1.json"
)
FACTS_SHA256 = "2e5a4a4981222a2237ff0cf9c76a8e67f8c870b708709bd8360529e5c07771c7"
NATIVE_SOURCE = SOURCE.with_name("sukuyo_native_witness_followup_v1.json")
NATIVE_FACTS_SHA256 = "135de374ffaad5459e6bfdc1ca46f5ebc8a1e74afdfdfeb4fe5eb802c65a9549"
COMPLETION_SOURCE = SOURCE.with_name("sukuyo_native_witness_completion_v1.json")
COMPLETION_FACTS_SHA256 = (
    "7a1bc1485e11d21619f1afa7a02c09013fb36f3ea8eda533a2df9514b18c9619"
)


def validate_bundle(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("所选影像研究事实、来源或接受状态改变，须重新核验")


def research_reference(taisho: dict[str, Any]) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    validate_bundle(data)
    if any(taisho.get(key) != value for key, value in data["taisho_binding"].items()):
        raise ValueError("所选影像研究参考与本次大正原文不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def native_followup_reference(previous: dict[str, Any]) -> dict[str, Any]:
    """Add a later capture record without rewriting the original first."""
    loaded = load_source(NATIVE_SOURCE)
    data = loaded.data
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != NATIVE_FACTS_SHA256:
        raise ValueError("原尺寸后续研究事实或接受状态改变，须重新核验")
    if (
        previous.get("source_bundle_sha256") != data["previous_research_source_sha256"]
        or previous.get("id") != data["previous_research_id"]
    ):
        raise ValueError("原尺寸后续研究与此前冻结参考不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def native_followup_lines(reference: dict[str, Any]) -> list[str]:
    capture = reference["capture_summary"]
    count = reference["naoj_count"]
    date = reference["capture_snapshot_as_of_utc"][:10]
    return [
        f"另据{date}后续冻结采集记录（非本次实时联网）：同一原队列取得"
        f"{capture['union_acquired']}／{capture['required']}张原尺寸图，"
        f"仍缺{len(capture['missing'])}张；此前0／17首采及本轮网络失败、"
        "未尝试项均保留，原尺寸门与全本校勘未通过。",
        "真福寺034、035已取得6112×4672原图，所选卅日宿字三角色工作读室；"
        "半后字及其他词列首读仍有分歧，主角色卅日／闕日首读更正另存。"
        "没有接受完整转录或据此改大正星字，也未确定现代日界、"
        "半日钟点及闰月复用与小月补配重叠的执行先后。",
        "天文台新版077与旧078本次分别工作读"
        f"{count['selected_native_working_reading']}，刻资工作读"
        f"{count['selected_working_cost']}；此为题记印文，未重新统计全文。"
        f"此前父角色首读{count['historical_root_first']}、"
        f"角色异读及后来错改{count['historical_root_correction']}的历史均保留，"
        "本次更正此前更正；不改NAGO075，不据两路图像认证同件实物或独立谱系。",
        "本次整图显示有缩小，关键字另读原生裁区；sips裁片与另一解码器的RGB值"
        "存在差异，未认证逐值相同。两代理复用提供方、历史和共享文件系统，"
        "不是严格盲审或人工全校；未改变历法政策、原180题验收或真实样本0的状态。",
    ]


def native_completion_reference(previous: dict[str, Any]) -> dict[str, Any]:
    """Bind the later completion to the unchanged historical followup."""
    loaded = load_source(COMPLETION_SOURCE)
    data = loaded.data
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != COMPLETION_FACTS_SHA256:
        raise ValueError("原尺寸完成记录事实或接受状态改变，须重新核验")
    if (
        previous.get("source_bundle_sha256") != data["previous_followup_source_sha256"]
        or previous.get("id") != data["previous_followup_id"]
    ):
        raise ValueError("原尺寸完成记录与此前后续参考不一致，须重新核验")
    return {**data, "source_bundle_sha256": loaded.sha256}


def native_completion_lines(reference: dict[str, Any]) -> list[str]:
    capture = reference["capture_summary"]
    colophon = reference["NAGO075_selected_colophon"]
    return [
        f"再据{reference['capture_snapshot_as_of_utc']}冻结复验记录（非实时联网）："
        "此前0／17与10／17为各次历史首采状态，记录保持原样；"
        f"同一原队列现已取得并逐件读验{capture['union_acquired']}／"
        f"{capture['required']}张原尺寸图，仍缺0张，原尺寸采集门通过。"
        "另取得天文台069、070两张计时页，未加入原17张分母；全本校勘门仍未通过。",
        "天文台070与名古屋068原尺寸所选段落工作读平明即是所直之曜、"
        "明日曉時即次後曜當直，支持平明与次日晓时的曜交接定性解释；"
        "正文昼八时、夜八时分别记录，未换成现代八小时或十六小时。"
        "西／酉仍未定字，主角色入夜、入时误读与受反馈后的更正分别保留。",
        "所选曜交接段未确定现代钟点、太阳高度、端点包含方式或完整日内曜序，"
        "也未证明所有宿日及阴历日期一律同界；桧尾半日钟点与闰月复用、"
        "小月补配重叠先后仍未定，现行计算未改用平明日界。",
        f"名古屋075本次另读原图，所选题记工作读{colophon['volume_working_reading']}、"
        f"{colophon['printed_character_count_working_reading']}、"
        f"{colophon['cost_working_reading']}、{colophon['inscription_working_reading']}；"
        "此前预览异读不倒改，印文字数未作全文重计，"
        "庚子年、顺治十八年与延宝九年题记分开，不给全部纸叶统一定年。",
        "关键裁区在同一Pillow解码路径下逐像素核对，不扩为所有解码器或显示一致；"
        "两模型角色共享提供方、历史和文件系统，未获严格盲审或独立人工全校。"
        "原文萬不失一属于效力宣称，不是实测准确率；原180题未改判，真实样本仍为0。",
    ]


def research_lines(reference: dict[str, Any]) -> list[str]:
    capture = reference["capture_summary"]
    shinpukuji = reference["shinpukuji"]
    nagoya = reference["nagoya_composite"]
    legacy = reference["naoj_legacy"]
    count = legacy["legacy78_character_count_readings"]
    date = reference["capture_snapshot_as_of_utc"][:10]
    return [
        f"所选影像研究按{date}冻结采集记录交付，非本次实时联网状态："
        f"国书预览{capture['NIJL_previews_saved']}／{capture['NIJL_previews_planned']}张，"
        "天文台新版069仍缺；所选原尺寸取得"
        f"{capture['original_resolution_acquired']}／{capture['original_resolution_requirements']}，"
        "未减少原尺寸需求或认证全本校勘。",
        f"真福寺大須文庫{shinpukuji['call_number']}《{shinpukuji['title']}》"
        "034左页至035右页已经定位闰月复用与小月缺三十日、次月初一分宿段。"
        "卅日宿字为生成角色室候选、复核角色预览读室，最终接受字仍未定；"
        "半…上／半…下与半晝上者、其□下者分别保留，□候选已／巳。"
        "这些是所选片段，未据此改大正星字或认证底本／甲本。",
        "名古屋馆方明确著录上下卷为不同版本配合本："
        f"上卷{nagoya['upper_lines_as_holder_statement']}行、享保序刊及无量寿院藏版，"
        f"下卷{nagoya['lower_lines_as_holder_statement']}行、据顺治十八年刊本的延宝和刻。"
        "古写本年代与弘法传写推测是馆方据序转述，不能据目录1681给全部纸叶定年。"
        "NAGO075下卷／上下卷及刻资三分／二分首读分别保留，最终未定；"
        "馆方转录印開識、柴水山不倒改此前像素读录。",
        f"天文台旧目录第{legacy['holder_catalogue_row']}项入口已保存"
        f"{len(legacy['selected_images'])}张2500×1872图；"
        f"{len(legacy['visually_supported_content_pairs'])}组所选内容对应不等于全部80页固定页差、"
        "同件实物或独立谱系。NAOJ-00315摄影编号不能接为旧目录315《談天》；"
        "旧070未补为新版缺069，2500像素未算作5616像素原图。",
        f"天文台旧078字数父角色首读{count['parent_first']}保留，"
        f"逐列查看后的工作读法为{count['working_selected_image_reading']}，"
        "此更正只限本图，不改NAGO075。旧071曉／曜及西／酉读录仍分别保留；"
        "平明、昼夜各八时尚未确定现代钟点、太阳高度或完整日内曜序，"
        "未把桧尾半日当民用12:00，也未裁定闰月与小月补配交叠先后。",
        "所选上卷正文随合十宿含牛、歌诀九宿分别记录，不合并进下卷27宿分类或删除牛字。"
        "本参考未应用为历法、物理月宿或他本改字政策，未获独立人工全校或严格盲读验收，"
        "不增加独立历史观察或现实预测样本。",
    ]
