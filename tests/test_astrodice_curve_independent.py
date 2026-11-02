"""Independent blossom and metric algorithms against exact analytic controls."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice_clock_interval import I
from scripts.astrodice_curve_math import bernstein, leaves, metrics
from scripts.verify_astrodice_compressed_curve import (
    B,
    binary64,
    cover,
    leaf_hulls,
    swe_chebyshev,
    vector_metrics,
)


@pytest.mark.parametrize(
    "polynomial",
    [
        [Q(7)],
        [Q(), Q(1)],
        [Q(1), Q(-2), Q(1)],
        [Q(3, 7), Q(-5, 11), Q(7, 13), Q(-9, 17)],
    ],
)
@pytest.mark.parametrize("depth", [1, 3, 5])
def test_integer_blossom_equals_exact_subdivision_control_hulls(polynomial, depth):
    coefficients = bernstein(polynomial)
    expected = [(min(c), max(c)) for c in leaves(coefficients, depth)]
    assert leaf_hulls(tuple(coefficients), depth) == expected


def test_manual_binary64_ties_to_even():
    assert binary64(1 + Q(1, 2**53)) == 1
    assert binary64(1 + Q(3, 2**53)) == 1 + Q(1, 2**51)
    assert binary64(Q(1, 2**30)) == Q(1, 2**30)


def test_source_polynomial_normalizer_is_defined_at_header_grid_limits():
    x = 1 + Q(1, 2**42)
    value, velocity = swe_chebyshev([Q(2), Q(), Q(), Q(1)], x)
    assert value == 2 + 4 * x**3 - 3 * x
    assert velocity == 12 * x * x - 3


def test_independent_higher_precision_metric_is_contained():
    fields = {
        "q": [Q(1), Q(1, 3), Q(1, 5)],
        "w": [Q(-1, 17), Q(1, 19), Q(2, 23)],
        "e": [Q(1, 10**8), Q(-1, 10**9), Q(2, 10**10)],
        "f": [Q(-1, 10**8), Q(2, 10**9), Q(3, 10**10)],
    }
    scales = []
    expected = metrics(
        **{k: list(map(I, v)) for k, v in fields.items()}, audit_scales=scales
    )
    actual = vector_metrics(
        **{k: list(map(B, v)) for k, v in fields.items()}, scales=scales
    )
    cover(actual, [list(map(str, x.bounds())) for x in expected])
    with pytest.raises(ValueError):
        cover(actual, [["0", "0"], ["0", "0"]])


def test_independent_metric_rejects_nonpositive_scaling():
    with pytest.raises(ValueError, match="positive"):
        vector_metrics(
            [B(1), B(), B()], [B()] * 3, [B()] * 3, [B()] * 3, ["1", "1", "1", "0"]
        )
