"""Sealed original arithmetic, discontinuities, missing facts and source conflicts."""

import copy
import math
from datetime import datetime
from fractions import Fraction
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.astrology_horary import _planet_state
from fatebridge.core.lilly_fortune import evaluate_fortune
from fatebridge.core.lilly_house_assignment import (
    HOUSE_ATTRIBUTES,
    assign_cusp_virtue,
    assign_from_cusps,
)
from fatebridge.core.output_western import LillyFortune, LillyHouseAssignment
from fatebridge.core.predictive.native_chart import build_native_subject
from scripts.audit_western_lilly_fortune import audit
from tests.test_western_lilly_fortitudes import inputs, result, row


def fortune(longitude=80, house=2):
    states, physical = inputs()
    assignment = {
        "assigned_house": house,
        "geometric_house": house,
        "assignment_policy": "explicit_test_house_fact",
    }
    return evaluate_fortune(
        longitude + states["Sun"]["longitude"] - states["Moon"]["longitude"],
        states,
        physical,
        house_assignment=assignment,
        house_system="R",
        zodiac_type="Tropic",
    )


def by_code(value, code):
    return next(r for r in value["rows"] if r["code"] == code)


def test_all_printed_rows_and_arithmetic_preserve_failed_original_application():
    value = audit()
    assert value["source_assets_verified"] == 34
    assert value["printed_table_rows_verified"] == 28
    assert value["formula_examples_passed"] == len(value["formula_examples"]) == 2
    assert value["p177_next_cusp_gap_degrees"] == float(Fraction(385, 60))
    assert value["p33_policy_assigned_house"] == 1
    assert value["p180_printed_assigned_house"] == 2
    assert value["p180_full_application_reproduced"] is False
    assert value["whole_audit_passed"] is False
    assert value["p180_printed_balance"] == -2
    assert value["candidate_literal_balance"] != -2
    assert {r["row"] for r in value["p180_row_differences"]} >= {
        "P09",
        "P11",
        "P16",
        "N06",
    }
    LillyFortune.model_validate(value["candidate"])


@pytest.mark.parametrize("house", [1, 12])
@pytest.mark.parametrize(
    "delta,expected_advance",
    [
        (math.nextafter(5.0, -math.inf), True),
        (5.0, True),
        (math.nextafter(5.0, math.inf), False),
    ],
)
def test_five_degree_boundary_uses_exact_gap_before_any_display_rounding(
    house, delta, expected_advance
):
    # The input gap is preserved as a dyadic fraction, avoiding rounded subtraction.
    value = assign_cusp_virtue(-Fraction(delta), house, -30, 0)
    assert value["assigned_house"] == (house % 12 + 1 if expected_advance else house)
    assert Fraction(value["next_cusp_gap_exact_degrees"]) == Fraction(delta)
    LillyHouseAssignment.model_validate(value)


@pytest.mark.parametrize("offset,assigned", [(1, 1), (3, None), (5, 2)])
def test_narrow_house_uses_nearest_cusp_and_retains_equal_distance_ambiguity(
    offset, assigned
):
    value = assign_cusp_virtue(offset, 1, 0, 6)
    assert value["assigned_house"] == assigned
    if assigned is None:
        assert value["unavailable_reason"] == "equal_nearest_cusps_within_five_degrees"


def test_no_same_sign_gate_and_no_change_to_geometric_or_role_house():
    r = assign_cusp_virtue(29, 1, 10, 31)
    assert r["geometric_house"] == 1 and r["assigned_house"] == 2
    subject = SimpleNamespace(
        is_diurnal=False,
        houses_system_identifier="R",
        zodiac_type="Tropic",
        saturn=SimpleNamespace(abs_pos=357.0, speed=0.1, house="Twelfth_House"),
    )
    for i, key in enumerate(HOUSE_ATTRIBUTES):
        setattr(subject, key, SimpleNamespace(abs_pos=i * 30.0))
    state = _planet_state(subject, "Saturn")
    assert state["occupied_house"] == 12
    assert state["house_condition"]["p115_house_points"] == -5
    assert state["house_assignment"]["assigned_house"] == 1
    assert state["house_assignment"]["assigned_p115_house_points"] == 5
    assert subject.saturn.abs_pos == 357 and subject.saturn.house == "Twelfth_House"


