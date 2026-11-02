"""Published ERFA vectors and analytic controls; not astronomical holdouts."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice_clock_interval import A, I, unit
from scripts.astrodice_emission_transfer import (
    aberration,
    light_deflection,
    signed_rates,
    solar_deflection,
)


def vector(values):
    return [A(Q(float(x))) for x in values]


def test_full_lorentz_potential_matches_frozen_erfa_ab_vector():
    # ERFA t_erfa_c.c, t_ab; SRS exact-decimal model vs C binary64 arithmetic.
    p = vector([-0.76321968546737951, -0.60869453983060384, -0.21676408580639883])
    v = vector([2.1044018893653786e-5, -8.9108923304429319e-5, -3.8633714797716569e-5])
    got = aberration(p, v, A(Q(float(0.99980921395708788))), "full_Lorentz", 1)
    expected = [-0.7631631094219556269, -0.6087553082505590832, -0.2167926269368471279]
    for result, value in zip(got, expected):
        lo, hi = result.v.bounds()
        assert abs((lo + hi) / 2 - Q(float(value))) < Q(5, 10**15)


def test_general_deflection_matches_frozen_erfa_ld_vector():
    p = vector([-0.763276255, -0.608633767, -0.216735543])
    q = vector([-0.763276255, -0.608633767, -0.216735543])
    e = vector([0.76700421, 0.605629598, 0.211937094])
    got, _ = light_deflection(
        p, q, e, A(Q(float(8.91276983))), Q(float(0.00028574)), Q(float(3e-10))
    )
    expected = [-0.7632762548968159627, -0.6086337670823762701, -0.2167355431320546947]
    for result, value in zip(got, expected):
        lo, hi = result.v.bounds()
        assert abs((lo + hi) / 2 - Q(float(value))) < Q(1, 10**12)


def test_published_ld_geometry_is_outside_declared_point_sun_domain():
    p = vector([-0.763276255, -0.608633767, -0.216735543])
    q = vector([-0.763276255, -0.608633767, -0.216735543])
    e = vector([0.76700421, 0.605629598, 0.211937094])
    with pytest.raises(ValueError, match="denominator"):
        solar_deflection(p, q, e, A(Q(float(8.91276983))))


@pytest.mark.parametrize("model", ("full_Lorentz", "normalized_second_order"))
@pytest.mark.parametrize("potential", (0, 1))
def test_zero_observer_velocity_leaves_direction_and_derivative_unchanged(
    model, potential
):
    p = [A(I(1), I(0)), A(I(0), I(1)), A(I(0), I(0))]
    got = aberration(p, vector([0, 0, 0]), A(1), model, potential)
    rates = signed_rates(got)
    assert rates[0].bounds()[0] > 200000 and rates[1].contains(0)
    assert got[0].v.contains(1) and got[1].d.contains(1)


def test_coordinate_pole_is_explicitly_unqualified():
    with pytest.raises(ValueError, match="pole"):
        signed_rates(unit(vector([0, 0, 1])))
