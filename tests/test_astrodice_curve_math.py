"""Analytic polynomials and nonconstant direction fields test enclosure math."""

import math
from fractions import Fraction as Q

import pytest

from scripts.astrodice_clock_interval import I
from scripts.astrodice_curve_math import (
    affine,
    bernstein,
    cheb_power,
    derivative,
    evaluate,
    leaves,
    metrics,
    pi,
)


def test_native_and_jpl_constant_conventions_and_chebyshev_derivative():
    assert cheb_power([4, 0, 0, 1], True) == [2, -3, 0, 4]
    assert cheb_power([4, 0, 0, 1], False) == [4, -3, 0, 4]
    assert derivative(cheb_power([4, 0, 0, 1], True), Q(2)) == [Q(-3, 2), 0, 6]


def test_exact_affine_composition_for_nonunit_source_span():
    p = [Q(3), Q(-2), Q(5), Q(7)]
    a, b = Q(11, 13), Q(17, 19)
    composed = affine(p, a, b)
    for u in (Q(), Q(1, 7), Q(1, 2), Q(1)):
        assert evaluate(composed, u) == evaluate(p, a + b * u)


def test_bernstein_hull_and_complete_fixed_subdivision():
    controls = bernstein([Q(), Q(1), Q(-1)])
    assert controls == [0, Q(1, 2), 0]
    nodes = leaves(controls, 5)
    assert len(nodes) == 32
    for j, row in enumerate(nodes):
        for u in (Q(j, 32), Q(2 * j + 1, 64), Q(j + 1, 32)):
            assert min(row) <= u * (1 - u) <= max(row)
    assert all(a[-1] == b[0] for a, b in zip(nodes, nodes[1:]))


def test_radial_position_and_velocity_changes_have_no_direction_error():
    values = metrics(
        list(map(I, [1, 0, 0])),
        list(map(I, [2, 0, 0])),
        list(map(I, [1, 0, 0])),
        list(map(I, [7, 0, 0])),
    )
    assert all(v.contains(0) and v.absolute_upper() < Q(1, 10**60) for v in values)


def test_known_transverse_rate_change_has_exact_radian_norm():
    position, rate = metrics(
        list(map(I, [1, 0, 0])),
        list(map(I, [0, 1, 0])),
        list(map(I, [0, 0, 0])),
        [I(0), I(Q(1, 10)), I(0)],
    )
    assert position.contains(0)
    expected = Q(64800) / pi()
    lo, hi = expected.bounds()
    assert rate.bounds()[0] <= lo <= hi <= rate.bounds()[1]


def test_zero_radius_cannot_receive_an_error_certificate():
    with pytest.raises(ValueError):
        metrics([I()] * 3, [I()] * 3, [I()] * 3, [I()] * 3)


def test_nonlinear_complete_leaf_ranges_cover_direct_unit_vector_derivatives():
    fields = {
        "q": [[Q(1)], [Q(), Q(1, 8)], [Q(1, 2)]],
        "e": [[Q(1, 10**6), Q(), Q(-1, 10**6)], [Q(), Q(2, 10**6)], [Q()]],
    }
    fields["w"] = [derivative(p, Q(1)) for p in fields["q"]]
    fields["f"] = [derivative(p, Q(1)) for p in fields["e"]]
    nodes = {k: [leaves(bernstein(p), 5) for p in v] for k, v in fields.items()}

    def direction(p, v):
        r = math.hypot(*p)
        u = [x / r for x in p]
        radial = sum(x * y for x, y in zip(u, v))
        return u, [(x - y * radial) / r for x, y in zip(v, u)]

    for j in range(32):
        box = {k: [I(min(p[j]), max(p[j])) for p in v] for k, v in nodes.items()}
        bound = metrics(**box)
        for k in range(1, 4):
            u = Q(j, 32) + Q(k, 128)
            value = {
                key: [float(evaluate(p, u)) for p in v] for key, v in fields.items()
            }
            q, w, e, f = [value[k] for k in ("q", "w", "e", "f")]
            a, da = direction(q, w)
            b, db = direction(
                [x + y for x, y in zip(q, e)], [x + y for x, y in zip(w, f)]
            )
            assert bound[0].contains(math.dist(a, b) * 648000 / math.pi)
            assert bound[1].contains(math.dist(da, db) * 648000 / math.pi)
