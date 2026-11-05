"""Exact angular bounds for diagnostics must not depend on ray length."""

import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from scripts.astrodice.diagnose_astrodice_de441_clock import (
    atan_bounds,
    diagnose,
    pi_bounds,
    ra_shift_arcsec,
)


def test_machin_bounds_contain_the_known_fifty_digit_pi_value():
    low, high = pi_bounds()
    known = F("3.14159265358979323846264338327950288419716939937510")
    assert low < known < high
    assert high - low < F(1, 10**44)


def test_arctangent_quadrant_sign_and_zero_are_preserved():
    low, high = atan_bounds(F(1, 3), 8)
    assert atan_bounds(F(-1, 3), 8) == (-high, -low)
    assert atan_bounds(0, 2) == (0, 0)
    pl, ph = pi_bounds()
    a, b = atan_bounds(F(1, 2), 32), atan_bounds(F(1, 3), 32)
    # atan(1/2)+atan(1/3)=pi/4; this also checks the remainder signs.
    assert a[0] + b[0] < pl / 4 < a[1] + b[1]
    assert a[0] + b[0] < ph / 4 < a[1] + b[1]


def test_geometric_ra_change_is_invariant_to_independent_positive_ray_scales():
    original, shifted = [F(2), F(1)], [F(2) + F(1, 10**7), F(1)]
    expected = ra_shift_arcsec(original, shifted)
    assert expected[1] < 0
    assert (
        ra_shift_arcsec([v * 37 for v in original], [v / 19 for v in shifted])
        == expected
    )
    assert ra_shift_arcsec(original, [v * 11 for v in original]) == (0, 0)
    reverse = ra_shift_arcsec(shifted, original)
    assert reverse == (-expected[1], -expected[0])


def test_an_opposite_ray_cannot_be_treated_as_a_tiny_local_ra_change():
    with pytest.raises(ValueError, match="local branch"):
        ra_shift_arcsec([F(2), F(1)], [F(-2), F(-1)])


def test_frozen_clock_proxies_preserve_all_original_witnesses_and_no_new_grade():
    fixtures = Path(__file__).parents[1] / "data/astrodice/reference_sets"
    clock = fixtures / "fixture-de441-clock-v1"
    result = diagnose(
        fixtures / "fixture-de441-records-v1",
        fixtures / "fixture-grid5-reference-v2",
    )
    assert (
        result["records"]
        == json.loads((clock / "clock-diagnostic-first.json").read_text())["records"]
    )
    assert len(result["records"]) == 5
    assert not result["actual_horizons_clock_identified"]
    assert not result["apparent_ra_sensitivity_proved"]
    assert not result["printing_constraints_or_grades_changed"]
    assert result["new_holdout_conditions"] == 0
    assert result["original_five_incompatibility_proofs_retained"]
