"""Regression and independent algebra for the second specialized-chart audit."""

import json
import math
import random
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import _sector13_for_longitude
from fatebridge.core.astro.midpoints import midpoint_geometry
from fatebridge.core.astro.parts import _build_planet_record
from fatebridge.core.astro.seven_planets import seven_planet_view
from fatebridge.services.astrology import calculate_germany_chart_analysis
from tests.fixtures.surface_payloads import astro_payload

EXAMPLE = json.loads(
    (Path(__file__).parents[1] / "fixtures/uranian-udo-1996-symbolic.json").read_text()
)


@pytest.mark.parametrize("case", EXAMPLE["cases"], ids=lambda case: case["id"])
def test_original_symbolic_example_with_separately_labelled_numeric_witness(case):
    result = midpoint_geometry(case["positions"], orb_degrees=0.0)
    contacts = result["dials"][str(case["midpoint_period"])]["four_factor_contacts"]
    row = next(row for row in contacts if row["equation"] == case["midpoint_equation"])
    sensitive = row["sensitive_point"]
    assert sensitive["longitude"] == case["expected_point"]
    assert sensitive["period_degrees"] == case["expected_sensitive_period"]
    assert sensitive["occupancy"] == case["expected_occupancy"]
    assert sensitive["orb"] == 0
    assert ("source_interpretation" in row) == case["source_reading_allowed"]
    if case["source_reading_allowed"]:
        reading = row["source_interpretation"]
        assert reading["source_id"] == "udo_rudolph_1996_abc_excerpt"
        assert reading["source_section"] == "printed p.14"
        assert reading["claim_type"] == "source_attributed_symbolic_interpretation"
        assert (
            reading["sensitive_point_longitude"] == reading["occupant_longitude"] == 25
        )


def test_sum_equivalence_doubles_both_period_and_orb_in_every_returned_contact():
    rng = random.Random(714019)
    values = {str(index): rng.uniform(-400, 700) for index in range(10)}
    result = midpoint_geometry(values)
    checked = 0
    for period, dial in result["dials"].items():
        p = int(period)
        for row in dial["four_factor_contacts"]:
            checked += 1
            a, b, c, d = [values[row[key]] for key in ("id_a", "id_b", "id_c", "id_d")]
            # Independent doubled-angle residual, without production helpers.
            phi = math.pi * (a + b - c - d) / p
            expected = abs(math.atan2(math.sin(phi), math.cos(phi))) * p / math.pi
            sensitive = row["sensitive_point"]
            assert sensitive["period_degrees"] == p * 2
            assert sensitive["maximum_orb_degrees"] == 2
            assert sensitive["orb"] == pytest.approx(expected, abs=2e-12)
            assert sensitive["orb"] == pytest.approx(2 * row["orb"], abs=1e-14)
            # Ordinary float summation can cancel large terms before modulo.
            # This exact affine reference preserves the supplied IEEE inputs.
            expected_point = float((Fraction(a) + Fraction(b) - Fraction(c)) % 360)
            assert sensitive["longitude"] == expected_point
    assert checked > 0


@pytest.mark.parametrize(
    "period,occupant,expected",
    [(90, 26.9999, True), (90, 27.0001, False), (45, 115.0, False)],
)
def test_original_reading_requires_actual_direct_occupancy(period, occupant, expected):
    result = midpoint_geometry(
        {"Mars": 10.0, "Jupiter": 30.0, "Zeus": 15.0, "Midheaven": occupant}
    )
    rows = [
        r
        for r in result["dials"][str(period)]["four_factor_contacts"]
        if r["equation"] == "Mars/Jupiter=Zeus/Midheaven"
    ]
    assert any("source_interpretation" in row for row in rows) == expected


