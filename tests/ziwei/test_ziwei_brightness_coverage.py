"""锁定紫微亮度的覆盖边界（对照 iztro src/data/stars.ts）。

iztro 仅对 20 颗星定义亮度数组：14 主星 + 文昌、文曲、火星、铃星、擎羊、
陀罗。其余辅曜杂耀（天钺、天魁、左辅、右弼、禄存、天马、天刑、天姚等）在
iztro 中无亮度，故引擎返回 None 是契约设计而非缺漏。本测试锁定该集合，防止
移植时悄悄增删，并钉死"天刑/天钺无亮度"这一点。
"""

from fatebridge.core.ziwei_tables import (
    ZIWEI_STAR_BRIGHTNESS,
    lookup_star_brightness,
)

EXPECTED_BRIGHTNESS_STARS = {
    # 14 主星
    "紫微",
    "天机",
    "太阳",
    "武曲",
    "天同",
    "廉贞",
    "天府",
    "太阴",
    "贪狼",
    "巨门",
    "天相",
    "天梁",
    "七杀",
    "破军",
    # 辅煞星 with brightness
    "文昌",
    "文曲",
    "火星",
    "铃星",
    "擎羊",
    "陀罗",
}


def test_brightness_coverage_matches_iztro():
    assert set(ZIWEI_STAR_BRIGHTNESS) == EXPECTED_BRIGHTNESS_STARS


def test_every_brightness_row_has_twelve_entries():
    for star, row in ZIWEI_STAR_BRIGHTNESS.items():
        assert len(row) == 12, star


def test_non_brightness_stars_return_none_by_design():
    # 命主命宫坐 天刑 / 天钺：iztro 不给亮度，返回 None 是设计而非 bug
    for star in ("天刑", "天钺", "天魁", "左辅", "右弼", "禄存", "天马", "天姚"):
        assert lookup_star_brightness(star, "未") is None


def test_known_brightness_values():
    # 命主命宫在未：火星(利)、陀罗(庙) —— 与排盘输出一致
    assert lookup_star_brightness("火星", "未") == "利"
    assert lookup_star_brightness("陀罗", "未") == "庙"
