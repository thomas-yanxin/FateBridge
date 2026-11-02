"""Compare a named Rizang edition without identifying a quoted exemplar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_fortnights import (
    fortnight_calendar_lines,
    fortnight_calendar_reference,
)
from fatebridge.core.sukuyo_month_names import month_name_lines, month_name_reference
from fatebridge.core.sukuyo_seasons import seasonal_reference, seasonal_reference_lines
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_rizang_comparison.json"


def named_rizang_reference(xuanying: dict[str, Any]) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    if data["compared_xuanying_capture_sha256"] != xuanying["capture_sha256"]:
        raise ValueError("日藏对照与玄应捕获版本不一致，须重新核验")
    rows = data["literal_slots"]
    keys = {(r["textual_month"], r["fortnight"], r["day"]) for r in rows}
    expected = {
        (month, half, day)
        for month in range(1, 13)
        if month != 8
        for half in ("black", "white")
        for day in range(1, 16)
    }
    if len(rows) != 330 or keys != expected:
        raise ValueError("日藏具名字面表槽不完整或重复，不能沿用对照")
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "month_name_reference": month_name_reference(data),
        "seasonal_time_reference": seasonal_reference(data),
        "fortnight_calendar_reference": fortnight_calendar_reference(data),
    }


def literal_cell(reference: dict[str, Any], month: int, half: str, day: int) -> str:
    """Read a textual table cell, never derive a date or a missing cell."""
    rows = [
        r
        for r in reference["literal_slots"]
        if (r["textual_month"], r["fortnight"], r["day"]) == (month, half, day)
    ]
    if len(rows) != 1:
        raise ValueError("该具名日藏表槽未唯一列出；不能从相邻月或宿序补值")
    return str(rows[0]["mansion_literal"])


def rizang_comparison_lines(reference: dict[str, Any]) -> list[str]:
    first9 = literal_cell(reference, 1, "white", 9)
    second7, second8, second9 = (
        literal_cell(reference, 2, "white", day) for day in (7, 8, 9)
    )
    second_black9 = literal_cell(reference, 2, "black", 9)
    month_names = (
        "",
        "正",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
    )
    day_names = (
        "",
        "一",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
        "十三",
        "十四",
        "十五",
    )
    compounds = "、".join(
        f"{month_names[row['textual_month']]}月"
        f"{ {'black': '黑', 'white': '白'}[row['fortnight']]}"
        f"{day_names[row['day']]}{row['mansion_literal']}"
        for row in reference["compound_literal_slots"]
    )
    return [
        "日藏具名版本对照：已取得T0397卷四十二《日藏分中星宿品第八之二》电子文本；"
        f"该表正月白九合{first9}，二月白七合{second7}、白八合{second8}、白九合{second9}，"
        f"二月黑九合{second_black9}（0281a03—26）。"
        "玄应引文仍原样保留二月九日，未明确其白黑分；"
        "它与此具名表的实际引本关系未解，尚未认定T0397此本就是实际引本，"
        "未把正月改成二月，也未断定玄应错引或据此平移当前历日。",
        "本次保留11个月号（正月至七月、九月至十二月）的22段显式白黑月表、330个字面槽；"
        "八月另有黑初胃与白十五昴等叙述锚点，未补造其30个显式表槽。"
        f"复字槽为{compounds}；牛女、女虛复字槽原样保留，未拆分或选成唯一宿。"
        "原文三十摸呼律多为一日夜不等于现代三十小时；"
        "这些表段未确定平明、寅卯钟点、桧尾半日或闰小月补配优先，"
        "不覆盖当前27宿或双向关系，也不是330次独立历史观察或现实样本。",
        *month_name_lines(reference["month_name_reference"]),
        *seasonal_reference_lines(reference["seasonal_time_reference"]),
        *fortnight_calendar_lines(reference["fortnight_calendar_reference"]),
    ]
