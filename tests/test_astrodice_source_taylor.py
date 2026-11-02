"""Manufactured analytic functions verify coefficient order and factorials."""

import math
from fractions import Fraction as Q

import pytest

from scripts.astrodice_clock_interval import I
from scripts.astrodice_source_slope_bounds import pi_bounds
from scripts.astrodice_source_taylor import J, angular_coefficients


def test_polynomial_jet_coefficients_are_normalized_not_raw_derivatives():
    t = J(0, 1)
    value = J(1)
    for _ in range(9):
        value = value * (1 + t)
    assert value.degree == 7
    for k, c in enumerate(value.c):
        assert c.contains(math.comb(9, k))
    derivative = value.derivative()
    assert derivative.degree == 6
    for k, c in enumerate(derivative.c):
        assert c.contains((k + 1) * math.comb(9, k + 1))


@pytest.mark.parametrize("operation", ["sqrt", "reciprocal"])
def test_seventh_order_elementary_coefficients_match_known_series(operation):
    t = J(0, 1)
    value = (1 + t).sqrt() if operation == "sqrt" else 1 / (1 + t)
    expected = Q(1)
    for k, c in enumerate(value.c):
        if k:
            expected = (
                expected * (Q(1, 2) - k + 1) / k
                if operation == "sqrt"
                else Q((-1) ** k)
            )
        assert c.contains(expected)


def test_coefficients_enclose_known_derivatives_over_a_whole_base_interval():
    value = 1 / (1 + J(I(Q(-1, 8), Q(1, 8)), 1))
    for k, c in enumerate(value.c):
        for point in [Q(-1, 8), Q(), Q(1, 8)]:
            assert c.contains(Q((-1) ** k) / (1 + point) ** (k + 1))


def test_cartesian_angular_coefficients_reproduce_arctangent_through_order_seven():
    alpha, delta = angular_coefficients([J(1), J(0, 1), J(0)])
    low, high = pi_bounds()
    as_low, as_high = Q(648000) / high, Q(648000) / low
    for k, c in enumerate(alpha, 1):
        if k % 2 == 0:
            assert c.lo == c.hi == 0
        else:
            sign = (-1) ** ((k - 1) // 2)
            for expected in [sign * as_low / k, sign * as_high / k]:
                assert c.contains(expected)
    assert all(c.lo == c.hi == 0 for c in delta)


def test_singular_support_and_unknown_high_order_are_rejected():
    with pytest.raises(ValueError):
        1 / J(I(-1, 1))
    with pytest.raises(ValueError):
        J(I(-1, 1)).sqrt()
    with pytest.raises(ValueError):
        J(1, degree=0).derivative()
    with pytest.raises(ValueError):
        angular_coefficients([J(0), J(0), J(1)])
