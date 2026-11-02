"""Exact half-open membership at house cusps, without an artificial tolerance."""

import math
from fractions import Fraction as F

import pytest

from fatebridge.core.astro.geometry import _house_for_longitude


def test_last_house_does_not_round_up_at_the_wrapped_first_cusp():
    cusps = [(60.0 + i * 30) % 360 for i in range(12)]
    assert (
        _house_for_longitude(math.nextafter(60.0, -math.inf), 60.0, "whole_sign", cusps)
        == 12
    )
    assert _house_for_longitude(60.0, 60.0, "whole_sign", cusps) == 1


@pytest.mark.parametrize("origin", [0.0, 30.0, 60.0, 215.12345])
def test_every_cusp_matches_independent_circular_interval_membership(origin):
    cusps = [(origin + i * 30) % 360 for i in range(12)]
    for edge in cusps:
        for probe in [
            math.nextafter(edge, -math.inf),
            edge,
            math.nextafter(edge, math.inf),
        ]:
            matches = []
            for i, start in enumerate(cusps):
                width = (F(cusps[(i + 1) % 12]) - F(start)) % 360
                offset = (F(probe) - F(start)) % 360
                if offset < width:
                    matches.append(i + 1)
            assert len(matches) == 1
            assert _house_for_longitude(probe, origin, "equal", cusps) == matches[0]


def test_equal_house_fallback_also_retains_both_sides_of_every_edge():
    ascendant = 60.0
    for i in range(12):
        edge = (ascendant + 30 * i) % 360
        assert _house_for_longitude(edge, ascendant, "equal") == i + 1
        assert (
            _house_for_longitude(math.nextafter(edge, -math.inf), ascendant, "equal")
            == (i - 1) % 12 + 1
        )
        assert (
            _house_for_longitude(math.nextafter(edge, math.inf), ascendant, "equal")
            == i + 1
        )


def test_whole_sign_fallback_handles_negative_wrap_without_rounding_to_zero():
    assert _house_for_longitude(math.nextafter(0.0, -math.inf), 0.0, "whole_sign") == 12
    assert _house_for_longitude(0.0, 0.0, "whole_sign") == 1


def test_nonfinite_geometry_is_rejected_explicitly():
    for invalid in [math.nan, math.inf, -math.inf]:
        invalid_cusps = [invalid, *[float(i * 30) for i in range(1, 12)]]
        for args in [
            (invalid, 0.0, None),
            (0.0, invalid, None),
            (0.0, 0.0, invalid_cusps),
        ]:
            with pytest.raises(ValueError, match="finite"):
                _house_for_longitude(args[0], args[1], "equal", args[2])
