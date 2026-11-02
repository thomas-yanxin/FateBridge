"""Exact arithmetic guards for the source clock enclosure, not accuracy scores."""

from fractions import Fraction as Q
from math import isqrt

import pytest

from scripts.astrodice_clock_interval import BITS, SCALE, A, I


@pytest.mark.parametrize(
    "bounds", [(Q(-7, 3), Q(-1, 7)), (Q(-1, 3), Q(8, 7)), (Q(1, 3), Q(8, 7))]
)
def test_all_rational_corners_are_enclosed_by_signed_arithmetic(bounds):
    a = I(*bounds)
    for other in [(Q(-8, 11), Q(-2, 11)), (Q(2, 11), Q(8, 11))]:
        b = I(*other)
        for x in bounds:
            for y in other:
                assert (a + b).contains(x + y)
                assert (a - b).contains(x - y)
                assert (a * b).contains(x * y)
                assert (a / b).contains(x / y)
        assert a.square().contains(bounds[0] ** 2)
        assert a.square().contains(bounds[1] ** 2)
        if bounds[0] <= 0 <= bounds[1]:
            assert a.square().contains(0)


@pytest.mark.parametrize("value", [Q(0), Q(1, 3), Q(2), Q(10**30, 7)])
def test_integer_square_root_proves_outward_endpoints(value):
    a = I(value)
    result = a.sqrt()
    low, high = result.bounds()
    assert low**2 <= value <= high**2
    assert result.lo == isqrt(a.lo * SCALE)
    assert (result.hi - 1) ** 2 < a.hi * SCALE <= result.hi**2 or result.hi == 0


def test_reciprocal_requires_a_proven_nonzero_denominator():
    with pytest.raises(ValueError, match="contains zero"):
        1 / I(-Q(1, 10**80), Q(1, 10**80))
    with pytest.raises(ValueError, match="Reversed"):
        I(2, 1)
    with pytest.raises(ValueError, match="Negative"):
        I(-1, 1).sqrt()


def test_grid_does_not_lose_small_epoch_shifts_at_far_future_JD():
    epoch = Q(4680826) + Q(67871, 86400)
    shifted = I(epoch + Q(1, 86400000000))
    assert shifted.contains(epoch + Q(1, 86400000000))
    assert not shifted.contains(epoch)
    assert BITS == 256


def test_jet_derivative_is_enclosed_through_quotient_and_square_root():
    t = A(I(Q(1, 3), Q(2, 3)), 1)
    # f(t)=sqrt(t*t+1)/(t+2). Independent exact derivative comparison.
    f = (t * t + 1).sqrt() / (t + 2)
    for x in [Q(1, 3), Q(1, 2), Q(2, 3)]:
        root = I(x * x + 1).sqrt()
        expected = (2 * x - 1) / (root * (x + 2) * (x + 2))
        assert f.d.lo <= expected.lo <= expected.hi <= f.d.hi


def test_derivative_at_a_singular_sqrt_cannot_be_silently_certified():
    with pytest.raises(ValueError, match="Nondifferentiable"):
        A(I(0, 1), 1).sqrt()