def test_short_arc_is_selected_before_rounding_at_the_antipodal_discontinuity():
    result = seven_planet_view(
        [{"id": "Sun", "longitude": 0.0}, {"id": "Moon", "longitude": 180.00001}]
    )
    midpoint = result["midpoints"][0]
    # Hand calculation: shorter arc crosses 360 and its halfway point is 270°.
    assert midpoint["longitude"] == pytest.approx(270.000005, abs=1e-12)
    assert midpoint["antipodal_inputs"] is False
    assert midpoint["computed_from_unrounded"] is True


def test_exact_antipodal_seven_planet_view_reports_both_endpoints_without_order_bias():
    factors = [{"id": "Sun", "longitude": 0.0}, {"id": "Moon", "longitude": 180.0}]
    for sequence in (factors, factors[::-1]):
        row = seven_planet_view(sequence)["midpoints"][0]
        assert row["longitude"] == 90
        assert row["opposite_longitude"] == 270
        assert row["antipodal_inputs"] is True


def test_legacy_contact_cannot_cross_orb_boundary_due_to_display_rounding():
    factors = [
        {"id": "Sun", "longitude": 0.0},
        {"id": "Moon", "longitude": 20.0},
        {"id": "Mars", "longitude": 12.00001},
    ]
    contacts = seven_planet_view(factors)["midpoint_aspects"]
    assert not any(
        row["planet"] == "Mars" and row["midpoint"] == "Sun/Moon" for row in contacts
    )


def test_existing_planet_major_contact_order_is_preserved_after_precision_fix():
    result = seven_planet_view(
        [
            {"id": "Sun", "longitude": 0.0},
            {"id": "Moon", "longitude": 0.5},
            {"id": "Mars", "longitude": 1.0},
        ]
    )
    expected = [
        (planet, pair)
        for planet in ("Sun", "Moon", "Mars")
        for pair in ("Sun/Moon", "Sun/Mars", "Moon/Mars")
    ]
    assert [
        (row["planet"], row["midpoint"]) for row in result["midpoint_aspects"]
    ] == expected


def test_sector_evidence_reconstructs_decision_even_when_client_rounding_crosses_cusp():
    edge = float(Fraction(360, 13))
    value = math.nextafter(edge, math.inf)
    record = _build_planet_record(
        "Sun", value, 0.0, 0.0, "whole_sign", include_sector13=True
    )
    assert record["sector13"] == 2
    # The shared Western record now preserves precision too. A client can still
    # round it to the historical four-decimal display, losing the edge side.
    assert _sector13_for_longitude(round(record["longitude"], 4), 0.0) == 1
    transported = json.loads(json.dumps(record))["sector13_evidence"]
    assert (
        _sector13_for_longitude(
            transported["longitude_unrounded"], transported["ascendant_unrounded"]
        )
        == record["sector13"]
    )
    assert transported["birth_time_uncertainty"] == "not_assessed"


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize("year", [2035, 2100])
def test_future_native_layer_uses_same_explicit_time_policy_as_its_base_chart(year):
    result = calculate_germany_chart_analysis(**{**astro_payload(), "birth_year": year})
    profile = result["midpoint_analysis"]["profile"]
    base = result["base_chart"]["chart_profile"]
    assert profile["julian_day_tt"] == base["julian_day_tt"]
    assert profile["julian_day_ut1"] == base["julian_day_ut1"]
    assert profile["future_leap_seconds_assumed_unchanged"] is True
    # Frozen post-2017 offset, not a measured future UTC history or UT1.
    assert (
        profile["julian_day_tt"] - profile["julian_day_utc"]
    ) * 86400 == pytest.approx(69.184, abs=5e-5)


def test_same_source_reading_on_two_dials_keeps_one_claim_identity():
    geometry = midpoint_geometry(
        {"Mars": 10.0, "Jupiter": 30.0, "Zeus": 15.0, "Midheaven": 25.0},
        orb_degrees=0.0,
    )
    claims = [
        row["source_interpretation"]
        for dial in geometry["dials"].values()
        for row in dial["four_factor_contacts"]
        if "source_interpretation" in row
    ]
    assert len(claims) == 2
    assert len({claim["claim_id"] for claim in claims}) == 1
