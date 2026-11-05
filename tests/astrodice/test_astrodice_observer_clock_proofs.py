"""Independent proof steps reject understated boxes and missing iterations."""

import copy
from fractions import Fraction as Q

import pytest

from scripts.astrodice.astrodice_clock_interval import I
from scripts.astrodice.astrodice_observer_clock import forward
from scripts.astrodice.verify_astrodice_observer_clock import (
    add,
    cover,
    divide,
    length,
    model_proof,
    mul,
    root,
    rounded,
)
from tests.astrodice.test_astrodice_observer_clock import PLAN, LinearReader


class LinearSource:
    def state(self, epoch, body):
        if body == "Earth":
            return [rounded(0) for _ in range(6)]
        return [
            add(rounded(1), mul(rounded(Q(1, 100)), epoch)),
            rounded(0),
            rounded(0),
            rounded(Q(1, 100)),
            rounded(0),
            rounded(0),
        ]


@pytest.mark.parametrize(
    "model",
    [
        "legacy_two_linearized_delays",
        "converged_Newtonian_24",
        "converged_Newtonian_24_emission_ET_ULP_hypothesis",
    ],
)
def test_independent_exact_proof_replays_analytic_motion_enclosures(model):
    stored = forward(LinearReader(), I(), model, PLAN)
    steps, checks = model_proof(LinearSource(), rounded(0), model, stored, PLAN)
    assert steps == (2 if model.startswith("legacy") else 24)
    assert checks == 5


@pytest.mark.parametrize(
    "mutation",
    ["skip", "understate_image", "understate_range", "emission", "promotion"],
)
def test_independent_proof_rejects_fabricated_source_claims(mutation):
    model = "converged_Newtonian_24_emission_ET_ULP_hypothesis"
    stored = copy.deepcopy(forward(LinearReader(), I(), model, PLAN))
    if mutation == "skip":
        stored["history"].pop()
    elif mutation == "understate_image":
        stored["history"][0]["image_days"] = ["0", "0"]
    elif mutation == "understate_range":
        stored["range_AU"] = ["0", "0"]
    elif mutation == "emission":
        stored["emission_argument_radius_days"] = "0"
    else:
        stored["internal_iteration_algorithm_certified"] = True
    with pytest.raises(ValueError):
        model_proof(LinearSource(), rounded(0), model, stored, PLAN)


def test_separate_box_arithmetic_keeps_reversed_support_and_zero_denominators_invalid():
    a, b = root(rounded(2))
    assert a * a <= 2 <= b * b
    assert length([rounded(3), rounded(4)]) == rounded(5)
    with pytest.raises(ValueError):
        rounded(2, 1)
    with pytest.raises(ValueError):
        divide(rounded(1), rounded(-1, 1))
    with pytest.raises(ValueError):
        cover(rounded(-1, 1), ["0", "0"])
