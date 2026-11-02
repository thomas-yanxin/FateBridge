"""Primary fixed coefficients, rational cases and retained oracle failures."""

import json
import math
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest

from fatebridge.core.jyotish_balas import PLANETS
from fatebridge.core.jyotish_war import BIMBA, STARS, THROUGH_HORA, war_bala

FIXTURES = Path(__file__).parent / "fixtures"
PRIMARY = json.loads((FIXTURES / "jyotish-war-classical.json").read_text())
ORACLE = json.loads((FIXTURES / "jyotish-war-pyjhora-reference.json").read_text())


def inputs():
    longitudes = dict(zip(PLANETS, [0, 30, 60, 120, 180, 240, 300]))
    components = {k: {"summary": dict.fromkeys(PLANETS, 0.0)} for k in THROUGH_HORA}
    sthana = {
        "profile": {"id": "synthetic_hand_inputs"},
        "summary": {p: {"total_virupa": 0.0} for p in PLANETS},
    }
    dig = {"source_id": "synthetic_hand_inputs", "summary": dict.fromkeys(PLANETS, 0.0)}
    return longitudes, components, sthana, dig


def calculate(lons, components, sthana, dig, scenarios=None):
    return war_bala(
        lons,
        components,
        scenarios or {"fixed": components["paksha_bala"]["summary"]},
        sthana,
        dig,
    )


def test_literal_source_constants_and_unusual_fixed_outer_disc_sizes():
    assert BIMBA == PRIMARY["source"]["bimba_arcseconds"]
    assert list(THROUGH_HORA) == PRIMARY["through_hora_keys"]
    assert (
        float(BIMBA["Jupiter"]) == 190.4
    )  # neither19.04 nor a current apparent diameter
    assert float(BIMBA["Saturn"]) == 158.0


def test_independent_hand_totals_divisor_and_signs():
    case = PRIMARY["hand_case"]
    lons, components, sthana, dig = inputs()
    lons.update(case["longitudes"])
    for p, v in case["sthana"].items():
        sthana["summary"][p]["total_virupa"] = v
    dig["summary"].update(case["dig"])
    for k in THROUGH_HORA:
        components[k]["summary"].update(case[k])
    result = calculate(lons, components, sthana, dig)
    evidence = result["evidence"]["fixed"]
    for p, v in case["expected_totals"].items():
        assert evidence["prewar_basis"][p]["total_virupa"] == v
    amount = float(Fraction(case["expected_amount_rational"]))
    assert result["summary"]["Mars"] == pytest.approx(amount, abs=1e-10)
    assert result["summary"]["Mercury"] == pytest.approx(-amount, abs=1e-10)
    assert result["pairs"][0]["winner"] == case["expected_winner"]


@pytest.mark.parametrize("a,b", list(combinations(STARS, 2)))
@pytest.mark.parametrize("reverse", [False, True])
def test_all_ten_pairs_and_both_victor_orders_against_independent_fraction(
    a, b, reverse
):
    lons, components, sthana, dig = inputs()
    lons[a], lons[b] = (15.25, 15.0) if reverse else (15.0, 15.25)
    sthana["summary"][a]["total_virupa"] = 200
    sthana["summary"][b]["total_virupa"] = 100
    result = calculate(lons, components, sthana, dig)
    denominator = abs(
        Fraction(PRIMARY["source"]["bimba_arcseconds"][a])
        - Fraction(PRIMARY["source"]["bimba_arcseconds"][b])
    )
    expected = float(Fraction(100) / denominator)
    winner, loser = (b, a) if reverse else (a, b)
    assert result["summary"][winner] == pytest.approx(expected, abs=1e-10)
    assert result["summary"][loser] == pytest.approx(-expected, abs=1e-10)
    assert (
        sum(result["summary"].values()) == 0
    )  # transfer, not creation of total strength


@pytest.mark.parametrize("key", PRIMARY["through_hora_keys"])
def test_every_through_hora_component_including_all_three_calendar_lords(key):
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=100.5)
    components[key]["summary"]["Mars"] = 30
    result = calculate(lons, components, sthana, dig)
    assert result["summary"]["Mars"] == pytest.approx(float(Fraction(75, 7)), abs=1e-10)


@pytest.mark.parametrize("key", PRIMARY["excluded"])
def test_later_or_cyclic_strength_components_are_not_in_prewar_basis(key):
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=100.5)
    sthana["summary"]["Mars"]["total_virupa"] = 100
    expected = calculate(lons, components, sthana, dig)
    components[key] = {"summary": dict.fromkeys(PLANETS, 9999.0)}
    assert calculate(lons, components, sthana, dig) == expected


def test_literal_strict_distance_boundary_and_no_added_same_sign_gate():
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=101)
    assert not calculate(lons, components, sthana, dig)["candidates"]
    lons["Mercury"] = math.nextafter(101.0, -math.inf)
    assert calculate(lons, components, sthana, dig)["candidates"]
    lons.update(Mars=29.8, Mercury=30.2)
    assert calculate(lons, components, sthana, dig)["pairs"][0]["winner"] == "Mars"


