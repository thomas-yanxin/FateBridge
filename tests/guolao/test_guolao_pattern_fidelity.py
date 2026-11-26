"""Condition witnesses, counterfactuals and exact-float boundary regressions.

These test software predicates, not original-text acceptance or prediction.
"""

from copy import deepcopy
from datetime import datetime

import pytest

from fatebridge.core.guolao import moira as m
from fatebridge.services.guolao import calculate_guolao_chart, compact_guolao_chart
from tests.fixtures.surface_payloads import astro_payload

ALONE = dict(zip(m.MOIRA_PLANET_ORDER, range(11)))
CASES = [
    (
        "八杀朝天",
        {"life_sign_idx": 0, "planet_signidx": {"火": 0}},
        {"life_sign_idx": 0, "planet_signidx": {"火": 1}},
        {"life_palace_index": 0, "disease_lord_palace_index": 0},
    ),
    (
        "孤月独明",
        {"planet_signidx": ALONE, "is_day": False, "is_winter": False},
        {"planet_signidx": {**ALONE, "炁": 1}, "is_day": False, "is_winter": False},
        {"moon_palace_index": 1, "same_palace_count": 1, "is_winter": False},
    ),
    (
        "日月拱官",
        {"life_sign_idx": 0, "planet_signidx": {"日": 1, "月": 5}},
        {"life_sign_idx": 0, "planet_signidx": {"日": 1, "月": 6}},
        {"sun_index": 1, "moon_index": 5, "career_index": 9},
    ),
    (
        "金水相涵",
        {"planet_signidx": {"金": 2, "水": 2}, "is_winter": False},
        {"planet_signidx": {"金": 2, "水": 2}, "is_winter": True},
        {"venus_index": 2, "mercury_index": 2, "is_winter": False},
    ),
    (
        "日月拱贵人",
        {
            "planet_signidx": {"日": 4, "月": 8},
            "god_signidx": {"天贵": 0, "玉贵": 1},
            "is_day": True,
        },
        {
            "planet_signidx": {"日": 4, "月": 8},
            "god_signidx": {"天贵": 0, "玉贵": 1},
            "is_day": False,
        },
        {"selected_noble": "天贵", "noble_index": 0},
    ),
    (
        "命登岁驾",
        {"life_sign_idx": 4, "god_signidx": {"岁驾": 4}},
        {"life_sign_idx": 4, "god_signidx": {"岁驾": 5}},
        {"life_palace_index": 4, "suijia_index": 4},
    ),
    (
        "日月失所",
        {"planet_signidx": {"日": 0, "月": 4}},
        {"planet_signidx": {"日": 4, "月": 4}},
        {"sun_branch": "戌", "moon_branch": "午"},
    ),
    (
        "官福失垣",
        {"life_sign_idx": 0, "planet_signidx": {"土": 8}},
        {"life_sign_idx": 0, "planet_signidx": {"土": 2}},
        {},
    ),
    (
        "孛犯太阳",
        {"planet_signidx": {"日": 0, "孛": 0}},
        {"planet_signidx": {"日": 0, "孛": 1}},
        {"sun_index": 0, "apogee_index": 0},
    ),
    (
        "罗犯太阳",
        {"planet_signidx": {"日": 7, "罗": 7}},
        {"planet_signidx": {"日": 7, "罗": 8}},
        {"sun_index": 7, "node_index": 7},
    ),
    (
        "孛罗交战",
        {"planet_signidx": {"孛": 10, "罗": 10}},
        {"planet_signidx": {"孛": 10, "罗": 11}},
        {"node_index": 10, "apogee_index": 10},
    ),
]


@pytest.mark.parametrize("name,positive,negative,expected_inputs", CASES)
def test_each_current_predicate_has_actual_operands_and_changes_with_its_counterfactual(
    name, positive, negative, expected_inputs
) -> None:
    original = deepcopy(positive)
    patterns = m.calculate(positive)
    assert positive == original
    pattern = next(p for p in patterns if p["name"] == name)
    assert name not in {p["name"] for p in m.calculate(negative)}
    if name == "孤月独明":
        assert pattern["rule_id"] == "moira_moon_alone_night_nonwinter_v3"
    else:
        assert pattern["rule_id"].endswith("_v2")
    evidence = pattern["evidence"]
    assert evidence["model_id"] == m.PATTERN_MODEL_ID
    assert evidence["condition_satisfied"]
    for key, value in expected_inputs.items():
        assert evidence["inputs"][key] == value


def test_life_palace_match_does_not_claim_a_calculated_life_degree() -> None:
    pattern = m.calculate({"life_sign_idx": 4, "god_signidx": {"岁驾": 4}})[0]
    assert pattern["name"] == "命登岁驾"
    assert "命宫与岁驾同宫" in pattern["detail"] and "命度" not in pattern["detail"]
    assert pattern["evidence"]["granularity"] == "palace_index"
    assert "longitude" not in pattern["evidence"]["inputs"]


