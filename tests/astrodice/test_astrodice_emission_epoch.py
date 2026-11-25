"""Analytic inversions, exact lattice boundaries and unqualified outcomes."""

import math
from fractions import Fraction as Q

import pytest

from scripts.astrodice.astrodice_emission_epoch import (
    cell_relations,
    coordinate,
    epoch_from_coordinate,
    lattice_points,
    rounding_cell,
)
from tests.unit_test.fixtures.astrodice_analytic import analytic_case


@pytest.mark.parametrize("center", [1.0, -1.0, 2e11, -2e11, 0.0])
def test_lattice_includes_exact_endpoints_in_order(center) -> None:
    a, b = math.nextafter(center, -math.inf), math.nextafter(center, math.inf)
    result = lattice_points(Q(a), Q(b), 10)
    assert result["status"] == "complete"
    assert list(map(Q, result["points"])) == [Q(a), Q(center), Q(b)]


def test_empty_lattice_and_enumeration_limit_are_distinct() -> None:
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
def test_nearest_cells_keep_exact_even_ties(value, even: bool) -> None:
    cell = rounding_cell(value)
    a, b = map(Q, cell["bounds"])
    assert cell_relations((a, a), cell) == (even, even)
    assert cell_relations((b, b), cell) == (even, even)
    assert cell_relations((Q(value), Q(value)), cell) == (True, True)
    assert cell_relations((a - 1, a - 1), cell) == (False, False)


@pytest.mark.parametrize(
    "model", ["absolute_JD_binary64", "seconds_from_J2000_binary64"]
)
def test_coordinate_conversion_keeps_the_exact_rational_epoch(model: str) -> None:
    epoch = Q(4680826) + Q(123457, 86400000000)
    assert epoch_from_coordinate(coordinate(epoch, model), model) == epoch
    with pytest.raises(ValueError):
        coordinate(epoch, "other")
    with pytest.raises(ValueError):
        epoch_from_coordinate(epoch, "other")


def test_analytic_range_inversion_retains_both_grids_and_unqualified_calibration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_unconditioned_and_unbracketed_cases_are_never_silently_widened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert analytic_case(monkeypatch, velocity=Q(0))["status"] == "conditioning_unknown"
    assert (
        analytic_case(monkeypatch, printed="2.00000000000000")["status"]
        == "source_range_unbracketed"
    )
