"""MJD changes serialization only; independent rational checks bind TT epochs."""

from fractions import Fraction as Q

import pytest

from scripts.audit_astrodice_horizons_wide_reference import DAY_US, input_tick
from scripts.gen_astrodice_horizons_wide import julian_input_label, wire_epochs


@pytest.mark.parametrize(
    "calendar,mjd",
    [
        ("1858ad-Nov-17 00:00:00.000000", "0"),
        ("2000ad-Jan-01 12:00:00.000000", "51544.5"),
    ],
)
def test_documented_mjd_zero_and_j2000_literals(calendar, mjd):
    assert Q(julian_input_label(input_tick(calendar), modified=True)) == Q(mjd)


@pytest.mark.parametrize(
    "calendar",
    [
        "1bc-Dec-31 23:59:59.123456",
        "1431ad-Mar-17 09:23:41.000000",
        "6431ad-Sep-17 09:04:16.000000",
        "9431ad-Dec-17 09:23:41.000000",
        "10000ad-Jan-01 00:00:00.999999",
    ],
)
def test_mjd_preserves_the_exact_requested_microsecond_and_day_origin(calendar):
    tick = input_tick(calendar)
    mjd = Q(julian_input_label(tick, modified=True))
    # Independent rational inverse. No float JD or collector helper is used.
    assert abs((mjd + 678576) * DAY_US - tick) <= Q(1, 10**30)
    assert abs(Q(julian_input_label(tick)) - mjd - Q(4800001, 2)) <= Q(1, 10**45)


def test_mjd_retains_the_same_integer_jd_guard_and_all_primary_ticks():
    primary = [
        input_tick("6431ad-Sep-17 09:04:16.000000") + s * 1000000 for s in [-5, 0, 5]
    ]
    policy = {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": "'MJD'"},
        "maximum_labels_per_batch": 19,
    }
    wire, auxiliary = wire_epochs(policy, primary)
    assert wire == [auxiliary, *primary]
    guard_jd = Q(julian_input_label(auxiliary, modified=True)) + Q(4800001, 2)
    assert guard_jd.denominator == 1
    # A JD-integer guard has a half-integer MJD; an integer-MJD substitute
    # would shift the protected auxiliary epoch by twelve hours.
    assert Q(julian_input_label(auxiliary, modified=True)).denominator == 2