@pytest.mark.parametrize(
    "pair,expected",
    [
        ((120, 120), "equal_longitude_unadjudicated"),
        ((359.75, 0.25), "longitude_origin_crossing_unadjudicated"),
    ],
)
def test_equal_and_origin_cut_cases_remain_missing_even_if_strength_difference_zero(
    pair, expected
):
    lons, components, sthana, dig = inputs()
    lons.update(Mars=pair[0], Mercury=pair[1])
    result = calculate(lons, components, sthana, dig)
    assert result["pairs"][0]["status"] == expected
    assert result["summary"]["Mars"] is result["summary"]["Mercury"] is None
    assert result["summary"]["Jupiter"] == 0


def test_all_connected_three_planet_participants_stay_missing_including_chain_endpoint():
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=100.75, Jupiter=101.5)
    result = calculate(lons, components, sthana, dig)
    assert len(result["pairs"]) == 2
    for p in ["Mars", "Mercury", "Jupiter"]:
        assert result["summary"][p] is None
    assert result["summary"]["Venus"] == 0
    assert all(
        p["status"] == "simultaneous_multi_planet_war_unadjudicated"
        for p in result["pairs"]
    )


def test_disjoint_pair_still_computes_when_other_pair_has_missing_basis():
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=100.5, Jupiter=200, Venus=200.5)
    dig["summary"]["Mercury"] = None
    sthana["summary"]["Jupiter"]["total_virupa"] = 100
    result = calculate(lons, components, sthana, dig)
    assert result["summary"]["Mars"] is result["summary"]["Mercury"] is None
    assert result["summary"]["Jupiter"] > 0 and result["summary"]["Venus"] < 0
    assert result["summary"]["Sun"] == result["summary"]["Moon"] == 0
    assert (
        "dig_bala"
        in result["evidence"]["fixed"]["prewar_basis"]["Mercury"]["missing_inputs"]
    )


def test_sun_moon_nodes_never_hide_star_pair_and_no_arbitrary_sixty_cap():
    lons, components, sthana, dig = inputs()
    lons.update(Sun=10, Moon=10.01, Mars=100, Mercury=100.5, Rahu=100, Ketu=280)
    sthana["summary"]["Mars"]["total_virupa"] = 200
    result = calculate(lons, components, sthana, dig)
    assert result["summary"]["Mars"] > 60
    assert result["summary"]["Mercury"] < -60
    assert result["summary"]["Sun"] == result["summary"]["Moon"] == 0


def test_nature_branches_keep_conserved_pair_contributions_without_choosing_highest():
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=100.5)
    sthana["summary"]["Mars"]["total_virupa"] = 20
    sthana["summary"]["Mercury"]["total_virupa"] = 100
    branches = {
        "a": dict.fromkeys(PLANETS, 0.0),
        "b": {**dict.fromkeys(PLANETS, 0.0), "Mercury": 60.0},
    }
    result = calculate(lons, components, sthana, dig, branches)
    assert result["summary"]["Mars"] is result["summary"]["Mercury"] is None
    for name, expected in [("a", Fraction(200, 7)), ("b", 50)]:
        assert result["scenarios"][name]["Mars"] == pytest.approx(
            float(expected), abs=1e-10
        )
        assert (
            result["scenarios"][name]["Mercury"] == -result["scenarios"][name]["Mars"]
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True])
def test_invalid_strength_input_cannot_be_serialized_as_an_amount(value):
    lons, components, sthana, dig = inputs()
    lons.update(Mars=100, Mercury=100.5)
    sthana["summary"]["Mars"]["total_virupa"] = value
    with pytest.raises(ValueError, match="finite"):
        calculate(lons, components, sthana, dig)


@pytest.mark.parametrize("case", ORACLE["rows"], ids=lambda c: c["id"])
def test_pinned_third_party_agreement_and_counterexamples_are_retained(case):
    lons, components, sthana, dig = inputs()
    lons.update(zip(PLANETS, case["longitudes"]))
    for p, v in zip(PLANETS, case["sthana"]):
        sthana["summary"][p]["total_virupa"] = v
    for field, key in [
        ("abda", "abda_bala"),
        ("masa", "masa_bala"),
        ("dina", "dina_bala"),
    ]:
        components[key]["summary"].update(zip(PLANETS, case.get(field, [0] * 7)))
    result = calculate(lons, components, sthana, dig)
    raw = case["raw_pyjhora_yuddha"]
    if case["id"] == "single_pair_zero_calendar":
        assert result["summary"] == pytest.approx(raw, abs=0.0050000001)
    elif case["id"] == "no_pair_within_one_degree":
        assert not result["candidates"] and raw["Mars"] != 0
    elif case["id"] == "sun_moon_hide_real_star_pair":
        assert result["summary"]["Mars"] > 0 and raw["Mars"] == 0
    elif case["id"] == "calendar_lords_omitted":
        assert result["summary"]["Mars"] == pytest.approx(
            float(Fraction(475, 7)), abs=1e-10
        )
        assert result["summary"]["Mars"] != pytest.approx(raw["Mars"], abs=0.0050000001)
    else:
        assert result["summary"]["Mars"] is None and any(v != 0 for v in raw.values())