def test_complete_ring_is_verified_and_native_projected_occupancy_is_not_overridden():
    cusps = list(range(0, 360, 30))
    assert assign_from_cusps(357, cusps)["assigned_house"] == 1
    assert assign_from_cusps(0, cusps)["assigned_house"] == 1
    mismatch = assign_from_cusps(357, cusps, native_occupied_house=1)
    assert (
        mismatch["assigned_house"] is None
        and "disagrees" in mismatch["unavailable_reason"]
    )
    cusps[2], cusps[3] = cusps[3], cusps[2]
    bad = assign_from_cusps(357, cusps, native_occupied_house=12)
    assert bad["assigned_house"] is None and "partition" in bad["unavailable_reason"]


def test_fortitude_rows_use_source_assignment_and_missing_assignment_is_not_zero():
    states, data = inputs()
    states["Mars"]["house_assignment"] = {
        "assigned_house": 6,
        "assignment_policy": "test",
    }
    r = result(states, data)
    assert row(r, "Mars", "F01")["satisfied"] is False
    assert row(r, "Mars", "D02")["contribution"] == -2
    states["Mars"]["house_assignment"]["assigned_house"] = None
    r = result(states, data)
    assert r["planets"]["Mars"]["literal_table_balance"] is None
    assert row(r, "Mars", "F01")["status"] == "unknown"


@pytest.mark.parametrize(
    "house,code,expected", [(6, "N09", -4), (8, "N08", -4), (12, "N07", -5)]
)
def test_fortune_has_its_own_house_table_not_the_planet_debility_weights(
    house, code, expected
):
    r = fortune(house=house)
    assert by_code(r, code)["contribution"] == expected
    assert by_code(r, "P11")["contribution"] == 0
    assert r["house_assignment"]["assigned_p145_house_points"] == expected
    assert "assigned_p115_house_points" not in r["house_assignment"]


@pytest.mark.parametrize(
    "longitude,term,bonus",
    [
        (156.999, "Mercury", 0),
        (157, "Venus", 2),
        (163, "Jupiter", 2),
        (168, "Saturn", 0),
    ],
)
def test_virgo_conditional_sign_bonus_and_malefic_terms_use_selected_lilly_table(
    longitude, term, bonus
):
    r = fortune(longitude=longitude)
    assert r["bound_lord"] == term
    assert by_code(r, "P04")["contribution"] == bonus
    if term == "Saturn":
        assert by_code(r, "N06")["contribution"] == -2


def test_aries_zero_row_is_preserved_and_not_treated_as_missing():
    r = fortune(longitude=10)
    assert by_code(r, "Z01")["satisfied"] is True
    assert by_code(r, "Z01")["contribution"] == 0
    assert len(r["rows"]) == r["row_count"] == 28


def test_cancellation_below_circle_boundary_keeps_nested_coordinate_inside_same_interval():
    states = {"Sun": {"longitude": 5e-324}, "Moon": {"longitude": 0.0}}
    r = evaluate_fortune(0.0, states, {}, cusps=list(range(0, 360, 30)))
    assert Fraction(r["exact_longitude"]) == 360 - Fraction(5e-324)
    assert r["longitude"] == r["house_assignment"]["longitude"] < 360
    assert r["house_assignment"]["geometric_house"] == 12
    assert r["house_assignment"]["assigned_house"] == 1


