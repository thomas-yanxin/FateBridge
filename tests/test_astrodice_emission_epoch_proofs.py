"""Independent IEEE neighbors and exact inverse proof failure controls."""

import copy
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_emission_epoch import K
from scripts.verify_astrodice_emission_epoch import (
    enumerate_bits,
    infer_proof,
    neighbor,
)
from scripts.verify_astrodice_observer_clock import add, mul, rounded, sub
from tests.test_astrodice_emission_epoch import analytic_case


@pytest.mark.parametrize(
    "value,previous,following",
    [
        (1.0, Q(1) - Q(1, 2**53), Q(1) + Q(1, 2**52)),
        (-1.0, -Q(1) - Q(1, 2**52), -Q(1) + Q(1, 2**53)),
        (0.0, -Q(1, 2**1074), Q(1, 2**1074)),
    ],
)
def test_independent_bit_neighbors_match_known_binary64_boundary_spacing(
    value, previous, following
):
    assert Q(neighbor(value, False)) == previous
    assert Q(neighbor(value, True)) == following


def test_independent_enumeration_distinguishes_empty_support_from_limit():
    lo, hi = Q(1), Q(1) + Q(2, 2**52)
    status, values = enumerate_bits(lo, hi, 3)
    assert status == "complete" and list(map(Q, values)) == [lo, lo + Q(1, 2**52), hi]
    assert enumerate_bits(lo, hi, 2)[0] == "enumeration_limit"
    assert enumerate_bits(lo + Q(1, 2**54), lo + Q(3, 2**54), 8) == ("complete", [])


def proof_case(monkeypatch):
    stored = analytic_case(monkeypatch)
    epoch = Q(4680826)

    class Source:
        def __init__(self, *args):
            pass

        def state(self, t, body):
            if body == "Earth":
                return [rounded(0)] * 6
            return [
                add(rounded(1), mul(rounded(Q(1, 100)), sub(t, rounded(epoch)))),
                rounded(0),
                rounded(0),
                rounded(Q(1, 100)),
                rounded(0),
                rounded(0),
            ]

    monkeypatch.setattr("scripts.verify_astrodice_emission_epoch.Source", Source)
    monkeypatch.setattr(
        "scripts.verify_astrodice_emission_epoch.exact_position",
        lambda directory, window, t, body: (
            [Q(0)] * 3 if body == "Earth" else [1 + Q(1, 100) * (t - epoch), Q(0), Q(0)]
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
    }
    cal = {
        "status": "bracketed",
        "effective_JD": [str(epoch + K)] * 2,
        "all_six_compatible": False,
    }
    row = {
        "range_AU": "1.00000000000000",
        "astrometric_angles": ["0.000000000", "0.000000000"],
    }
    return stored, cal, row, plan


def test_independent_inverse_and_lattice_proof_matches_analytic_source(monkeypatch):
    stored, cal, row, plan = proof_case(monkeypatch)
    assert infer_proof(
        Path("."), {"window_index": 0}, row, cal, "printing_only", stored, plan
    ) == (4, 2)


@pytest.mark.parametrize(
    "mutation",
    ["drop_candidate", "Earth_center", "Earth_radius", "endpoint", "tie", "promote"],
)
def test_independent_proof_rejects_changed_inverse_or_lattice_claims(
    monkeypatch, mutation
):
    value, cal, row, plan = proof_case(monkeypatch)
    stored = copy.deepcopy(value)
    lattice = stored["lattices"]["seconds_from_J2000_binary64"]
    if mutation == "drop_candidate":
        lattice["candidates"].pop()
    elif mutation == "Earth_center":
        stored["Earth_center_AU"][0] = "1"
    elif mutation == "Earth_radius":
        stored["Earth_radius_AU"] = "-1"
    elif mutation == "endpoint":
        stored["inverse"]["boundary_brackets_JD"][0][0] = "0"
    elif mutation == "tie":
        lattice["candidates"][0]["rounding_cell"]["lower_included"] = False
    else:
        lattice["candidates"][0]["physical_or_internal_algorithm_certified"] = True
    with pytest.raises(ValueError):
        infer_proof(
            Path("."), {"window_index": 0}, row, cal, "printing_only", stored, plan
        )
