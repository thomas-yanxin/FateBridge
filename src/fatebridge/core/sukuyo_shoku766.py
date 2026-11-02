"""Selected physical witnesses, with an editorial emendation kept explicit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_shoku766_witnesses.json"
FACTS_SHA256 = "f288efce5fcd845bfbd6ce3fcbad27ba9ad04656269cd45412866cea1c664f55"
DAY_CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[n % 10] + "子丑寅卯辰巳午未申酉戌亥"[n % 12]
    for n in range(60)
)


def validate_bundle(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("天平神护二年所选底本、校改和回指证据的固定绑定已改变")


def month_witness_comparison(
    year: int, month: int, leap: bool, *, host_month_start_index: int
) -> dict[str, Any] | None:
    """Infer cyclic labels conditionally; never select a corrected calendar."""
    if (
        type(year) is not int
        or type(month) is not int
        or not 1 <= month <= 12
        or type(leap) is not bool
        or type(host_month_start_index) is not int
        or not 0 <= host_month_start_index < 60
    ):
        raise ValueError("底本月首比较须有明确月键及0至59月首干支序号")
    if (year, month, leap) != (766, 2, False):
        return None
    source = load_source(SOURCE)
    data = source.data
    validate_bundle(data)
    inferences = []
    for witness in data["witnesses"]:
        index = DAY_CYCLE.index(witness["event_day_ganzhi_literal"])
        first = (index - (data["retrospective_referred_day"] - 1)) % 60
        inferences.append(
            {
                "witness_id": witness["witness_id"],
                "event_day_ganzhi_literal": witness["event_day_ganzhi_literal"],
                "event_day_cycle_index": index,
                "conditional_month_start_index": first,
                "conditional_month_start_ganzhi": DAY_CYCLE[first],
                "matches_selected_host_month_start": first == host_month_start_index,
            }
        )
    return {
        **data,
        "source_bundle_sha256": source.sha256,
        "conditional_inferences": inferences,
        "host_month_start_index": host_month_start_index,
        "host_month_start_ganzhi": DAY_CYCLE[host_month_start_index],
        "witness_day_label_conflict": len(
            {r["event_day_cycle_index"] for r in inferences}
        )
        > 1,
        "selected_historical_month_start": None,
        "selected_absolute_civil_date": None,
        "source_image_reread_at_runtime": False,
        "all_cited_original_records_independently_collated": False,
    }


def witness_lines(result: dict[str, Any]) -> list[str]:
    first, second = result["conditional_inferences"]
    return [
        "《续日本纪》卷二十七天平神护二年二月该诏的所选影像另列校勘："
        "国会图书馆1897年《国史大系》本印页456作丙午，并注"
        "『原作甲午，据一本改』，该『一本』尚未另行识别；"
        "国文研鵜飼文库刊本叶二所见则为甲午。"
        "六月丙申条的所选影像分别作『去二月廿日』与『去二月二十日』，"
        "两处所述近江近郡五万斛入松原仓的诏令相接。"
        "二月条没有直接印出二十日；二十日来自同书六月回指，"
        "不是两次独立历史观测。",
        f"若接受同诏回指为二十日，按1897年校订丙午减十九日，"
        f"条件推得月首{first['conditional_month_start_ganzhi']}；"
        f"保留鵜飼刊本甲午则条件推得{second['conditional_month_start_ganzhi']}。"
        f"当前所选NAOJ月首{result['host_month_start_ganzhi']}仍单列。"
        "两个条件干支不是两个已认证历法候选，未裁定唯一历史月首或实际公历日期。",
        "以上是主代理模型对两部所选影像的核读，未获独立人工校勘，"
        "两部传承独立性未确立；《类聚三代格》京大抄本所选引文另列，"
        "NDL1900年本目标图像与早稻田考证卷九仍未取得。"
        "327行所引原记录未全部校勘，原固定NAOJ对照的52项研究方向分歧仍保留。"
        "此诏不能确立古代统一日界、T1299平明或桧尾半日与闰小月补配先后，"
        "未改写当前历日、主宿或现实预测效力。",
    ]
