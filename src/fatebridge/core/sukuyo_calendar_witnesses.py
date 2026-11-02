"""Keep adopted electronic text and reported apparatus witnesses distinct."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_printed_pages import (
    printed_page_lines,
    printed_page_reference,
)
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_witness_identity import CANONICAL_SHA256

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_calendar_witnesses.json"


def calendar_witness_reference(
    parent: dict[str, Any], parent_sha256: str
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != CANONICAL_SHA256:
        raise ValueError("历日校勘层来源已改变，须重新核验")
    data = loaded.data
    if parent_sha256 != data["parent_fortnight_source_bundle_sha256"]:
        raise ValueError("历日校勘层与黑白分来源版本不一致")
    paragraphs = {r["paragraph_id"]: r for r in parent["selected_paragraphs"]}
    for row in data["all_five_selected_paragraphs"]:
        original = paragraphs.get(row["paragraph_id"])
        if (
            original is None
            or original["source_file"] != row["source_file"]
            or hashlib.sha256(original["main_literal"].encode()).hexdigest()
            != row["body_main_sha256"]
            or original["publisher_note_layers"] != row["inline_note_layers_unchanged"]
            or parent["actual_sources"][row["source_file"]]["sha256"]
            != data["actual_sources"][row["source_file"]]["sha256"]
        ):
            raise ValueError("历日校勘层与所选正文、行内注或实际源字节不一致")
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "legacy_acquisition_status_scope": "T1644_0196a12_digital_difference内未核定标志为v70取得状态；本次所选印页观测另列，未改写旧电子记录或冒称独立人工验收。",
        "printed_page_reference": printed_page_reference(loaded.sha256),
    }


def calendar_witness_lines(reference: dict[str, Any]) -> list[str]:
    counts = reference["counts"]
    changes = "；".join(
        f"{r['source_file'].removesuffix('.xml')} {r['from_line']}正文"
        f"{r['adopted_layer_literal']}／所报【大】{r['reported_orig_literal']}"
        for r in reference["all_six_body_vs_reported_orig_changes"]
    )
    return [
        f"历日校勘层：所选五段共有{counts['standoff_apparatus_entries']}条后置校勘记录，"
        f"其中{counts['inline_note_apparatus_entries']}条锚在行内注层，"
        f"{counts['corresp_repeat_entries']}条带corresp复现关联；全部分别保存，"
        "这些条数不是独立抄本、历史观察或真实样本数。"
        "此前所选main_literal是CBETA采纳的电子正文，不能一律称未经校改的大正正文。",
        f"六处电子正文与该XML所报【大】不同：{changes}。"
        "【大】读法是该文件校勘表的记录，其他【甲】【乙】等标识也限于各自文件；"
        "这些标签本身不是各本影像的取得证明；另列SAT所选图页，仍不能与桧尾甲本混同，也未重建整部未改写印本。",
        "法宝0617段的所报甲乙异文还包括八月十六／八月八长增句、"
        "七日若以此方九月八日等段的删除，以及月／日、月尽／昼、六／七、雨／寒；"
        "既有七月十六与八月十六、白八落八月八与九月八的说明限于本次所选正文。"
        "完整校勘记录另列，不按与当前算法相合、季节对称或多数来选唯一历制。",
        "新取SAT T1644电子文本0196b23作牟林多，0196b28作十一月九日；"
        "0196a12实际作牟，与CBETA电子正文相同，却不同于该XML所报【大】矣。"
        "这处数字版本差别照留，不能说SAT逐项认证六处所报【大】读法；"
        "二者仍是同名大正版的数字记录，不是新得独立抄本或独立人工纸本读字验收。"
        "十一所在点未列校记，也不证明全部历史版本一致；后疏十二及明示校改继续分层。"
        "本补充未取得高丽藏新字节，不改日期、古代日界、桧尾半日、闰小月先后或任何候选。",
        "现实前瞻须在结局发生前重新冻结并绑定本版来源、模型和解释；"
        "旧版预测和旧版结局不能直接复用于新版认证。原端点、窗口、基线、样本、覆盖、"
        "弃权、失访及置信门槛不变；本组真实样本仍为0，电子校勘和工程检查未建立现实预测效力。",
        *printed_page_lines(reference["printed_page_reference"]),
    ]
