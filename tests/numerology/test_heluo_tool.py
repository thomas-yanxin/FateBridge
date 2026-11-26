"""Heluo named examples, transformation rules, sovereign/Nayin tables, and budgets."""

from __future__ import annotations

import json
import time

from fatebridge.core.heluo.chart import (
    TWELVE_SOVEREIGN_HEXAGRAMS,
    assess_nayin_relation,
    calculate,
    sixty_jiazi_nayin_table,
    transform_houtian,
)
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.services.divination import calculate_heluo_analysis

_CASE1 = {"year": "甲子", "month": "丁卯", "day": "庚申", "hour": "庚辰"}


def test_heluo_documented_anchors() -> None:
    """heluoLocal.js:3-4 算例：甲子…→天風姤/上九；丁巳…→水風井。"""
    c1 = calculate(
        four_pillars=_CASE1, gender="男", hour_zhi="辰", birth_year=1924, month_zhi="卯"
    )
    assert c1["xian"]["name"] == "天風姤"
    assert c1["xian"]["yuan"] == 6  # 上九

    c2 = calculate(
        four_pillars={"year": "丁巳", "month": "丙午", "day": "壬寅", "hour": "辛丑"},
        gender="男",
        hour_zhi="丑",
        birth_year=1917,
        month_zhi="午",
    )
    assert c2["xian"]["name"] == "水風井"


def test_heluo_service_shape() -> None:
    result = calculate_heluo_analysis(
        date="2000-05-15",
        time="09:33:00",
        timezone="+08:00",
        gender="男",
        longitude="121e28",
    )
    assert result["analysis_type"] == "河洛理数"
    assert result["chart"]["xian"]["name"] and result["chart"]["hou"]["name"]
    assert len(result["dayun"]["all"]) == 12  # 先天 6 段 + 后天 6 段
    assert result["solar_term"]["term"] == "立夏"
    assert set(result["four_pillars"]) == {"year", "month", "day", "hour"}


def test_heluo_zhizun_bian_er_bu_yi() -> None:
    """三至尊卦(坎為水/水雷屯/水山蹇) 九五阴令/上六阳令『变而不易』特例覆盖。"""

    lines = [0, 1, 0, 0, 1, 0]  # 坎為水
    # 上六(yuan=6) + 阳令 → 变而不易：只翻爻、不互换上下卦、元堂位不动。
    hou = transform_houtian("坎為水", lines, 6, True)
    assert hou["yuan"] == 6
    assert hou["lines"] == [0, 1, 0, 0, 1, 1]


def test_heluo_oracle_1984_sovereign_and_nayin_fortune() -> None:
    """§7.6 Heluo oracle (1984 甲子 丙寅 戊辰 甲寅 男) + 十二辟卦 + 六十甲子纳音吉凶."""
    c = calculate(
        four_pillars={"year": "甲子", "month": "丙寅", "day": "戊辰", "hour": "甲寅"},
        gender="男",
        hour_zhi="寅",
        birth_year=1984,
        month_zhi="寅",
    )
    assert (c["tianNum"], c["tianGua"]) == (3, "震")
    assert (c["diNum"], c["diGua"]) == (2, "坤")
    assert (c["xian"]["name"], c["xian"]["yuan"]) == ("雷地豫", 1)
    assert (c["hou"]["name"], c["hou"]["yuan"]) == ("震為雷", 4)
    assert len(TWELVE_SOVEREIGN_HEXAGRAMS) == 12
    assert c["sovereign_hexagram"]["month_sovereign"]["gua"] == "地天泰"
    assert len(sixty_jiazi_nayin_table()) == 60
    rel = assess_nayin_relation("甲子", "乙巳")
    assert rel["natal_nayin"] == "海中金" and rel["target_nayin"] == "覆灯火"
    assert rel["relation"] == "岁克本命" and rel["auspiciousness"] == "凶"


def test_heluo_modern_gregorian_year_and_budget() -> None:
    """Verify Gregorian analysis_year Lichun bounds and <15ms / <25KB audit budget."""
    build_heluo_result(
        date="1984-02-14",
        time="04:00",
        timezone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    t0 = time.perf_counter()
    res = build_heluo_result(
        date="1984-02-14",
        time="04:00",
        timezone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    payload_bytes = len(json.dumps(res, ensure_ascii=False))
    assert elapsed_ms < 15.0, f"Heluo took {elapsed_ms:.2f}ms >= 15ms"
    assert payload_bytes < 25 * 1024, f"Heluo audit payload {payload_bytes}B >= 25KB"
    assert "nayin_fortune" in res["judge"]

    res_yr = build_heluo_result(
        date="1984-02-14",
        time="04:00",
        timezone="+08:00",
        gender="男",
        analysis_year=2025,
        use_true_solar_time=False,
    )
    annual = res_yr["heluo_timing"]["selected_annual"]
    assert annual["year_label"] == 2025
    assert annual["gregorian_bounds"]["gregorian_year"] == 2025
    assert annual["nayin_fortune"]["target_ganzhi"] == annual["ganzhi"]
