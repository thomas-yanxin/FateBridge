"""Keep the Key's winter-Jiazi hour count separate from solstice reset hours.

The civil/apparent clock and 23:00 day boundary are explicit modern adapters.
This does not implement the unresolved Jinjing ancient-calendar constants.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from fatebridge.core.almanac import get_day_ganzhi

from .common import SEXAGENARY_INDEX

TaiyiHourProfile = Literal["jinjing_hour_solstice_v1", "key_hour_winter_jiazi_v1"]
DEFAULT_HOUR_PROFILE = "jinjing_hour_solstice_v1"
KEY_HOUR_PROFILE = "key_hour_winter_jiazi_v1"
HOUR_PROFILES = {DEFAULT_HOUR_PROFILE, KEY_HOUR_PROFILE}
KEY_SOURCE = (
    "https://www.shidianguji.com/zh/book/NGJ89241199902106666022/chapter/1lq8dkylq3yn8"
)


def double_hour_slot(clock: datetime) -> int:
    """23:00 starts 子, without rounding away boundary microseconds."""
    microseconds = (
        (clock.hour * 60 + clock.minute) * 60 + clock.second
    ) * 1000000 + clock.microsecond
    return clock.toordinal() * 12 + (microseconds + 3600_000000) // 7200_000000


def key_hour_origin(winter_clock: datetime, target_clock: datetime) -> dict[str, Any]:
    if winter_clock.tzinfo is not None or target_clock.tzinfo is not None:
        raise ValueError("金钥匙时计须先确定所选民用/真太阳钟，再传无时区钟面")
    winter_ordinal = double_hour_slot(winter_clock) // 12
    winter_day = datetime.fromordinal(winter_ordinal)
    winter_ganzhi = get_day_ganzhi(winter_day.year, winter_day.month, winter_day.day)
    origin_ordinal = winter_ordinal - SEXAGENARY_INDEX[winter_ganzhi]
    if origin_ordinal < 2:
        raise ValueError("冬至前甲子锚点超出可表达日期")
    origin_day = datetime.fromordinal(origin_ordinal)
    origin_clock = origin_day - timedelta(hours=1)
    target_slot = double_hour_slot(target_clock)
    day_number = target_slot // 12 - origin_ordinal + 1
    branch_index = target_slot % 12
    if day_number < 1:
        raise ValueError("时计所求日期早于冬至前甲子锚点")
    accumulation = (day_number - 1) * 12 + branch_index + 1
    effective_day = datetime.fromordinal(target_slot // 12)
    return {
        "source": KEY_SOURCE,
        "winter_clock": winter_clock.isoformat(),
        "winter_effective_date": winter_day.date().isoformat(),
        "winter_day_ganzhi": winter_ganzhi,
        "origin_effective_date": origin_day.date().isoformat(),
        "origin_day_ganzhi": "甲子",
        "origin_clock": origin_clock.isoformat(),
        "origin_day_selection": "甲子日在冬至所属日或此前；包含同日为现代适配约定，待古例裁定",
        "target_effective_date": effective_day.date().isoformat(),
        "target_day_ganzhi": get_day_ganzhi(
            effective_day.year, effective_day.month, effective_day.day
        ),
        "day_number": day_number,
        "hour_number": branch_index + 1,
        "accumulation": accumulation,
        "gate_cycle_counter": (accumulation - 1) % 120 + 1,
        "day_boundary": "23:00_Zi_initial_modern_convention",
        "scope": "只适配原文冬至前甲子积时规则；古历冬至、时区及夜半子初差别未复原，不用甲己捷数替代完整积时。",
    }
