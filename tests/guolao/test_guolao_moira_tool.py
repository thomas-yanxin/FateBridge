"""Current discrete-palace pattern inputs, source conditions and public output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fatebridge.core import guolao_moira
from tests.support.transports import SPECS, business, rest, surface_calls

_FIXTURE = Path(__file__).resolve().parents[1] / "data/guolao/moira_palace_inputs.json"


@pytest.fixture(scope="module")
def moira_cases():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.local_data
def test_oracle_fixture_is_nonempty(moira_cases):
    assert moira_cases, "guolaoMoira oracle fixture must contain cases"


@pytest.mark.local_data
def test_good_patterns_sort_before_bad(moira_cases):
    """build order: good first, bad after (matches JS level sort)."""
    for case in moira_cases:
        patterns = guolao_moira.calculate(case["facts"])
        ranks = [0 if p["level"] == "good" else 1 for p in patterns]
        assert ranks == sorted(ranks), case["label"]


@pytest.mark.local_data
def test_god_dependent_patterns_inert_without_gods(moira_cases):
    """日月拱贵人 / 命登岁驾 stay inert when 神煞 positions are absent (oracle cases)."""
    for case in moira_cases:
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


def test_purple_clouds_matches_pinned_horosa_source_controls():
    # Actual pcLon execution at10fb75de, kept independently of FateBridge.
    # https://github.com/Horace-Maxwell/Horosa-Web-App-comprehensively-improved-MacOS/blob/10fb75de980bb0a6e0d1f50c7ee93cc97a88d7de/Horosa-Web/flatlib-ctrad2/flatlib/ephem/tools.py
    controls = [
        (1721425.5, 47.29638140791576),
        (2415020.5, 343.0135251475258),
        (2451544.5, 188.7201016913959),
        (5373449.5, 84.71819983005116),
    ]
    for jd, expected in controls:
        assert guolao_moira.purple_clouds_longitude(jd) == expected


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
        {
            "asc_lon": 75,
            "planet_signidx": {**base, "炁": 4},
            "is_day": False,
            "is_winter": False,
        }
    )
    assert any(p["name"] == "孤月独明" for p in alone)
    # 炁与月同宫(5) → 月不再独居 → 不点亮
    with_qi = guolao_moira.calculate(
        {
            "asc_lon": 75,
            "planet_signidx": {**base, "炁": 5},
            "is_day": False,
            "is_winter": False,
        }
    )
    assert not any(p["name"] == "孤月独明" for p in with_qi)


@pytest.mark.parametrize(
    "day,winter,expected",
    [
        (False, False, [("孤月独明", "good")]),
        (False, True, [("寒月单行", "bad")]),
        (True, False, []),
        (True, True, [("寒月单行", "good")]),
        (None, True, []),
        (False, None, []),
    ],
)
def test_moon_solitude_matches_original_moira_seasonal_rules(day, winter, expected):
    # Executed unmodified Moira1.50Final RuleEntry/RuleParse and three original
    # moon rules at9bb126fd. Its winter-night rule rejects the generic good one.
    planets = dict(zip("日月金木水火土计罗炁孛", range(11)))
    patterns = guolao_moira.calculate(
        {
            "planet_signidx": planets,
            "life_sign_idx": 0,
            "god_signidx": {"岁驾": 0},
            "is_day": day,
            "is_winter": winter,
        }
    )
    levels = [p["level"] != "good" for p in patterns]
    assert levels == sorted(levels)
    assert any(p["name"] == "命登岁驾" for p in patterns)
    moon = [p for p in patterns if p["name"] in {"孤月独明", "寒月单行"}]
    assert [(p["name"], p["level"]) for p in moon] == expected
    for pattern in moon:
        assert pattern["source"].endswith(
            "9bb126fd84997aa26fed6e91b4bdf438fceb0e38/moira_s.prop"
        )
        assert pattern["evidence"]["inputs"]["is_winter"] is winter


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("hour,level", [(0, "bad"), (12, "good")])
def test_cold_moon_rule_reaches_all_three_transports(tool, hour, level, surface_calls):
    # Synthetic J2000 date, selected after confirming all11positions and the
    # actual solar conditions. This checks source rule composition/delivery,
    # not independent absolute astronomy or prediction efficacy.
    inputs = {
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": hour,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 51.5,
    }
    if tool == "astro_chart":
        inputs["chart_variant"] = "guolao_chart"
    fields = [
        "guolao.moira_patterns",
        "guolao.conditions",
        "guolao.profile.pattern_model_id",
        "guolao.rule_trace",
    ]
    response, protocol, code, cli = surface_calls(
        SPECS[tool],
        inputs,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields],
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    outputs = [response.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    result = outputs[0]["guolao"]
    assert result["conditions"]["season"] == "冬"
    assert result["conditions"]["is_day"] == (hour == 12)
    patterns = result["moira_patterns"]
    moon = [p for p in patterns if p["name"] in {"孤月独明", "寒月单行"}]
    assert [(p["name"], p["level"]) for p in moon] == [("寒月单行", level)]
    assert not moon[0]["classical_acceptance"]
    trace = next(
        t
        for t in result["rule_trace"]
        if t["rule_id"] == "moira_conditions_with_seasonal_moon_v3"
    )
    witness = next(
        p for p in trace["outputs"]["matched_patterns"] if p["name"] == "寒月单行"
    )
    assert witness["source"] == moon[0]["source"]


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


@pytest.mark.local_data
def test_section_text_format(moira_cases):
    """build_section_text mirrors runGuolaoMoira: 喜格/忌格 lines, 名（detail）；-joined."""
    # multi-fire case is index 0
    patterns = guolao_moira.calculate(moira_cases[0]["facts"])
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