def test_actual_night_whole_sign_chart_uses_physical_ascendant_and_keeps_other_lot_method_separate():
    subject = build_native_subject(
        name="night formula control",
        local_datetime=datetime(2024, 6, 1, 2, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
        longitude=116.4,
        latitude=39.9,
        timezone_name="Asia/Shanghai",
        house_system="W",
    )
    assert subject.is_diurnal is False
    assert subject.ascendant.abs_pos != subject.first_house.abs_pos
    states = {
        p: {"longitude": getattr(subject, p.lower()).abs_pos} for p in ["Sun", "Moon"]
    }
    r = evaluate_fortune(subject.ascendant.abs_pos, states, {})
    a, s, m = map(
        Fraction, [subject.ascendant.abs_pos, subject.sun.abs_pos, subject.moon.abs_pos]
    )
    assert Fraction(r["exact_longitude"]) == (a + m - s) % 360
    assert Fraction(r["exact_longitude"]) != (a + s - m) % 360
    assert r["formula"]["ascendant"] == subject.ascendant.abs_pos


@pytest.mark.parametrize(
    "star,code,points,orb",
    [("Regulus", "P14", 6, 6), ("Spica", "P15", 5, 5), ("Algol", "N10", -4, 5)],
)
def test_declared_star_range_retains_exact_boundary_and_distinct_fortune_weight(
    star, code, points, orb
):
    states, data = inputs()
    asc = Fraction(75) + states["Sun"]["longitude"] - states["Moon"]["longitude"]
    data["star_longitudes"][star] = 75.0 + orb
    r = evaluate_fortune(asc, states, data)
    assert by_code(r, code)["contribution"] == points
    data["star_longitudes"][star] = math.nextafter(75.0 + orb, math.inf)
    assert by_code(evaluate_fortune(asc, states, data), code)["satisfied"] is False


def test_grouped_aspects_count_once_and_fortune_has_no_self_aspect_or_fake_motion():
    states, data = inputs()
    states["Jupiter"]["longitude"] = states["Venus"]["longitude"] = Fraction(80)
    lon = 80 + states["Sun"]["longitude"] - states["Moon"]["longitude"]
    r = evaluate_fortune(lon, states, data)
    assert by_code(r, "P05")["contribution"] == 5
    states["Jupiter"]["longitude"] += Fraction(1, 2)
    states["Venus"]["longitude"] += Fraction(1, 2)
    assert by_code(evaluate_fortune(lon, states, data), "P05")["satisfied"] is False
    assert all(
        "direct" not in r["condition"] and "retrograde" not in r["condition"]
        for r in r["rows"]
    )
    assert r["formula"]["reverses_at_night"] is False


def test_unknown_nodes_stars_cusps_and_core_positions_never_produce_a_complete_sum():
    states, data = inputs()
    snapshot = copy.deepcopy((states, data))
    r = evaluate_fortune(123, states, {})
    assert r["literal_table_balance"] is None
    assert {"P08", "P09", "P14", "P15", "N03", "N10"} <= set(r["unknown_rows"])
    r = evaluate_fortune(None, states, data)
    assert r["longitude"] is None and len(r["unknown_rows"]) == 28
    assert (states, data) == snapshot


def test_free_solar_condition_is_not_confused_with_unknown_or_given_sun_points():
    states, data = inputs()
    clear = fortune(longitude=300)
    assert by_code(clear, "P16")["satisfied"] is True
    assert by_code(clear, "N11")["satisfied"] is False
    missing = evaluate_fortune(100, {"Moon": states["Moon"]}, data)
    assert by_code(missing, "P16")["status"] == "unknown"
    combust = fortune(longitude=states["Sun"]["longitude"] + 1)
    assert by_code(combust, "N11")["contribution"] == -5
    assert by_code(combust, "P16")["contribution"] == 0


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_inputs_are_rejected_before_formula_or_house_classification(value):
    with pytest.raises(ValueError):
        fortune(value)
    with pytest.raises(ValueError):
        assign_cusp_virtue(value, 1, 0, 30)
