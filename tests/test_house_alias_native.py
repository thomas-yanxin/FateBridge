"""E and A are the same declared Equal-Ascendant backend branch, not Placidus."""

import itertools

import pytest

from fatebridge.core.astro import runtime


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
def test_e_and_a_have_identical_native_cusps_on_the_predeclared_grid():
    count = 0
    for armc, lat, eps in itertools.product(
        range(0, 360, 30), [-55, -25, 0, 25, 55], [0, 23.4, 30]
    ):
        a = runtime.ephemeris_call("houses_armc", armc, lat, eps, b"A")
        e = runtime.ephemeris_call("houses_armc", armc, lat, eps, b"E")
        assert a == e
        count += 1
    assert count == 180
