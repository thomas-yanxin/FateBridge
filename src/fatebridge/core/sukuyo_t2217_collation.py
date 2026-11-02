"""A printed variant report is distinct from seeing its manuscript witness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_t2217_daytext_collation_v1.json"
)
DATA_SHA256 = "5d3db326f61767d2c07fd7fc56194e6654ad0aa368fab6a82dddaa99dacc20a2"
FACTS_SHA256 = "ab5c9fc357baa508779af61d4be8999427da0400e33b1328eeb4b295c319aed3"


def validate_collation(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("T2217印字、见证身份或未定控制改变，须重新校核")


def collation_reference() -> dict[str, Any]:
    from fatebridge.core.sukuyo_quotation_comparison import quotation_reference

    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("T2217印页来源身份改变，须重新冻结")
    data = loaded.data
    validate_collation(data)
    return {
        "source_data": data,
        "source_bundle_sha256": loaded.sha256,
        "before_code_reference_sha256": DATA_SHA256,
        "previous_electronic_evidence": {
            "acquisition_round": 85,
            "artifact_name": "T2217-SAT.html",
            "bytes": 469435,
            "sha256": "5343cf8db268357a4bd4a446035e1fbb2203bc3b5f96735377d6ec9ca04fbe84",
            "new_in_round_87": "selected_printed_page_pixel_reading",
        },
        "layout_notes": {
            "乃至": "smaller_inline_characters",
            "⑥": "body_apparatus_anchor",
        },
        "source_data_snapshot_round": 87,
        "subsequent_research_round": 88,
        "subsequent_quotation_comparison": quotation_reference(),
    }


def witness_reference(work_id: str, siglum: str) -> dict[str, Any]:
    """Resolve this work's key only; identical sigla elsewhere are unrelated."""
    data = collation_reference()["source_data"]
    if work_id != data["work"]["id"]:
        raise KeyError((work_id, siglum))
    witness: dict[str, Any] = data["witness_key"]["witnesses"][siglum]
    return witness


def collation_lines(reference: dict[str, Any]) -> list[str]:
    from fatebridge.core.sukuyo_quotation_comparison import quotation_lines

    validate_collation(reference["source_data"])
    lines = [
        "《大日經疏指心鈔》T2217所选大正印页正文作‘從旦至夕’，"
        "底注报告‘夕＝且〔甲〕’；〔甲〕是圈甲的转写。"
        "此处称引链为‘鈔第二云。智論云’，中间‘鈔第二’的作品身份未定，"
        "不合并成直接亲见《智論》原本。起首页校注把本书原本记作寛文元年刊本，"
        "甲本记作室町时代写高野山宝龟院藏本；这一甲号仅用于T2217。"
        "当前亲见的是大正排印正文及编者异读、书目报告，未见两底本目标原件，"
        "甲本馆藏号、现藏和实物同一性尚未核定。"
        "电子夕／且此前已有，本次新增所选印页像素核读；"
        "不把夕、且和他书的旦统一校改，也不将同一数字体系的正文、校注算作独立见证票数。"
        "本段昼夜三十时及季节配数仍未确定现代换日钟点、T1299平明、桧尾半日"
        "或闰小月补配先后。"
    ]
    if reference.get("subsequent_research_round") == 88:
        lines[0] = "第87轮所选印页快照：" + lines[0]
        lines += quotation_lines(reference["subsequent_quotation_comparison"])
    return lines
