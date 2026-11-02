"""Analytic interval constraints; these fixtures are never celestial holdouts."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice_nonuniform_reference import polynomial
from scripts.astrodice_transferred_reference import system
from scripts.verify_astrodice_transferred_reference import independent_system


def analytic_data():
    epochs = {o: Q(o) + Q(o * o, 10**10) for o in range(-1440, 1441, 5)}
    intervals = {}
    for o, t in epochs.items():
        # RA crosses a full turn; DEC remains a polynomial in the source clock.
        ra = (1295999 + t / 100) % 1296000
        dec = Q(3) + t / 10000 + t * t / 10**9
        error = Q(1 + (o // 5) % 3, 10**6)
        intervals[o] = [(ra - error, ra + error), (dec - error, dec + error)]
    return intervals, epochs


@pytest.mark.parametrize("axis", (0, 1))
def test_all_interval_constraints_include_known_polynomial_and_independent_system(axis):
    intervals, epochs = analytic_data()
    a, b, base, scale = system(intervals, epochs, 1440, 7, axis)
    other, rhs, independent_base, independent_scale = independent_system(
        intervals, epochs, 1440, 7, axis
    )
    permutation = [1, 0, *range(2, 8)]
    assert [[row[k] for k in permutation] for row in a] == other
    assert (b, base, scale) == (rhs, independent_base, independent_scale)
    assert len(a) == 1154
    # Each interval midpoint lies on this analytic polynomial, including RA wrap.
    for row, high, negative, low in zip(a[::2], b[::2], a[1::2], b[1::2]):
        assert row == [-v for v in negative]
        assert high >= 0 and low >= 0
    assert polynomial(base, Q()) == 0
    assert base[1] == (Q(1440, 100) if axis == 0 else Q(1440, 10000))


def test_one_missing_node_refuses_fitting_even_if_outside_selected_window():
    intervals, epochs = analytic_data()
    del intervals[1440]
    with pytest.raises(ValueError, match="577"):
        system(intervals, epochs, 60, 5, 0)
