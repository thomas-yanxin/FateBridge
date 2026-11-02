"""Exact clock-field units, unavailable epochs and unqualified calibration."""

from fractions import Fraction as Q

import pytest

from scripts.astrodice_receiver_clock import receiver


def settings(ulps=0):
    return {
        "quantity30_modern_cutoff_JD": "4875369/2",
        "latest_known_TAI_minus_UTC_seconds": "37",
        "TT_minus_TAI_seconds": "32.184",
        "future_current_leap_hold_hypothesis_seconds": "69.184",
        "numerical_tube_profiles": {"test": {"extra_binary64_ULPs": ulps}},
    }


def test_clock_field_is_added_as_exact_seconds_to_the_nominal_label():
    row = {"nominal_JD": "2974374", "TDB_minus_UT_seconds": "69.185057"}
    actual = receiver(row, {}, "quantity30_current_leap_hold", "test", settings())
    assert actual["status"] == "available"
    cal = actual["calibration"]
    assert [(Q(v) - 2974374) * 86400 for v in cal["effective_JD"]] == [
        Q(1056, 1000000),
        Q(1058, 1000000),
    ]
    assert cal["all_six_compatible"] is False


def test_second_printing_profile_expands_the_field_interval_without_qualification():
    row = {"nominal_JD": "5166012", "TDB_minus_UT_seconds": "69.183233"}
    intervals = []
    for ulps in (0, 64):
        cal = receiver(row, {}, "quantity30_current_leap_hold", "test", settings(ulps))[
            "calibration"
        ]
        assert cal["all_six_compatible"] is False
        intervals.append(list(map(Q, cal["effective_JD"])))
    assert intervals[1][0] < intervals[0][0] < intervals[0][1] < intervals[1][1]


def test_ancient_ut1_field_cannot_be_promoted_to_tt_tdb_even_when_field_is_missing():
    assert receiver(
        {"nominal_JD": "2243797"},
        {},
        "quantity30_current_leap_hold",
        "test",
        settings(),
    ) == {"status": "not_assessed_pre_1962"}


def test_unavailable_modern_field_is_not_replaced_by_zero_or_vector_clock():
    assert receiver(
        {"nominal_JD": "2974374", "TDB_minus_UT_seconds": None},
        {},
        "quantity30_current_leap_hold",
        "test",
        settings(),
    ) == {"status": "time_field_unavailable"}


def test_vector_calibration_status_and_failed_components_are_preserved():
    cal = {"status": "unbracketed", "all_six_compatible": False}
    assert receiver({}, cal, "vector_TT_source_epoch", "test", settings()) == {
        "status": "available",
        "calibration": cal,
    }
    assert cal == {"status": "unbracketed", "all_six_compatible": False}


def test_inconsistent_leap_hold_and_undeclared_model_are_rejected():
    row = {"nominal_JD": "2974374", "TDB_minus_UT_seconds": "69.185057"}
    plan = settings()
    plan["TT_minus_TAI_seconds"] = "32"
    with pytest.raises(ValueError, match="decomposition"):
        receiver(row, {}, "quantity30_current_leap_hold", "test", plan)
    with pytest.raises(ValueError, match="Unplanned"):
        receiver(row, {}, "zero_TT_TDB", "test", settings())


@pytest.mark.parametrize("field", ["NaN", "Infinity"])
def test_nonfinite_time_field_is_never_a_receiver_interval(field):
    with pytest.raises(ValueError):
        receiver(
            {"nominal_JD": "2974374", "TDB_minus_UT_seconds": field},
            {},
            "quantity30_current_leap_hold",
            "test",
            settings(),
        )
