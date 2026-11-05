"""Independent pre-edit binary-input references, never observed accuracy."""

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.jyotish_balas import directional_strength
from fatebridge.core.jyotish_strength import degree_condition

PATH = Path(__file__).parents[1] / "fixtures/jyotish-strength-arithmetic-reference.json"
REF = json.loads(PATH.read_text())
PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]


def test_preedit_reference_is_sealed_and_retains_both_independent_evaluators():
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == "ebb7b8ecf57fd8e78ee4a29cd584eaf440f9d41762be827899f6352fbc76b29a"
    )
    assert REF["counts"] == {
        "uchcha": 3339,
        "dig_packets": 460,
        "dig_values": 3220,
    }
    assert REF["protocol"]["comparison_tolerance"] == 0
    assert REF["real_events"] == REF["independent_model_blind_reviews"] == 0


@pytest.mark.parametrize("planet", PLANETS)
def test_uchcha_matches_the_once_rounded_literal_reference(planet):
    for row in REF["uchcha_cases"]:
        if row["planet"] != planet:
            continue
        assert row["longitude"].hex() == row["longitude_hex"]
        actual = degree_condition(planet, row["longitude"])["uchcha_bala"]["value"]
        assert actual.hex() == row["expected_hex"], row


@pytest.mark.parametrize(
    "row", REF["dig_cases"], ids=lambda r: f"{r['frame']}:{r['side']}"
)
def test_dig_uses_original_cardinal_inputs_before_rounding_opposite_displays(row):
    result = directional_strength(row["raw"])
    assert result["summary"] == row["expected_virupa"]
    for planet, exact_arc in row["expected_shortest_arcs_exact"].items():
        assert result["evidence"][planet]["shortest_arc_degrees"] == float(
            Fraction(exact_arc)
        )
    assert "unrounded opposite points" in result["basis"]["numerical_policy"]
