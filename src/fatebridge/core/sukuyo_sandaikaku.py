"""A later administrative quotation is not an original observed day label."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_sandaikaku766.json"
FACTS_SHA256 = "d4cdeb8fee076da9222f823e6ea95b2389aa2dce9bc722130db286c674aef67d"


def validate_bundle(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("京大三代格所选文书、被引日期及未载干支的绑定已改变")


def month_reference(year: int, month: int, leap: bool) -> dict[str, Any] | None:
    """Bind the quoted month and the later document month, without changing dates."""
    if (
        type(year) is not int
        or type(month) is not int
        or not 1 <= month <= 12
        or type(leap) is not bool
    ):
        raise ValueError("三代格文书须使用明确年月与闰月布尔键")
    if (year, month, leap) not in ((766, 2, False), (822, 3, False)):
        return None
    source = load_source(SOURCE)
    data = source.data
    validate_bundle(data)
    role = next(
        row["role"]
        for row in data["binding_months"]
        if row["month_key"] == [year, month, leap]
    )
    return {
        **data,
        "source_bundle_sha256": source.sha256,
        "selected_month_key": [year, month, leap],
        "selected_month_binding_role": role,
        "inferred_original_event_ganzhi": None,
        "inferred_historical_month_start": None,
        "inferred_absolute_civil_date": None,
        "current_calendar_rewritten": False,
        "source_image_reread_at_runtime": False,
    }


def reference_lines(result: dict[str, Any] | None) -> list[str]:
    if result is None:
        return [
            "本次月份未绑定京大三代格这组所选文书，sandaikaku_edict_reference为空；"
            "不继承766年二月旧敕或822年三月文书的引文日期、数量或未载干支作为本月结论。"
            "已有NAOJ历日、研究选行和配宿仍按实际返回交付，未绑定不等于否定其他史料。"
        ]
    role = result["selected_month_binding_role"]
    return [
        "京大菊亭文库《类聚三代格》RB00028238卷第08的实际frame320—321所选影像，"
        "传载弘仁十三年三月廿八日（822年三月二十八日）太政官符，"
        "正文引『天平神护二年二月廿日敕书』（766年二月二十日）及"
        "近江近郡五万斛贮纳松原仓的旧事。当前月份与该材料的绑定角色为"
        + (
            "被引766年二月的旧敕月份。"
            if role == "quoted_earlier_edict_month"
            else "传载822年三月的文书月份。"
        )
        + "这两个原文日期分别交付，不取代本次输入或把整月每一天说成文书二十八日。",
        "所选引文直接写被引敕书二月二十日，但没有甲午或丙午干支；"
        "该文书日期也未载干支，未据此生成事件干支、月首或实际公历日期。"
        "它是另一著作传载的较晚引文，不是已取得766年敕书或822年文书的同时代原件，"
        "与《续日本纪》的传承独立性未确立，不能据此消除甲午／校订丙午异文或选定丁亥／乙亥。",
        "文书列近江谷十一万五千斛，其中应运进十万斛、驮赁料一万五千斛；"
        "旧敕所引五万斛另列，不把不同条文的数量混成日期或单一运输额。"
        "京大抄本所选页已取得，不等于NDL1900年本目标图像已取得，"
        "也未认定就是研究表所称352页的同一版，或1897校者的『一本』。",
        "以上为主代理模型所选影像核读，非完整外交转写或独立人工校勘；"
        "实际抄写年代未因此确立，早稻田考证卷九仍未取得。"
        "没有据此确定古代统一日界、平明钟点、桧尾半日或闰小月补配先后；"
        "当前NAOJ历日、配宿与52项研究方向分歧及1项未知均保留。"
        "新增独立历史观测0，真实预测样本0，不能由引文相合认证现实预测效力。",
    ]
