"""Tests for the canping (邵子参评数 / 金锁银匙) tool.

The historical golden in ``tests/fixtures/canping_golden_snapshot.txt`` was produced
by running horosa's own ``canpingLocal.js`` (buildSnapshotText) on fixed pillars
庚午/寅/巳/午, 男, 明法, 起运 3, 流年支 戌. It is retained as port history;
named primary-source corrections are applied explicitly in the comparison.
Fixed-pillar arithmetic and source selection use no ephemeris.
"""

from __future__ import annotations

from pathlib import Path

from fatebridge.core.canping import (
    build_snapshot_text,
    calculate,
    compute_number,
    nayin_element,
)
from fatebridge.services.divination import calculate_canping_analysis
from fatebridge.utils.data import get_nayin

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "canping_golden_snapshot.txt"

# horosa NAYIN_PAIRS (canpingLocal.js:18-29): (ganzhi_a, ganzhi_b, element).
_HOROSA_NAYIN_PAIRS = [
    ("甲子", "乙丑", "金"),
    ("丙寅", "丁卯", "火"),
    ("戊辰", "己巳", "木"),
    ("庚午", "辛未", "土"),
    ("壬申", "癸酉", "金"),
    ("甲戌", "乙亥", "火"),
    ("丙子", "丁丑", "水"),
    ("戊寅", "己卯", "土"),
    ("庚辰", "辛巳", "金"),
    ("壬午", "癸未", "木"),
    ("甲申", "乙酉", "水"),
    ("丙戌", "丁亥", "土"),
    ("戊子", "己丑", "火"),
    ("庚寅", "辛卯", "木"),
    ("壬辰", "癸巳", "水"),
    ("甲午", "乙未", "金"),
    ("丙申", "丁酉", "火"),
    ("戊戌", "己亥", "木"),
    ("庚子", "辛丑", "土"),
    ("壬寅", "癸卯", "金"),
    ("甲辰", "乙巳", "火"),
    ("丙午", "丁未", "水"),
    ("戊申", "己酉", "土"),
    ("庚戌", "辛亥", "金"),
    ("壬子", "癸丑", "木"),
    ("甲寅", "乙卯", "水"),
    ("丙辰", "丁巳", "土"),
    ("戊午", "己未", "火"),
    ("庚申", "辛酉", "木"),
    ("壬戌", "癸亥", "水"),
]


def test_canping_nayin_parity_with_fb_get_nayin():
    """FB get_nayin element must match horosa's NAYIN_ELEMENT for all 60 ganzhi."""
    for a, b, element in _HOROSA_NAYIN_PAIRS:
        for ganzhi in (a, b):
            assert nayin_element(ganzhi) == element
            assert get_nayin(ganzhi[0], ganzhi[1])[-1] == element


def test_canping_compute_number_documented_anchor():
    """本命 巳/午/火 → 2242/3242, the algorithm's own documented test case."""
    result = compute_number("巳", "午", "火")
    assert result["numShun"] == 2242
    assert result["numNi"] == 3242


def test_canping_historical_snapshot_with_documented_primary_text_corrections():
    """Retain the historical port fixture and apply named, source-checked deltas."""
    result = calculate(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        gender="男",
        method="ming",
        qiyun_age=3,
        liunian_branch="戌",
        active_dayun_branch="申",
    )
    expected = _FIXTURE.read_text(encoding="utf-8").rstrip("\n")
    # 卷六金部明文同支十三位，原先顺1/逆13属于移植缺陷。
    expected = expected.replace(
        "33-42岁 亥：顺2179  ／ 逆3379",
        "33-42岁 亥：顺3379 塞翁須失馬，反禍又成福。 ／ 逆3379",
    )
    # Earth PDF 99, 102 and 104: literal.tsv is checked against the overlay in
    # test_canping_earth_depth; this migration does not rewrite the port fixture.
    for inherited, primary in (
        ("酩酊見街盃", "酩酊見衝盃"),
        ("收威並失勢", "收威并失勢"),
        ("喬校須出群", "喬枝須出群"),
        ("良畫惟歸去", "良晝惟歸去"),
    ):
        assert inherited in expected
        expected = expected.replace(inherited, primary)
    # Historical content remains a port fixture; source/column states are now
    # appended separately instead of silently certifying that inherited text.
    assert build_snapshot_text(result).split("\n\n[参评选条与来源]")[0] == expected


def test_canping_service_full_shape():
    result = calculate_canping_analysis(
        date="1990-06-15",
        time="09:33:00",
        zone="+08:00",
        gender="男",
        method="ming",
        lon="121e28",  # Fictional test coordinate, now supplied explicitly.
    )
    assert result["analysis_type"] == "邵子参评数 / 金锁银匙"
    assert result["element"] in {"金", "木", "水", "火", "土"}
    assert (
        result["ming_gong"] is None
    )  # Named month-pillar schedule does not use a fabricated Minggong.
    assert result["canping_timing"]["profile_id"] == "bazi_appendix_v1"
    assert set(result["four_pillars"]) == {"year", "month", "day", "hour"}
    # Full 120 sexagenary-year labels, with actual date segments.
    assert len(result["liunian_series"]["rows"]) == 120
    assert result["liunian_series"]["year_boundary"] == "lichun"
    assert result["snapshot_text"].startswith("[起盘]")


def test_canping_gu_method_uses_day_branch():
    ming = calculate(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        method="ming",
    )
    gu = calculate(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        method="gu",
    )
    # 古法日宫支 = 八字日支; 明法用月支反向 (寅→亥), so the two diverge.
    assert gu["dayPalaceBranch"] == "巳"
    assert ming["dayPalaceBranch"] == "亥"
