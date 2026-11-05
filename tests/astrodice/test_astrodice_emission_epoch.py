"""Analytic inversions, exact lattice boundaries and unqualified outcomes."""

import math
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice.astrodice_clock_interval import A
from scripts.astrodice.astrodice_emission_epoch import (
    K,
    cell_relations,
    coordinate,
    epoch_from_coordinate,
    infer,
    lattice_points,
    rounding_cell,
)


@pytest.mark.parametrize("center", [1.0, -1.0, 2e11, -2e11, 0.0])
def test_lattice_includes_exact_endpoints_in_order(center):
    a, b = math.nextafter(center, -math.inf), math.nextafter(center, math.inf)
    result = lattice_points(Q(a), Q(b), 10)
    assert result["status"] == "complete"
    assert list(map(Q, result["points"])) == [Q(a), Q(center), Q(b)]


def test_empty_lattice_and_enumeration_limit_are_distinct():
    a, b = Q(1.0), Q(math.nextafter(1.0, math.inf))
    assert lattice_points(a + (b - a) / 3, b - (b - a) / 3, 8) == {
        "status": "complete",
        "points": [],
    }
    result = lattice_points(a, a + 1, 3)
    assert result["status"] == "enumeration_limit" and len(result["points"]) == 3


@pytest.mark.parametrize(
    "value,even", [(1.0, True), (math.nextafter(1.0, math.inf), False), (-1.0, True)]
)
def test_nearest_cells_keep_exact_even_ties(value, even):
    cell = rounding_cell(value)
    a, b = map(Q, cell["bounds"])
    assert cell_relations((a, a), cell) == (even, even)
    assert cell_relations((b, b), cell) == (even, even)
    assert cell_relations((Q(value), Q(value)), cell) == (True, True)
    assert cell_relations((a - 1, a - 1), cell) == (False, False)


@pytest.mark.parametrize(
    "model", ["absolute_JD_binary64", "seconds_from_J2000_binary64"]
)
def test_coordinate_conversion_keeps_the_exact_rational_epoch(model):
    epoch = Q(4680826) + Q(123457, 86400000000)
    assert epoch_from_coordinate(coordinate(epoch, model), model) == epoch
    with pytest.raises(ValueError):
        coordinate(epoch, "other")
    with pytest.raises(ValueError):
        epoch_from_coordinate(epoch, "other")


def analytic_case(monkeypatch, velocity=Q(1, 100), printed="1.00000000000000"):
    epoch = Q(4680826)

    class Source:
        def __init__(self, *args):
            pass

        def state(self, t, body):
            if body == "Earth":
                return [A() for _ in range(6)]
            return [1 + velocity * (t - epoch), A(), A(), A(velocity), A(), A()]

    monkeypatch.setattr("scripts.astrodice.astrodice_emission_epoch.Reader", Source)
    monkeypatch.setattr(
        "scripts.astrodice.astrodice_emission_epoch.earth_center",
        lambda *args: [Q(0)] * 3,
    )
    monkeypatch.setattr(
        "scripts.astrodice.astrodice_emission_epoch.scalar_source",
        lambda source, window, nominal, axis: (
            (lambda t: 1 + velocity * (t - epoch)) if axis == 0 else (lambda t: Q(0))
        ),
    )
    plan = {
        "numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}},
        "emission_search_radius_seconds": "1/1000",
        "minimum_absolute_emission_radial_derivative_AU_per_day": "1/1000000",
        "emission_inverse_bisection_iterations": 48,
        "lattice_coordinate_models": [
            "absolute_JD_binary64",
            "seconds_from_J2000_binary64",
        ],
        "maximum_lattice_points_per_model": 32,
        "interval_trig_terms": 80,
    }
    tr = epoch + K
    calibration = {
        "status": "bracketed",
        "effective_JD": [str(tr), str(tr)],
        "all_six_compatible": False,
    }
    return infer(
        Path("."),
        {"window_index": 0},
        {"range_AU": printed, "astrometric_angles": ["0.000000000", "0.000000000"]},
        calibration,
        "printing_only",
        plan,
    )


def test_analytic_range_inversion_retains_both_grids_and_unqualified_calibration(
    monkeypatch,
):
    result = analytic_case(monkeypatch)
    assert result["status"] == "inferred"
    lo, hi = map(Q, result["effective_emission_JD"])
    assert lo <= 4680826 <= hi
    assert result["continuous_necessary_overlap"]
    assert result["calibration_all_six_not_refuted"] is False
    for lattice in result["lattices"].values():
        assert lattice["enumeration_status"] == "complete"
        assert lattice["points_in_effective_interval"] == 1
        assert lattice["unique_not_refuted"] and not lattice["conditional_refuted"]


def test_unconditioned_and_unbracketed_cases_are_never_silently_widened(monkeypatch):
    assert analytic_case(monkeypatch, velocity=Q(0))["status"] == "conditioning_unknown"
    assert (
        analytic_case(monkeypatch, printed="2.00000000000000")["status"]
        == "source_range_unbracketed"
    )
