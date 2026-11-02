"""Analytic adversarial geometry; synthetic cases are not ephemeris holdouts."""

from decimal import Decimal, localcontext
from fractions import Fraction as Q

import pytest

from scripts.astrodice_nonuniform_reference import fit, interpolate, polynomial, system
from scripts.verify_astrodice_nonuniform_reference import (
    independent_system,
    linear_solve,
)


def test_arbitrary_rational_nodes_match_separate_moment_solution():
    nodes = [Q(-3, 2), Q(-1, 7), Q(2, 3), Q(7, 5), Q(19, 4), Q(83, 11)]
    coefficients = [Q(2, 7), Q(-11, 3), Q(5), Q(19, 13), Q(-1, 9), Q(8, 11)]
    values = [polynomial(coefficients, x) for x in nodes]
    assert interpolate(nodes, values) == coefficients
    assert (
        linear_solve([[x**k for k in range(6)] for x in nodes], values) == coefficients
    )
    with pytest.raises(ValueError, match="duplicate"):
        interpolate([Q(1), Q(1)], [Q(), Q()])


def fixture():
    angles = {}
    epochs = {}
    for offset in range(-1440, 1441, 5):
        # Deliberately asymmetric 1/64-second timing error and a zero center.
        t = Q(offset) + (Q(1, 64) if offset > 0 else Q(-1, 32) if offset < 0 else 0)
        epochs[offset] = Q(123456789) + t
        x = t / 1440
        ra = Q(40) + Q(1, 1000) * x * x + Q(1, 100000) * x**5
        dec = Q(16) + Q(1, 1000) * x + Q(1, 10000) * x**3
        with localcontext() as c:
            c.prec = 90
            angles[offset] = [
                format(Decimal(v.numerator) / Decimal(v.denominator), ".32f")
                for v in (ra, dec)
            ]
    return angles, epochs


def test_full_population_and_baseline_independently_reconstruct():
    angles, epochs = fixture()
    a, b, base, scale = system(angles, epochs, 1440, 5, 0)
    aa, bb, baseline, other = independent_system(angles, epochs, 1440, 5, 0)
    assert len(a) == len(b) == 1154
    assert [[r[1], r[0], *r[2:]] for r in a] == aa
    assert b == bb and base == baseline and scale == other
    assert abs(base[1]) < Q("1e-25")
    # The assumed uniform-node odd part would contain spurious quadratic terms.
    left = Q(angles[5][0])
    right = Q(angles[-5][0])
    assert abs((left - right) / 10) > Q("1e-12")


def test_missing_or_duplicate_time_nodes_are_not_dropped_to_fit():
    angles, epochs = fixture()
    angles.pop(5)
    with pytest.raises(ValueError, match="population"):
        system(angles, epochs, 1440, 5, 0)
    angles, epochs = fixture()
    epochs[5] = epochs[0]
    with pytest.raises(ValueError, match="Nonincreasing"):
        system(angles, epochs, 1440, 5, 0)


def test_exact_interval_contains_analytic_derivative_on_asymmetric_nodes():
    pytest.importorskip(
        "scipy",
        reason="Optional reference solver; run the frozen solver environment for this test",
    )
    angles, epochs = fixture()
    result = fit(angles, epochs, 1440, 5)
    assert result["status"] == "conditional_exact_polynomial_interval"
    for axis, expected in enumerate((Q(0), Q(1, 1000) * 3600 * 86400 / 1440)):
        a, b = map(Q, result["axes"][axis]["derivative_interval_arcsec_per_TDB_day"])
        assert a <= expected <= b and b - a < Q("1e-20")
    assert not result["physical_remainder_certified"]
