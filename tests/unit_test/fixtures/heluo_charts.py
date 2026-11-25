"""Shared chart inputs for Heluo calculation and rule tests."""

from typing import Any

from fatebridge.core.heluo.heluo import calculate
from fatebridge.core.heluo.heluo_hexagrams import _gua_tables, gua_lines

PILLARS = dict(year="甲子", month="丁卯", day="庚申", hour="庚辰")


def example_chart() -> dict[str, Any]:
    return calculate(
        four_pillars=PILLARS,
        gender="男",
        hour_zhi="辰",
        birth_year=1924,
        month_zhi="卯",
    )


def chart_for(gua: str) -> dict[str, Any]:
    chart = example_chart()
    pair = _gua_tables()[0][gua]
    for phase in ("xian", "hou"):
        chart[phase].update(name=gua, **pair, lines=gua_lines(pair["up"], pair["low"]))
    return chart
