"""Analytic moving-observer controls and exact binary64 tie decisions."""

import math
from fractions import Fraction as Q

import pytest

from scripts.astrodice_lunar_split import K, apparent
from scripts.verify_astrodice_lunar_split import binary64_nearest, model

CENTER = Q(2451545)
V, W, RADIUS = Q(1, 100), Q(1, 10000), Q(1, 400)


class DirectLinearSource:
    def group(self, t, group):
        assert group == 9
        zero = t * 0
        return [zero + RADIUS, (t - CENTER) * W, zero, zero, zero + W, zero]

    def state(self, t, body):
        zero = t * 0
        earth = [(t - CENTER) * V, zero, zero, zero + V, zero, zero]
        if body == "Earth":
            return earth
        assert body == "Moon"
        return [a + b for a, b in zip(earth, self.group(t, 9))]


class PowerLinearSource:
    def group_derivatives(self, t, group):
        assert group == 9
        return [
            t.cast(RADIUS),
            W * (t - CENTER),
            t.cast(0),
            t.cast(0),
            t.cast(W),
            t.cast(0),
        ]

    def state_derivatives(self, t, body):
        earth = [
            V * (t - CENTER),
            t.cast(0),
            t.cast(0),
            t.cast(V),
            t.cast(0),
            t.cast(0),
        ]
        if body == "Earth":
            return earth
        assert body == "Moon"
        return [a + b for a, b in zip(earth, self.group_derivatives(t, 9))]


def expected_derivative():
    # Independent differential of the textbook boost along x, using the
    # explicit linear lunar ray and a constant geometric delay at the centre.
    k, v, w, r = map(float, (K, V, W, RADIUS))
    x, y = r - v * k * r, -w * k * r
    length = math.hypot(x, y)
    nx, ny = x / length, y / length
    dx, dy = -nx * ny * w / length, (1 - ny * ny) * w / length
    beta = v * k
    gamma = math.sqrt(1 - beta * beta)
    d = 1 + beta * nx
    return [
        gamma * gamma * dx / (d * d),
        gamma * (dy * d - ny * beta * dx) / (d * d),
        0,
    ]


def test_complete_lunar_chain_and_aberration_match_an_analytic_boost():
    result = apparent(DirectLinearSource(), CENTER, derivative=True)
    independent = model(PowerLinearSource(), CENTER, "continuous_split", True)
    expected = expected_derivative()
    for axis, pair in enumerate(result["direction_derivative_per_source_day"]):
        a, b = map(Q, pair)
        assert float((a + b) / 2) == pytest.approx(expected[axis], abs=1e-13)
        lo, hi = independent["direction_derivative_per_source_day"][axis]
        assert a <= lo <= hi <= b
    assert (
        Q(result["emission_clock_derivative"][0])
        <= 1
        <= Q(result["emission_clock_derivative"][1])
    )


@pytest.mark.parametrize(
    "profile", ["rounded_emitter_only", "rounded_reception_and_emitter"]
)
def test_quantized_clock_profiles_never_gain_a_smooth_derivative(profile):
    with pytest.raises(ValueError):
        apparent(DirectLinearSource(), CENTER, profile, True)
    with pytest.raises(ValueError):
        model(PowerLinearSource(), CENTER, profile, True)


@pytest.mark.parametrize(
    "value", [Q(1721426), Q(5373482), Q(5373482) + Q(1, 86400000000)]
)
def test_independent_integer_rounding_agrees_with_binary64(value):
    assert binary64_nearest(value) == Q(float(value))


def test_binary64_midpoint_ties_choose_the_even_significand():
    h = Q(1, 2**30)
    base = Q(5373482)
    assert binary64_nearest(base + h / 2) == base
    assert binary64_nearest(base + 3 * h / 2) == base + 2 * h


def test_point_only_rounded_profile_does_not_report_a_rate():
    a = apparent(DirectLinearSource(), CENTER + Q(1, 12345), "rounded_emitter_only")
    b = model(PowerLinearSource(), CENTER + Q(1, 12345), "rounded_emitter_only")
    assert a["direction_derivative_per_source_day"] is None
    assert b["direction_derivative_per_source_day"] is None
