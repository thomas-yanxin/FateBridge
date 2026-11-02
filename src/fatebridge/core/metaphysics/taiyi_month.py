"""Key completed-year month count, with a declared modern Jie boundary adapter."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

from .taiyi_hour import KEY_SOURCE

TaiyiMonthProfile = Literal["jinjing_month_jie_360_v1", "key_month_tianzheng_jie_v1"]
DEFAULT_MONTH_PROFILE = "jinjing_month_jie_360_v1"
KEY_MONTH_PROFILE = "key_month_tianzheng_jie_v1"
MONTH_PROFILES = {DEFAULT_MONTH_PROFILE, KEY_MONTH_PROFILE}


def jinjing_month_origin(cycle_year: int, month_offset: int) -> dict[str, Any]:
    """Expose the adapter's actual year and unit without asserting an ancient epoch.

    The sought nominal year follows the Tianzheng11/Daxue anchor year.
    Subtracting one from that nominal year counts completed years once.
    The Key appendix arithmetic and Wujing 前十一月 constrain this reading;
    neither restores historical Jie boundaries or the mean-lunation calendar.
    """
    if (
        type(cycle_year) is not int
        or not 1 <= cycle_year <= 9999
        or type(month_offset) is not int
        or not 0 <= month_offset < 12
    ):
        raise ValueError("金镜节月须明确大雪起算公历年与0至11节月序")
    counted_year = cycle_year + 1
    annual = 1937281 + counted_year - 724
    accumulation = (annual - 1) * 12 + month_offset + 1
    return {
        "profile": DEFAULT_MONTH_PROFILE,
        "cycle_year": cycle_year,
        "counted_year": counted_year,
        "counted_year_basis": "nominal_year_after_tianzheng11",
        "source_epoch_year": 724,
        "source_epoch_annual_accumulation": 1937281,
        "annual_accumulation": annual,
        "completed_annual_accumulation": annual - 1,
        "months_per_year": 12,
        "month_offset": month_offset,
        "month_number_from_daxue": month_offset + 1,
        "accumulation": accumulation,
        "counter_unit": "twelve_jie_months",
        "mean_lunation_counter": False,
        "source_year_label_adjudicated": False,
        "year_label_policy": "天正十一月窗按其后所求名义年取积年减一；大雪公历锚年已是该名前一年，不再重复减年。金钥匙附例及武经年前十一月补证本取数，完整古历年界仍未裁定。",
        "scope": "现行六纪节月适配，闰朔月不增数；未使用章岁章月求日计经朔累月，不是完整王氏同元四分历。",
    }


def jinjing_month_origin_text(origin: dict[str, Any]) -> str:
    """Render the stored origin; no new calendar or counter computation."""
    return (
        f"月计配置：{origin['profile']}；大雪公历起算年{origin['cycle_year']}，"
        f"本盘年标{origin['counted_year']}；完整节月积数"
        f"({origin['annual_accumulation']} - 1) × 12 + "
        f"{origin['month_number_from_daxue']} = {origin['accumulation']}。"
        f"{origin['year_label_policy']}{origin['scope']}"
    )


def key_month_origin(cycle_year: int, month_offset: int) -> dict[str, Any]:
    if (
        type(cycle_year) is not int
        or not 1 <= cycle_year <= 9999
        or type(month_offset) is not int
        or not 0 <= month_offset < 12
    ):
        raise ValueError("月计须明确大雪起算年与0至11节月序")
    nominal_year = cycle_year + int(month_offset >= 2)
    nominal_month = (month_offset + 10) % 12 + 1
    annual = 10155478 + nominal_year - 1561
    full = (annual - 1) * 12 + 2 + nominal_month
    shortcut_completed = nominal_year - 1504
    shortcut = shortcut_completed * 12 + 2 + nominal_month
    return {
        "source": KEY_SOURCE,
        "cycle_year": cycle_year,
        "nominal_year": nominal_year,
        "nominal_month": nominal_month,
        "year_label_policy": "现代节月寅月换名义年标；非原书月界及岁首复原。",
        "source_epoch_year": 1561,
        "source_epoch_accumulation": 10155478,
        "annual_accumulation": annual,
        "completed_annual_accumulation": annual - 1,
        "months_per_year": 12,
        "tianzheng_preceding_months": 2,
        "tianzheng_month_offset": nominal_month + 2,
        "accumulation": full,
        "shortcut_epoch_year": 1504,
        "shortcut_inclusive_years": shortcut_completed + 1,
        "shortcut_completed_years": shortcut_completed,
        "shortcut_completed_months": shortcut_completed * 12,
        "shortcut_count": shortcut,
        "full_minus_shortcut": full - shortcut,
        "shared_cycle_lcm": 720,
        "all_shared_cycles_aligned": (full - shortcut) % 720 == 0,
        "cycle360": (full - 1) % 360 + 1,
        "palace_month_number": (full - 1) % 3 + 1,
        "source_chart_ju_unadjudicated": None,
        "scope": "开辟祖数先减一年、乘十二、再加天地二正及本月名义序；节月边界为声明的现代适配，非完整古历。1504前截数可负，实际起局始终用正的完整积月。",
    }


@lru_cache(maxsize=1)
def month_source_data() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[2] / "data/classical/taiyi-key-month-v1.json"
    )
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def month_calendar_reference(
    civil_date: date, origin: dict[str, Any]
) -> dict[str, Any] | None:
    data = month_source_data()
    calendar = data["calendar"]
    if (
        not calendar["month_start"]["gregorian"]
        <= civil_date.isoformat()
        < calendar["next_month_start"]["gregorian"]
    ):
        return None
    source = data["month_example"]
    return {
        "source_label": source["label"],
        "source_calendar_basis": "not_adjudicated",
        "comparison_hypothesis": "original_month_label_as_lunar_month",
        "lunar_month_start_julian": calendar["month_start"]["julian"],
        "lunar_month_start_gregorian": calendar["month_start"]["gregorian"],
        "next_lunar_month_start_gregorian": calendar["next_month_start"]["gregorian"],
        "calendar_title": calendar["title"],
        "calendar_authors": calendar["authors"],
        "calendar_edition": calendar["edition"],
        "calendar_printed_page": calendar["printed_page"],
        "calendar_source": calendar["url"],
        "source_month": source["nominal_month"],
        "actual_nominal_month": origin["nominal_month"],
        "month_label_matches": (origin["nominal_year"], origin["nominal_month"])
        == (source["year"], source["nominal_month"]),
        "source_shortcut_count": source["counter"],
        "actual_shortcut_count": origin["shortcut_count"],
        "counter_matches": origin["shortcut_count"] == source["counter"],
        "scope": "原例仅写九月戊戌，尚不能独立裁定其朔月或节月边界。独立历表核对将九月解释为朔月的假设：所选日期仍在历表九月而现代节月已换亥月时明示差异，不据此证明原例必用朔月，也不补造原地点、日时。",
    }
