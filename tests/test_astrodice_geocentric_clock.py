"""Analytic necessary enclosures and IEEE rounding support, not sky holdouts."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice_geocentric_clock import delay_support, enclose
from scripts.verify_astrodice_emission_epoch import cell
from scripts.verify_astrodice_geocentric_clock import delay_proof


@pytest.mark.parametrize("increasing", (True, False))
def test_necessary_enclosure_contains_every_uncertainty_parameter(increasing):
    sign = 1 if increasing else -1
    result = enclose(
        lambda t: (1 + sign * t - Q(1, 1000), 1 + sign * t + Q(1, 1000)),
        (Q(-1), Q(1)),
        (Q(99, 100), Q(101, 100)),
        increasing,
        48,
    )
    low, high = map(Q, result["effective_reception_JD"])
    assert low <= -Q(11, 1000) <= Q(11, 1000) <= high
    assert not result["root_existence_or_uniqueness_proved"]
    excluded = enclose(lambda t: (1 + t, 2 + t), (Q(0), Q(1)), (Q(10), Q(11)), True, 48)
    assert excluded == {"status": "excluded_over_original_support"}


@pytest.mark.parametrize(
    "family", ("absolute_JD_binary64", "seconds_from_J2000_binary64")
)
def test_both_rounding_models_elapsed_support_covers_binade_edges(family):
    row = {"light_time_minutes": "8.1234567800000000"}
    for raw_tr in (float(2**20), -float(2**20), float(2**37), -float(2**37)):
        scale = Q(1 if family == "absolute_JD_binary64" else 86400)
        nominal = Q(raw_tr) if scale == 1 else Q(2451545) + Q(raw_tr) / scale
        support = delay_support(row, 0, family, nominal)
        low, high = delay_proof(row, 0, family, nominal, support)
        light = Q(row["light_time_minutes"]) * scale / 1440
        for delay in (light, Q(float(light))):
            te = float(Q(raw_tr) - delay)
            a, b, _ = cell(te)
            assert low * scale <= Q(raw_tr) - Q(te) <= high * scale
            assert a <= Q(raw_tr) - delay <= b