def test_lost_rulership_evidence_exposes_the_actual_two_ruler_chains() -> None:
    result = m.calculate({"life_sign_idx": 0, "planet_signidx": {"土": 8}})
    inputs = next(p for p in result if p["name"] == "官福失垣")["evidence"]["inputs"]
    assert inputs["career"]["palace_index"] == 9
    assert inputs["fortune"]["palace_index"] == 10
    for chain in inputs.values():
        assert chain["palace_ruler"] == "土"
        assert chain["ruler_palace_index"] == 8
        assert (
            chain["ruler_of_ruler_palace"]
            == chain["compatibility_opposing_ruler"]
            == "木"
        )


@pytest.mark.parametrize("mapping", ["planet_signidx", "god_signidx"])
@pytest.mark.parametrize("bad", [True, 1.0, None, -2, 12, float("nan")])
def test_invalid_indices_cannot_become_palace_facts(mapping: str, bad) -> None:
    key = "月" if mapping == "planet_signidx" else "岁驾"
    with pytest.raises((TypeError, ValueError)):
        m.calculate({mapping: {key: bad}})


@pytest.mark.parametrize("key", ["is_day", "is_winter"])
@pytest.mark.parametrize("bad", [0, 1, "false"])
def test_unknown_conditions_are_not_coerced_from_numbers_or_text(
    key: str, bad: int | str
) -> None:
    with pytest.raises(TypeError):
        m.calculate({key: bad})


def test_missing_and_explicit_unknown_values_do_not_create_patterns_or_cross_roles() -> (
    None
):
    assert not m.calculate({})
    assert not m.calculate({"planet_signidx": {"月": -1}})
    with pytest.raises(ValueError):
        m.calculate({"life_sign_idx": 4, "planet_signidx": {"岁驾": 4}})
    with pytest.raises(ValueError):
        m.calculate({"god_signidx": {"月": 4}})


@pytest.mark.parametrize("target", [None, "2027-06-01T00:00:00+08:00"])
def test_native_pattern_trace_and_classical_features(
    target: str | None,
) -> None:
    r = calculate_guolao_chart(
        **{
            **astro_payload(),
            "use_true_solar_time": False,
            "analysis_datetime": datetime.fromisoformat(target) if target else None,
        },
    )
    assert "error" not in r
    g = r["guolao"]
    assert g["profile"]["pattern_model_id"] == m.PATTERN_MODEL_ID
    assert g["life_palace"]["longitude"] is not None
    assert g["life_palace"]["mansion"] is not None
    assert g["body_palace"]["branch"] is not None
    assert len(g["god_positions"]["branches"]) == 33
    assert len(g["hua_yao"]["by_transformation"]) == 10
    assert len(g["dongwei_daxian"]["periods"]) == 12
    assert set(g["en_yong_nan_chou"]["by_life_palace"]) == {
        "恩",
        "用",
        "难",
        "仇",
        "同",
    }
    trace = next(t for t in g["rule_trace"] if t["rule_id"] == m.PATTERN_MODEL_ID)
    assert [p["name"] for p in trace["outputs"]["matched_patterns"]] == [
        p["name"] for p in g["moira_patterns"]
    ]
    assert all(
        p["evidence"]["granularity"] == "palace_index" for p in g["moira_patterns"]
    )


def test_guolao_moira_oracle_and_shoushi_and_compact() -> None:
    import json

    result = calculate_guolao_chart(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4,
        birth_latitude=39.9,
        use_true_solar_time=False,
        analysis_datetime=datetime.fromisoformat("2026-06-01T12:00:00+08:00"),
        month_basis="jie_month",
    )
    g = result["guolao"]
    bodies = {b["name_zh"]: b for b in g["bodies"]}
    assert 54.0 < bodies["日"]["longitude"] < 54.3
    assert bodies["日"]["palace_branch"] == "酉"
    assert g["life_palace"]["branch"] == "巳"
    assert g["life_palace"]["palace_lord"] == "水"
    assert 293.5 < bodies["月"]["longitude"] < 294.1
    assert g["body_palace"]["branch"] == "丑"
    assert g["body_palace"]["palace_lord"] == "土"
    assert g["god_positions"]["year_stem"] == "庚"
    assert g["god_positions"]["year_branch"] == "午"
    assert g["god_positions"]["branches"]["天贵"] == "丑"
    assert g["god_positions"]["branches"]["玉贵"] == "未"
    assert g["god_positions"]["branches"]["岁驾"] == "午"
    assert g["hua_yao"]["by_transformation"]["天禄"] == "水"
    assert g["timing"]["small_limit"]["branch"] == "巳"
    assert g["timing"]["small_limit"]["natal_functional_palace"] == "命"
    assert 311.0 < bodies["罗"]["longitude"] < 311.7
    assert 131.0 < bodies["计"]["longitude"] < 131.7
    assert 231.0 < bodies["孛"]["longitude"] < 231.9
    assert 64.5 < bodies["炁"]["longitude"] < 65.2

    shoushi = calculate_guolao_chart(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4,
        birth_latitude=39.9,
        use_true_solar_time=False,
        mansion_frame="shoushi_ecliptic",
    )
    assert (
        shoushi["guolao"]["life_palace"]["mansion"]["coordinate_unit"]
        == "shoushi_du_365_2575"
    )

    compact = compact_guolao_chart(result)
    assert len(json.dumps(compact, ensure_ascii=False).encode("utf-8")) < 6144
