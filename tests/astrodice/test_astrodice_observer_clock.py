"""Analytic motion checks light-time enclosures before querying the holdout."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice.astrodice_clock_interval import A, I
from scripts.astrodice.astrodice_observer_clock import (
    LIGHT_DAYS_PER_AU,
    emission_budget,
    forward,
    observed_direction,
    trig_point,
)

PLAN = {
    "light_time_initial_interval_days": ["0", "1/32"],
    "fixed_point_iterations": 24,
    "emission_error_full_binary64_ET_ULPs": 1,
}


class LinearReader:
    def __init__(self, distance=Q(1), velocity=Q(1, 100)):
        self.distance, self.velocity = distance, velocity

    def state(self, t, body):
        if body == "Earth":
            return [A() for _ in range(6)]
        return [self.distance + self.velocity * t, A(), A(), A(self.velocity), A(), A()]


def contains(bounds, value):
    return Q(bounds[0]) <= value <= Q(bounds[1])


def test_converged_newtonian_family_contains_exact_linear_motion_solution():
    result = forward(LinearReader(), I(), "converged_Newtonian_24", PLAN)
    exact_delay = Q(1) / (1 / LIGHT_DAYS_PER_AU + Q(1, 100))
    assert contains(result["light_time_minutes"], exact_delay * 1440)
    assert contains(result["range_AU"], exact_delay / LIGHT_DAYS_PER_AU)
    assert len(result["history"]) == 24
    for step in result["history"]:
        a, b = map(Q, step["input_days"])
        c, d = map(Q, step["next_days"])
        assert a <= c <= d <= b


def test_two_linearized_delay_model_does_not_silently_become_converged():
    result = forward(LinearReader(), I(), "legacy_two_linearized_delays", PLAN)
    expected = LIGHT_DAYS_PER_AU * (1 - Q(1, 100) * LIGHT_DAYS_PER_AU)
    assert contains(result["light_time_minutes"], expected * 1440)
    exact_delay = Q(1) / (1 / LIGHT_DAYS_PER_AU + Q(1, 100))
    assert not contains(result["light_time_minutes"], exact_delay * 1440)
    assert len(result["history"]) == 2


@pytest.mark.parametrize(
    "reader", [LinearReader(velocity=2 / LIGHT_DAYS_PER_AU), LinearReader(distance=100)]
)
def test_invalid_root_support_or_contraction_is_rejected_without_widening(reader):
    with pytest.raises(ValueError):
        forward(reader, I(), "converged_Newtonian_24", PLAN)


def test_emission_allowance_is_an_explicit_ET_representation_hypothesis():
    t = I(Q(4680826))
    epsilon = emission_budget(t, Q(1, 32), 1)
    assert epsilon > 0
    assert emission_budget(t, Q(1, 32), 0) == 0
    with pytest.raises(ValueError):
        emission_budget(t, Q(1, 32), 2)


@pytest.mark.parametrize(
    "angle,sine,cosine",
    [(0, 0, 1), (90, 1, 0), (180, 0, -1), (270, -1, 0), (-90, -1, 0)],
)
def test_rigorous_point_trig_encloses_known_quadrant_values(angle, sine, cosine):
    sn, cs = trig_point(Q(angle), 80)
    assert sn.contains(sine) and cs.contains(cosine)


def test_angular_printing_noise_uses_a_lipschitz_radius_after_point_evaluation():
    direction = observed_direction(["0.000000000", "0.000000000"], 0, 80)
    assert direction[0].contains(1)
    assert direction[1].contains(0) and direction[2].contains(0)
    assert direction[1].absolute_upper() < Q(1, 10**9)
    with pytest.raises(ValueError):
        observed_direction(["360", "0"], 0, 80)
