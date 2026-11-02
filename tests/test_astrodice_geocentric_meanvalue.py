"""Mean-value set enclosures on analytic families, not celestial holdouts."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice_geocentric_meanvalue import mean_value_enclosure


@pytest.mark.parametrize("sign", (1, -1))
def test_uniform_derivative_enclosure_contains_every_toy_root(sign):
    derivative = (Q(2), Q(3)) if sign == 1 else (Q(-3), Q(-2))
    result = mean_value_enclosure(
        Q(0), (Q(3, 10), Q(1, 2)), (Q(-1, 10), Q(1, 10)), derivative, (Q(-1), Q(1))
    )
    low, high = map(Q, result["effective_reception_JD"])
    roots = [t / d for t in (Q(1, 5), Q(3, 5)) for d in derivative]
    assert low <= min(roots) <= max(roots) <= high
    assert not result["root_existence_or_uniqueness_proved"]


def test_empty_support_and_zero_derivative_are_not_promoted():
    excluded = mean_value_enclosure(
        Q(0), (Q(10), Q(11)), (Q(-1), Q(1)), (Q(2), Q(3)), (Q(-1), Q(1))
    )
    assert excluded["status"] == "excluded_over_original_support"
    assert excluded["effective_reception_JD"] is None
    with pytest.raises(ValueError):
        mean_value_enclosure(
            Q(0), (Q(0), Q(1)), (Q(0), Q(0)), (Q(-1), Q(1)), (Q(-1), Q(1))
        )
