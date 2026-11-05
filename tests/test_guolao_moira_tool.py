"""Current discrete-palace pattern inputs, source conditions and public output."""

from __future__ import annotations

import json
from pathlib import Path

from fatebridge.core import guolao_moira

_FIXTURE = Path(__file__).resolve().parent / "data/guolao/moira_palace_inputs.json"
_CASES = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _names_levels(patterns):
    return [(p["name"], p["level"]) for p in patterns]


def test_oracle_fixture_is_nonempty():
    assert _CASES, "guolaoMoira oracle fixture must contain cases"


def test_good_patterns_sort_before_bad():
    """build order: good first, bad after (matches JS level sort)."""
    for case in _CASES:
        patterns = guolao_moira.calculate(case["facts"])
        ranks = [0 if p["level"] == "good" else 1 for p in patterns]
        assert ranks == sorted(ranks), case["label"]


def test_god_dependent_patterns_inert_without_gods():
    """日月拱贵人 / 命登岁驾 stay inert when 神煞 positions are absent (oracle cases)."""
    for case in _CASES:
        names = {p["name"] for p in guolao_moira.calculate(case["facts"])}
        assert "日月拱贵人" not in names
        assert "命登岁驾" not in names


def test_purple_clouds_matches_horosa_fixtures():
    """紫炁(木余) horosa 对照锁：4 张 horosa 七政四余盘 fixture 的紫炁黄经，残差 <0.01°。"""
    # (JD_UT, horosa Purple Clouds 黄经) —— chart_guolao / 1998_predictive / liureng / traditional
    horosa_points = [
        (2446145.583333333, 358.66910331920116),
        (2450865.033333333, 164.80172577759032),
        (2461135.054166667, 166.32382978206476),
        (2461193.770833333, 168.39076),
    ]
    for jd, expected in horosa_points:
        got = guolao_moira.purple_clouds_longitude(jd)
        delta = ((got - expected + 180) % 360) - 180
        assert (
            abs(delta) < 0.01
        ), f"jd={jd}: 紫炁 {got} vs horosa {expected} (Δ={delta})"


def test_si_yu_sign_index_matches_horosa_chart():
    """四余(孛/罗/计/炁) horosa 对照锁：chart_guolao fixture(1985-03-21 10:00 +08 上海)。

    horosa 后端实测：孛 Aries(0)、罗 Taurus(1)、计 Scorpio(7)、炁 Pisces(11)。
    """
    from fatebridge.services.astrology import calculate_core_chart_analysis

    guolao = calculate_core_chart_analysis(
        birth_year=1985,
        birth_month=3,
        birth_day=21,
        birth_hour=10,
        birth_minute=0,
        birth_longitude=121.47,
        birth_latitude=31.22,
        chart_variant="guolao_chart",
        birth_timezone="Asia/Shanghai",
    )["guolao"]
    assert guolao["si_yu_sign_index"] == {"孛": 0, "罗": 1, "计": 7, "炁": 11}


def test_gu_yue_du_ming_counts_purple_clouds():
    """孤月独明：紫炁补齐后，同宫计数覆盖全 11 体——炁与月同宫应使月不再「独居」。"""
    base = {
        "日": 1,
        "月": 5,
        "水": 2,
        "金": 3,
        "火": 7,
        "木": 8,
        "土": 9,
        "孛": 10,
        "罗": 0,
        "计": 6,
    }
    # 月独居（炁不在月宫）→ 点亮
    alone = guolao_moira.calculate(
        {"asc_lon": 75, "planet_signidx": {**base, "炁": 4}, "is_day": False}
    )
    assert any(p["name"] == "孤月独明" for p in alone)
    # 炁与月同宫(5) → 月不再独居 → 不点亮
    with_qi = guolao_moira.calculate(
        {"asc_lon": 75, "planet_signidx": {**base, "炁": 5}, "is_day": False}
    )
    assert not any(p["name"] == "孤月独明" for p in with_qi)


def test_god_patterns_fire_when_positions_supplied():
    """供入神煞位置时，日月拱贵人 / 命登岁驾 应能点亮（Phase 2a）。"""
    # 命登岁驾：显式命宫与岁驾同宫。
    dengsuijia = guolao_moira.calculate(
        {"life_sign_idx": 6, "planet_signidx": {}, "god_signidx": {"岁驾": 6}}
    )
    assert any(p["name"] == "命登岁驾" for p in dengsuijia)

    # 日月拱贵人（昼取天贵）：日=天贵+4、月=天贵-4。
    gongguiren = guolao_moira.calculate(
        {
            "life_sign_idx": 3,
            "planet_signidx": {"日": 4, "月": 8},
            "god_signidx": {"天贵": 0},
            "is_day": True,
        }
    )
    assert any(p["name"] == "日月拱贵人" for p in gongguiren)


def test_section_text_format():
    """build_section_text mirrors runGuolaoMoira: 喜格/忌格 lines, 名（detail）；-joined."""
    # multi-fire case is index 0
    patterns = guolao_moira.calculate(_CASES[0]["facts"])
    text = guolao_moira.build_section_text(patterns)
    lines = text.split("\n")
    assert lines[0].startswith("喜格：")
    assert lines[1].startswith("忌格：")
    assert "金水相涵" in lines[0]
    assert "孛犯太阳" in lines[1]
    assert "；" in lines[1]  # multiple 忌格 joined


def test_empty_chart_yields_no_patterns():
    """A chart with no usable positions produces empty 喜格/忌格 (not a crash)."""
    patterns = guolao_moira.calculate({"asc_lon": None, "planet_signidx": {}})
    assert patterns == []
    assert guolao_moira.build_section_text(patterns) == "喜格：（无）\n忌格：（无）"
