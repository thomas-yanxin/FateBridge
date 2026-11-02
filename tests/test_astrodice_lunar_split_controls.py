"""Nonzero delay slope and observer acceleration in an analytic lunar ray."""

import math
from fractions import Fraction as Q

import pytest

from scripts.astrodice_lunar_split import K, apparent
from scripts.verify_astrodice_lunar_split import model
from tests.test_astrodice_lunar_split import (
    CENTER,
    RADIUS,
    DirectLinearSource,
    PowerLinearSource,
    V,
    W,
)


class AcceleratingDirect(DirectLinearSource):
    def __init__(self, acceleration):
        self.acceleration = acceleration

    def state(self, t, body):
        x = t - CENTER
        zero = t * 0
        a = self.acceleration
        earth = [V * x + a * x * x / 2, zero, zero, V + a * x, zero, zero]
        if body == "Earth":
            return earth
        assert body == "Moon"
        return [u + v for u, v in zip(earth, self.group(t, 9))]


class AcceleratingPower(PowerLinearSource):
    def __init__(self, acceleration):
        self.acceleration = acceleration

    def state_derivatives(self, t, body):
        u = t - CENTER
        a = self.acceleration
        earth = [
            V * u + a * u * u / 2,
            t.cast(0),
            t.cast(0),
            V + a * u,
            t.cast(0),
            t.cast(0),
        ]
        if body == "Earth":
            return earth
        assert body == "Moon"
        return [x + y for x, y in zip(earth, self.group_derivatives(t, 9))]


def analytic(offset, acceleration):
    u, a, k, v, w, r = map(float, (offset, acceleration, K, V, W, RADIUS))
    separation = math.hypot(r, w * u)
    tau = k * separation
    dtau = k * w * w * u / separation
    x = r - v * tau - a * u * tau + a * tau * tau / 2
    y = w * (u - tau)
    vx = -(v + a * u - a * tau) * dtau - a * tau
    vy = w * (1 - dtau)
    rho = math.hypot(x, y)
    nx, ny = x / rho, y / rho
    along = nx * vx + ny * vy
    dx, dy = (vx - nx * along) / rho, (vy - ny * along) / rho
    beta = (v + a * u) * k
    dbeta = a * k
    gamma = math.sqrt(1 - beta * beta)
    dgamma = -beta * dbeta / gamma
    denominator = 1 + beta * nx
    dd = dbeta * nx + beta * dx
    return [
        ((dx + dbeta) * denominator - (nx + beta) * dd) / denominator**2,
        ((dgamma * ny + gamma * dy) * denominator - gamma * ny * dd) / denominator**2,
        0,
    ], 1 - dtau


@pytest.mark.parametrize("offset", [Q(0), Q(1, 4), Q(-1, 2)])
@pytest.mark.parametrize("acceleration", [Q(0), Q(1, 1000)])
def test_full_clock_and_beta_derivatives_match_the_analytic_differential(
    offset, acceleration
):
    a = apparent(AcceleratingDirect(acceleration), CENTER + offset, derivative=True)
    b = model(
        AcceleratingPower(acceleration), CENTER + offset, "continuous_split", True
    )
    expected, clock = analytic(offset, acceleration)
    for axis, pair in enumerate(a["direction_derivative_per_source_day"]):
        lo, hi = map(Q, pair)
        x, y = b["direction_derivative_per_source_day"][axis]
        assert lo <= x <= y <= hi
        assert float((lo + hi) / 2) == pytest.approx(expected[axis], abs=1e-13)
    pair = list(map(Q, a["emission_clock_derivative"]))
    assert float(sum(pair) / 2) == pytest.approx(clock, abs=1e-15)
