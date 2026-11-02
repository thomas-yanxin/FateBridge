"""Selected publisher print-image readings, distinct from electronic witnesses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_printed_pages.json"
CANONICAL_SHA256 = "5431bddb2dd1a7c933b5106e29efba4128d1a64c88d09b8a8622aefbd55c77db"


def printed_page_reference(parent_sha256: str) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != CANONICAL_SHA256:
        raise ValueError("所选印页来源已改变，须重新核验")
    data = loaded.data
    if parent_sha256 != data["parent_witness_data_sha256"]:
        raise ValueError("所选印页与电子校勘层版本不一致")
    return {**data, "source_bundle_sha256": loaded.sha256}


def printed_page_lines(reference: dict[str, Any]) -> list[str]:
    whole_tiles = sum(
        r["all_selected_level_tiles"] for r in reference["printed_frames"]
    )
    observations = {r["id"]: r for r in reference["root_selected_observations"]}
    a12 = observations["T1644_a12"]["root_selected_image_literal"]
    return [
        "所选SAT大正图页现另作直接对照：立世T32第196页a12原分辨率局部，"
        f"根代理选读{a12}，所报【大】矣与该图相合；CBETA采纳正文牟及SAT电子主文牟仍分别保留。"
        "b16图上月减一牟休多的月后未补又，后文第三月又属于另一位置；"
        "b23图上牟林多、b28十一月九日、c20至瞿耶尼，与电子采纳休、后疏明示校改十二、采纳至西分层。"
        "这不是证明电子平台整体错误，也不由一张印页推定所有印次、六处差别均为印错或原抄本身份。",
        "宿曜T21第399页所选图段仍见平明、日夜各八时、明日晓时次后曜当直；"
        "最高层局部根代理复读为则八时而周，复核代理首读分时的分歧与后续勘误分别保留；"
        "并未因此求出古代地方钟时、太阳高度、唯一逐时曜序或桧尾半日。",
        f"本次取得三张指定印页的完整第12层图像，共{whole_tiles}块图砖，"
        "另取a12最高第13层局部8块，再取分时及半日两处最高层局部42块，"
        f"共{reference['raw_tiles_total']}块实际读回；"
        "只按DZI网格裁去声明重叠并复制像素，未增强、重采样或生成缺失文字。"
        "整页并非全部最高分辨率，来源是出版方所呈大正图页，不是新得独立抄本。"
        "a12局部原记录页高5772、DZI实为5771，差1像素；局部不触页边，像素未变，原记录及更正均保留。"
        "根代理已知候选，选读不是严格盲测、独立人工字形验收或全书校勘。"
        "电子差异对象中的旧未核定标志描述v70取得状态，现有图页选读另列，未静默改旧记录；历日、主宿和候选均未因此改动。",
    ]


def hinoo_printed_page_lines() -> list[str]:
    """Deliver the T2465 print comparison only in the Hinoo profile branch."""
    from fatebridge.core.sukuyo_witness_identity import (
        CANONICAL_SHA256 as WITNESS_SHA256,
    )

    printed_page_reference(WITNESS_SHA256)
    return [
        "桧尾T78第30页所选印字仍为十二月初一虚、十五星、三十星；京都和善通寺室、T1299算法三十日室均未改写。半字后己／已的辨字分歧另列，原先根代理选读半已上／半已下保留为首读，不当作独立人工定字。十六字校记的イ及甲标记保留，没有据图裁定补配先后、甲本身份或现代12:00。末句根代理另选读眞宿、复核首读直宿及后续真字类勘误分层记录，尚不据此立新规则。"
    ]
