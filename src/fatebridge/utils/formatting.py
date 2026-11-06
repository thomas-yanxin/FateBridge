"""Shared response text, pillar representation and JSON formatting."""

import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


def format_birth_datetime_display(
    birth_datetime: datetime,
    include_minutes: bool = False,
    *,
    include_seconds: bool = False,
) -> str:
    """Format birth datetime for user-facing API responses."""
    if include_seconds:
        fraction = (
            f".{birth_datetime.microsecond:06d}" if birth_datetime.microsecond else ""
        )
        return birth_datetime.strftime("%Y年%m月%d日 %H时%M分%S") + fraction + "秒"
    if include_minutes:
        return birth_datetime.strftime("%Y年%m月%d日 %H时%M分")
    return birth_datetime.strftime("%Y年%m月%d日 %H时")


def format_clock_datetime(
    moment: datetime, *, include_seconds: Optional[bool] = None
) -> str:
    """Retain computed subminute values without changing old whole-minute labels."""
    if include_seconds is False:
        return moment.strftime("%Y-%m-%d %H:%M")
    timespec = (
        "microseconds"
        if moment.microsecond
        else "seconds" if include_seconds or moment.second else "minutes"
    )
    return moment.isoformat(sep=" ", timespec=timespec)


def create_pillar_dict(
    pillars: Dict[str, Tuple[str, str]],
) -> Dict[str, Dict[str, str]]:
    """创建标准化的四柱字典格式

    Args:
        pillars: 四柱数据

    Returns:
        标准化的四柱字典
    """
    return {
        "year": {"stem": pillars["year"][0], "branch": pillars["year"][1]},
        "month": {"stem": pillars["month"][0], "branch": pillars["month"][1]},
        "day": {"stem": pillars["day"][0], "branch": pillars["day"][1]},
        "hour": {"stem": pillars["hour"][0], "branch": pillars["hour"][1]},
    }


def format_json_response(
    data: Dict[str, Any],
    *,
    compact: bool = True,
) -> str:
    """统一的JSON格式化函数

    Args:
        data: 要格式化的数据字典
        compact: 是否输出紧凑 JSON

    Returns:
        格式化的JSON字符串
    """
    if compact:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=2)
