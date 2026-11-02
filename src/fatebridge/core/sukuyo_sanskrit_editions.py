"""Keep Sanskrit editorial witnesses separate from calendar policy."""

from __future__ import annotations

import hashlib
import json
from math import prod
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_sanskrit_edition_sources.json"
)
DATA_SHA256 = "6524a6bf9864ec376279b75b327cf64907d6cc0e474bd97ed2f2f49fc4fa0087"
FACTS_SHA256 = "5f172b4b6717d62a1e3115659b3a88ac8627dd2870c8c9e15d59a797bed0c693"
REFERENCE_SHA256 = "7f98037a8906e806c4ce7c8a07c021e5968e07bcc8fccf2ce8fb68b121b4560f"

ADJUDICATION_SHA256 = "b43af934885b1f9b361b5880edcc1d31ebb5c99c7cafd606fb21540fade4e660"


def validate_edition_data(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("梵文版本、条件单位链或未定控制改变，须重新核验")


def sanskrit_edition_reference() -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("梵文来源身份改变，须重新冻结捕获与参考")
    data = loaded.data["source_data"]
    validate_edition_data(data)
    products = {}
    for edition in data["editions"]:
        values = {
            "thread_per_day_night": prod(edition["thread_chain_counts"]),
            "water_blinks_per_muhurta": prod(edition["water_chain_counts"]),
            "blink_per_nominal_year": prod(edition["blink_chain_counts"]),
        }
        if "annual_words_counts" in edition:
            words = edition["annual_words_counts"]
            values["conditional_annual_words_total"] = (
                words["crore"] * 10_000_000
                + words["hundred_thousand"] * 100_000
                + words["thousand"] * 1000
            )
        products[edition["id"]] = values
    return {
        **loaded.data,
        "source_bundle_sha256": loaded.sha256,
        "source_bundle_hash_scope": "source_data_and_capture_identities_v80",
        "before_code_reference_sha256": REFERENCE_SHA256,
        "adjudication_before_c_sha256": ADJUDICATION_SHA256,
        "conditional_products": products,
        "historical_clock_or_calendar_override_applied": False,
        "full_physical_witness_collation_completed": False,
    }


def sanskrit_edition_lines(reference: dict[str, Any]) -> list[str]:
    validate_edition_data(reference["source_data"])
    products = reference["conditional_products"]
    old = products["cowell_neil_1886"]
    later = products["mukhopadhyaya_1954_titus"]
    return [
        "梵文计时须指定版本。Cowell／Neil1886年刊本644页漏刻链依次为"
        "二、四、四十、三十一、二；TITUS所署1954年Mukhopadhyaya版电子本文"
        "I.57.3依次为二、八、十六、三十、二。"
        f"各链每muhūrta条件乘积分别为{old['water_blinks_per_muhurta']}和"
        f"{later['water_blinks_per_muhurta']}眼瞬；不能因同书同名合并，更未换算秒。",
        "1886年645页眼瞬名义年链中kalā到muhūrta为六十四；"
        "1954版电子本文I.58.1为六十，"
        f"条件年乘积各为{old['blink_per_nominal_year']}与"
        f"{later['blink_per_nominal_year']}。1954电子本年度数词在具名通常数制假设下"
        f"合为{later['conditional_annual_words_total']}，只与本版链比较；"
        "1886年度原字及编辑注、汉译年度数字仍分别保留，未据此校改T1301。",
        "1886年655页编辑说明后半若干章节未刊全文，只列章名；未刊不能当作古文无此规则。"
        "1954版电子本I.103.1写第三年有增月，未给具体置闰年月或桧尾补配先后；"
        "I.105.1另列昼十二固定、夜十二固定及六移动分，I.108.2涉及半月，不能改成日内半日。"
        "这些是各自文本语境，未解决T1299平明钟时、桧尾前后半或闰小月交叠先后。"
        "1954印页尚未亲验；TITUS罗马字／天城体是同一数字工作，I／II编号由TITUS加入，"
        "I段52、53号重复须保留出现次序；不同显示不是独立传本。",
    ]
