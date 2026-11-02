"""Identify a quoted work without certifying its physical exemplar or clock."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "data/sukuyo_t2217_quotation_comparison_v1.json"
)
DATA_SHA256 = "9e94e06e04a0db00104ab03ba1f6ec89ce0e8a744ed6b85cc68d36154b42d5c6"
FACTS_SHA256 = "fcfb7a344b4634847c24ab47ec7ec9a51eb5fc2f629dbd7e636294347428a858"
KANBUN_SOURCE = SOURCE.with_name("sukuyo_kyoto_kanbun_selected_v1.json")
KANBUN_DATA_SHA256 = "c002d5dae988b756b2ac4ffc2d6ef7056a7266f882cc0c79259d695390ffe5c5"
KANBUN_FACTS_SHA256 = "2658e352a97cbf8628e5ddb8eac68ad07a55ec93ab29407eab29bc4f09a58138"


def validate_quotation(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("引书身份、卷次、文字层或未定条件改变，须重新核验")


def quotation_reference() -> dict[str, Any]:
    from fatebridge.core.sukuyo_zhidu_calendar import zhidu_reference

    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("引书比较资料字节改变，须重新冻结来源")
    data = loaded.data
    validate_quotation(data)
    return {
        "source_data": data,
        "source_bundle_sha256": loaded.sha256,
        "before_code_reference_sha256": DATA_SHA256,
        "kanbun_witness_round": 88,
        "kanbun_printed_witness": kanbun_reference(),
        "upstream_context_round": 89,
        "upstream_calendar_context": zhidu_reference(),
    }


def quotation_lines(reference: dict[str, Any]) -> list[str]:
    validate_quotation(reference["source_data"])
    lines = [
        "第88轮引用比较：目标整段、邻近多组连续长引和《指心鈔》明称‘演密抄’的内部证据，"
        "强力支持‘鈔第二’指向覺苑《大日經義釋演密鈔》X0439卷二。"
        "这是作品层的强识别，尚未找到形式缩称定义，具体引本和完整传引谱系未认证，"
        "不能把每个鈔字都并为此书；它也不是T2216《演奧鈔》。"
        "目标处《指心鈔》自身是卷四，引用另一书的卷二；X0439的0548b07再用日名段，"
        "已属卷三，不是卷二第二处。",
        "《演密鈔》卷二电子段落作‘從旦至旦’，与所选大正正文夕、甲本异读报告且分别保留。"
        "当前XML含AI电子标点‘三、十’及‘十一月翻。此言’，不把它当原印句读或新数词，"
        "也不静默订正。台大PDF为CBETA2023.Q4的电子排版，非旧印本影像，"
        "不能与XML计两份独立古代见证；所选电子段未交付相交校注不证明所有古本无异文。",
        "國圖D18n8863电子文件的作者元数据记‘唐 釋一行撰’，"
        "《指心鈔》SAT署记另载頼瑜；原疏作者与钞书署记者分别保留，不以元数据覆盖署记。"
        "其电子正文亦作夕，本轮未据此声称已见所述國圖原刊字形。"
        "后续另引‘智證大師鈔’，与前一‘鈔第二’分开，私释仍有各／合及三十时的疑问；"
        "未据作品识别统一时制、现代秒、T1299平明、桧尾半日或闰小月补配先后。",
    ]
    if reference.get("kanbun_witness_round") == 88:
        lines += kanbun_lines(reference["kanbun_printed_witness"])
    if reference.get("upstream_context_round") == 89:
        from fatebridge.core.sukuyo_zhidu_calendar import zhidu_lines

        lines += zhidu_lines(reference["upstream_calendar_context"])
    return lines


def validate_kanbun(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != KANBUN_FACTS_SHA256:
        raise ValueError("京都印页读法、首读分歧、实物身份或未定条件改变，须重新核验")


def kanbun_reference() -> dict[str, Any]:
    loaded = load_source(KANBUN_SOURCE)
    if loaded.sha256 != KANBUN_DATA_SHA256:
        raise ValueError("京都选页资料身份改变，须重新冻结")
    data = loaded.data
    validate_kanbun(data)
    return {
        "source_data": data,
        "source_bundle_sha256": loaded.sha256,
        "before_code_reference_sha256": KANBUN_DATA_SHA256,
    }


def kanbun_lines(reference: dict[str, Any]) -> list[str]:
    validate_kanbun(reference["source_data"])
    return [
        "京都大学RB00018489本轮实际核看具名刊本的目标印页，目录记寛文元年刊、頼瑜著；"
        "已另核卷首，目标为卷四、右叶十九，左页续二十的工作读法。"
        "‘至’后的目标字各首读均作夕；‘從’后的旦／且及部分晝／畫形仍有分歧，"
        "首读分别保留，完整逐字稿未统一，不按人数或电子文字定字。"
        "黑色大字、小字与朱笔分别记录，朱笔年代和未定红字不补读。"
        "所用服务原生图为6016×4016，原生区域读字与缩小概览分开；"
        "目录年款未据刊记独立核实，仍未证明京都本与大正原底本实物同一，也未见大正甲本目标原图。"
        "这一目标字的一致不抹去旦、且等其他层次或首读分歧，不改变平明、半日和闰小月先后。",
    ]
