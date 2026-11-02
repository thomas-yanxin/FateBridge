"""Named textual dawn criteria and conflicting quoted unit counts."""

from __future__ import annotations

import hashlib
import json
import re
from math import gcd
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_daybreak_sources.json"
DATA_SHA256 = "2c78e5f4164b59a8b4343c9398afe1d1bb1d6abab7aef284c1f3ff93ee0f8dea"
FACTS_SHA256 = "68c0635f87750b99e23d29344824db8d4d74d49c61257e693e26c4571494e308"


def validate_reference(data: dict[str, Any]) -> None:
    """An updated source requires a new review; do not inherit old controls."""
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("明相来源、引文层或未定控制改变，须重新核验")


def _quantity(text: str, pattern: str) -> int:
    match = re.search(pattern, re.sub(r"[。，]", "", text))
    if match is None:
        raise ValueError("所选时分数值没有原文支持")
    values = {"五": 5, "六": 6, "五十": 50}
    if match[1] not in values:
        raise ValueError("所选原文数词尚未核定")
    return values[match[1]]


def daybreak_reference() -> dict[str, Any]:
    from fatebridge.core.sukuyo_t2217_collation import collation_reference
    from fatebridge.core.sukuyo_upstream_dawn import upstream_reference

    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("明相及校勘资料身份变化，须重新冻结来源")
    data = loaded.data["source_data"]
    validate_reference(data)
    sources = {row["id"]: row for row in data["sources"]}
    products = {}
    for name, window in (("X0744", "time"), ("T2087", "units")):
        text = sources[name]["windows"][window]["main_literal"]
        per_part = _quantity(text, r"([五十]+)牟呼栗多為一時")
        parts = _quantity(text, r"([六]+)時合成一日一夜")
        if data["unit_controls"][name] != {
            "muhurta_per_part": per_part,
            "day_night_parts": parts,
        }:
            raise ValueError("时分控制与引用原字不一致")
        products[name] = per_part * parts
    divisor = gcd(products["X0744"], products["T2087"])
    return {
        "source_data": data,
        "selected_apparatus": loaded.data["selected_apparatus"],
        "header_attribution": loaded.data["header_attribution"],
        "source_bundle_sha256": loaded.sha256,
        "conditional_unit_products": products,
        "conditional_product_ratio": {
            "numerator": products["X0744"] // divisor,
            "denominator": products["T2087"] // divisor,
        },
        "modern_seconds_before_sunrise": None,
        "textual_criteria_are_observed_timestamps": False,
        "birth_calendar_override_applied": False,
        "upstream_collation": upstream_reference(),
        "T2217_printed_collation": collation_reference(),
    }


def daybreak_lines(reference: dict[str, Any]) -> list[str]:
    from fatebridge.core.sukuyo_t2217_collation import collation_lines
    from fatebridge.core.sukuyo_upstream_dawn import upstream_lines

    products = reference["conditional_unit_products"]
    titles = {row["id"]: row["title"] for row in reference["source_data"]["sources"]}
    headers = reference["header_attribution"]["sources"]
    attribution = "、".join(
        f"《{titles[row['source_id']]}》"
        + re.sub(r"\s+", "", "／".join(row["title_stmt_author_literals"]))
        for row in headers
    )
    body_attribution = "；".join(
        f"《{titles[row['source_id']]}》"
        + re.sub(r"\s+", "", "／".join(row["selected_body_bylines"]))
        for row in headers
    )
    return (
        [
            f"四书电子题头分别署{attribution}。所选正文署名另录为{body_attribution}。"
            "正文各处署名的字样分别保留，序文署名未移作编译者；"
            "题头时代标签不证明各条报道皆为亲历，也不是本轮纸本身份认证。"
            "阿留那条正文另列阿樓那、薩埵，Aruṇa.属外语脚注；这些词形及校注"
            "未据此校定梵语词源或同一物理瞬间。",
            "《翻譯名義集》阿留那条引《明了論》东方已赤，"
            "引通慧《指歸》此方日未出前二刻、观见掌文，"
            "并明说‘是四分明’、‘又別宗名地了時’，后者以见地色分了为说。"
            "本组取得状态是第75轮快照，当前具名上游另见下述核验。"
            "《四分律名義標釋》在地了时前署《十誦律》，"
            "而《翻譯名義集》此处只说别宗，不无标识移入另一书的具体归属；"
            "其具体引本和地色释义原段不能只凭同名书就认定已校定。"
            "《薩婆多毘尼毘婆沙》所选离衣宿段"
            "则保存黑、青、白三色而以白色为正的叙述。"
            "这些是不同文本归属的明相判据，不能只因词近就认作同一精确瞬间。"
            "前二刻未给出适用刻制或现代秒量，也没有据此确定太阳高度、T1299平明、"
            "出生换日、桧尾前后半或闰小月补配先后。",
            "《名義標釋》转引《西域記》的电子正文作‘五十牟呼栗多為一時’，"
            "《西域記》所选电子正文作‘五牟呼栗多為一時’，两处均记六时合一日夜；"
            f"条件乘算分别为{products['X0744']}与{products['T2087']}，相差十倍。"
            "前者未校成后者，也未据300改写既有昼夜算法。差异产生环节未裁定，"
            "转引不是独立的第二次计时实测；《西域記》居俗八时正文与昼四夜四夹注另层保留，"
            "《名義標釋》相应文字则在所选正文中，不混合两书层次。"
            "电子校勘还报《名義標釋》东方已赤的已【CB】／巳【卍續】，"
            "以及《西域記》合／念、昼三夜／夜三昼、於／于、一一／二；"
            "原注、改注、增注及读法装置分别记录，未据此宣称亲见各版印字或完整原典校勘。",
        ]
        + upstream_lines(reference["upstream_collation"])
        + collation_lines(reference["T2217_printed_collation"])
    )
