"""Exact source roots and retained historical cycle/nonbracketing counterexamples."""

import math
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from fatebridge.core.astro.light_cone import LIGHT_SPEED_AU_DAY, solve_light_cone
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize(
    "observation", [0.0, -12345.0, 2451545.0, 2460398.8333333335, 1e8]
)
def test_stationary_source_selects_exact_rational_first_post_light_cone(
    observation,
) -> None:
    # The constant one-AU source gives an independent exact root. These are
    # mathematical TT carriers, not claimed observed dates or source accuracy.
    exact = Fraction(observation) - Fraction(149597870700, 299792458 * 86400)
    expected = float(exact)
    if Fraction(expected) < exact:
        expected = math.nextafter(expected, math.inf)
    else:
        pass
    solution = solve_light_cone(
        observation, [0.0, 0.0, 0.0], lambda at: ((1.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0)
    )
    assert solution.upper.epoch == expected
    assert Fraction(solution.lower.epoch) < exact <= Fraction(solution.upper.epoch)
    assert math.nextafter(solution.lower.epoch, math.inf) == solution.upper.epoch
    assert solution.lower.residual_squared < 0 < solution.upper.residual_squared
    assert 1 <= solution.iterations <= 20


def test_subluminal_linear_source_has_certified_adjacent_root_not_cycle_acceptance() -> (
    None
):
    observation = 2460398.8333333335
    lower = observation - 0.01
    upper = math.nextafter(lower, math.inf)
    midpoint = (Fraction(lower) + Fraction(upper)) / 2
    c = Fraction(299792458 * 86400, 149597870700)
    velocity = c / 100

    def source(at):
        # Independent linear trajectory whose unrounded root is the midpoint.
        distance = float(
            c * (Fraction(observation) - midpoint)
            + velocity * (Fraction(at) - midpoint)
        )
        return (distance, 0.0, 0.0, float(velocity), 0.0, 0.0), 0

    solution = solve_light_cone(observation, [0.0, 0.0, 0.0], source)
    assert solution.upper.epoch == upper
    assert solution.lower.epoch == lower and solution.upper.epoch == upper
    with localcontext() as context:
        context.prec = 100
        speed = Decimal(299792458) * Decimal(86400) / Decimal(149597870700)
        for epoch, sign in [(lower, -1), (upper, 1)]:
            values, _ = source(epoch)
            residual = (
                Decimal(epoch) - Decimal(observation) + Decimal(values[0]) / speed
            ) * Decimal(86400)
            assert residual * sign > 0
    assert 1 <= solution.iterations <= 20


def test_exact_light_cone_root_is_distinguished_from_an_adjacent_bracket() -> None:
    solution = solve_light_cone(
        2451545.0, [0.0, 0.0, 0.0], lambda at: ((0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0)
    )
    assert solution.upper.epoch == 2451545.0 and solution.iterations == 1
    assert solution.lower.epoch == solution.upper.epoch
    assert solution.lower.residual_squared == solution.upper.residual_squared == 0


def test_unbracketed_source_still_fails_after_the_original_twenty_steps() -> None:
    observation = 2451545.0
    calls = []

    def no_light_cone(at):
        # A numerical source violating the subluminal prerequisite: F stays
        # positive. Its endless proposals must never become a computed place.
        calls.append(at)
        return (
            LIGHT_SPEED_AU_DAY * (observation - at) + 1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ), 0

    with pytest.raises(EphemerisSourceError) as failure:
        solve_light_cone(observation, [0.0, 0.0, 0.0], no_light_cone)
    assert failure.value.reason == "light_cone_not_bracketed"
    assert len(calls) == 20


@pytest.mark.parametrize("offset", [-0.02, -0.01, 0.0, 0.01, 0.02])
def test_real_j2000_source_refines_its_fine_clock_bracket(offset) -> None:
    from fatebridge.core.astro.analytic_observer import AnalyticObserver

    # This real source previously exhausted the combined twenty-step loop.
    # Its fine elapsed-TT bracket must resolve without an epsilon or JD loss.
    source = AnalyticObserver()
    observation = 2451545.0007387605 - 2451545.0 + offset
    earth = source._source_state("Earth", observation).position
    solution = solve_light_cone(
        observation,
        earth,
        lambda at: (source._source_state("Jupiter", at).position, None),
    )
    assert solution.lower.residual_squared < 0 < solution.upper.residual_squared
    assert math.nextafter(solution.lower.epoch, math.inf) == solution.upper.epoch
