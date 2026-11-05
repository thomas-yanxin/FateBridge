"""Condition witnesses, counterfactuals and exact-float boundary regressions.

These test software predicates, not original-text acceptance or prediction.
"""

from copy import deepcopy
from datetime import datetime

import pytest

from fatebridge.core import guolao_moira as m
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.fixtures.surface_payloads import astro_payload

ALONE = dict(zip(m._MOIRA_PLANET_ORDER, range(11)))
CASES = [
    (
        "八杀朝天",
        {"life_sign_idx": 0, "planet_signidx": {"火": 0}},
        {"life_sign_idx": 0, "planet_signidx": {"火": 1}},
        {"life_palace_index": 0, "disease_lord_palace_index": 0},
    ),
    (
        "孤月独明",
        {"planet_signidx": ALONE, "is_day": False},
        {"planet_signidx": {**ALONE, "炁": 1}, "is_day": False},
        {"moon_palace_index": 1, "same_palace_count": 1},
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
):
    original = deepcopy(positive)
    patterns = m.calculate(positive)
    assert positive == original
    pattern = next(p for p in patterns if p["name"] == name)
    assert name not in {p["name"] for p in m.calculate(negative)}
    assert pattern["rule_id"].endswith("_v2")
    evidence = pattern["evidence"]
    assert evidence["model_id"] == m.PATTERN_MODEL_ID
    assert evidence["condition_satisfied"]
    assert not evidence["classical_acceptance"]
    assert not evidence["event_probability_estimated"]
    for key, value in expected_inputs.items():
        assert evidence["inputs"][key] == value


def test_life_palace_match_does_not_claim_a_calculated_life_degree():
    pattern = m.calculate({"life_sign_idx": 4, "god_signidx": {"岁驾": 4}})[0]
    assert pattern["name"] == "命登岁驾"
    assert "命宫与岁驾同宫" in pattern["detail"] and "命度" not in pattern["detail"]
    assert pattern["evidence"]["granularity"] == "palace_index"
    assert "longitude" not in pattern["evidence"]["inputs"]


def test_lost_rulership_evidence_exposes_the_actual_two_ruler_chains():
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
def test_invalid_indices_cannot_become_palace_facts(mapping, bad):
    key = "月" if mapping == "planet_signidx" else "岁驾"
    with pytest.raises((TypeError, ValueError)):
        m.calculate({mapping: {key: bad}})


@pytest.mark.parametrize("key", ["is_day", "is_winter"])
@pytest.mark.parametrize("bad", [0, 1, "false"])
def test_unknown_conditions_are_not_coerced_from_numbers_or_text(key, bad):
    with pytest.raises(TypeError):
        m.calculate({key: bad})


def test_missing_and_explicit_unknown_values_do_not_create_patterns_or_cross_roles():
    assert not m.calculate({})
    assert not m.calculate({"planet_signidx": {"月": -1}})
    with pytest.raises(ValueError):
        m.calculate({"life_sign_idx": 4, "planet_signidx": {"岁驾": 4}})
    with pytest.raises(ValueError):
        m.calculate({"god_signidx": {"月": 4}})


@pytest.mark.parametrize("target", [None, "2027-06-01T00:00:00+08:00"])
def test_native_reading_evidence_resolves_to_the_same_calculation_and_preserves_nulls(
    target,
):
    r = calculate_core_chart_analysis(
        chart_variant="guolao_chart",
        **{
            **astro_payload(),
            "analysis_datetime": datetime.fromisoformat(target) if target else None,
        },
    )
    assert "error" not in r
    g = r["guolao"]
    assert g["profile"]["pattern_model_id"] == m.PATTERN_MODEL_ID
    assert g["life_palace"]["longitude"] is None and g["life_palace"]["mansion"] is None
    assert set(r["interpretation_evidence"]) == set(r["interpretation"])
    for evidence in r["interpretation_evidence"].values():
        assert evidence["policy_id"] == "guolao_calculation_reading_v2"
        for path in evidence["source_paths"]:
            value = r
            for part in path.split("."):
                value = value[part]
    trace = next(t for t in g["rule_trace"] if t["rule_id"] == m.PATTERN_MODEL_ID)
    assert [p["name"] for p in trace["outputs"]["matched_patterns"]] == [
        p["name"] for p in g["moira_patterns"]
    ]
    assert all(
        p["evidence"]["granularity"] == "palace_index" for p in g["moira_patterns"]
    )
    assert not g["validation"]["classical_acceptance_passed"]
