"""紫微斗数年界回归：命盘年干支须按农历年（正月初一），非八字立春年柱。

立春～正月初一之间出生者，立春年比正月初一年多一位。命盘的五虎遁宫干、
五行局、紫微落宫、四化、年支系辅煞都随农历年走；若误用八字年柱会让整张
星盘平移一宫。

期望值由 iztro 2.5.8（astro.bySolar，独立软件对照）交叉核对得出。
回归前（误用立春年柱）这些 case 的五行局/命宫干支均不同 —— 见函数 docstring
`_lunar_year_ganzhi`。
"""

from copy import deepcopy
from dataclasses import replace

import pytest

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.services.metaphysics import _build_analysis_seed

# (year, month, day, hour, gender) -> 期望 (五行局, 命宫干支, 命宫大限)
# 四个 case 均出生在立春之后、正月初一之前（或正月初一之后、立春之前）的年界窗口。
BOUNDARY_CASES = [
    ((2002, 2, 8, 10, "男"), ("火六局", "丙申", "6~15")),
    ((1995, 2, 3, 2, "男"), ("火六局", "己丑", "6~15")),
    ((1974, 2, 4, 12, "男"), ("金四局", "壬申", "4~13")),
    ((1985, 2, 15, 6, "男"), ("火六局", "甲戌", "6~15")),
]


def _chart(year: int, month: int, day: int, hour: int, gender: str):
    seed = _build_analysis_seed(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=hour,
    )
    return build_ziwei_chart(seed, gender)


def test_boundary_charts_match_lunar_year():
    for (year, month, day, hour, gender), (ju, ming_gz, daxian) in BOUNDARY_CASES:
        chart = _chart(year, month, day, hour, gender)
        ming = next(p for p in chart["palaces"] if p["name"] == "命宫")
        assert chart["wuxing_ju"]["label"] == ju, (year, month, day)
        assert chart["ming_gong"]["ganzhi"] == ming_gz, (year, month, day)
        assert ming["daxian"] == daxian, (year, month, day)


def test_non_boundary_chart_unaffected():
    # 五月出生远离年界，农历年与立春年一致：修复不改变其结果。
    chart = _chart(1990, 5, 15, 10, "男")
    assert chart["ming_gong"]["ganzhi"] == "戊子"
    assert chart["wuxing_ju"]["label"] == "火六局"


@pytest.mark.parametrize(
    "date,lunar_year,bazi_year_pillar,expected_ming",
    [
        ((2002, 2, 8, 10), 2001, ("壬", "午"), "丙申"),
        ((1995, 2, 3, 2), 1995, ("甲", "戌"), "己丑"),
    ],
)
def test_missing_lunar_year_cannot_use_different_lichun_year(
    date, lunar_year, bazi_year_pillar, expected_ming
):
    year, month, day, hour = date
    seed = _build_analysis_seed(
        analysis_year=year, analysis_month=month, analysis_day=day, analysis_hour=hour
    )
    assert seed.calendar_context["lunar_calendar"]["year"] == lunar_year
    assert seed.pillars["year"] == bazi_year_pillar
    assert build_ziwei_chart(seed, "男")["ming_gong"]["ganzhi"] == expected_ming

    incomplete_context = deepcopy(seed.calendar_context)
    del incomplete_context["lunar_calendar"]["year"]
    incomplete_seed = replace(seed, calendar_context=incomplete_context)
    with pytest.raises(ValueError, match="农历年缺失"):
        build_ziwei_chart(incomplete_seed, "男")

    incomplete_context["lunar_calendar"]["year"] = None
    with pytest.raises(ValueError, match="农历年缺失"):
        build_ziwei_chart(incomplete_seed, "男")
