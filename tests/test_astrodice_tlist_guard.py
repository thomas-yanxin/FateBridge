"""The guard preserves every primary epoch and uses a separate exact JD."""

from fractions import Fraction

import pytest

from scripts.gen_astrodice_horizons_wide import julian_day, ticks, wire_epochs


def policy():
    return {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": "'JD'"},
        "maximum_labels_per_batch": 19,
    }


@pytest.mark.parametrize(
    "date",
    [
        "0001-01-01",
        "0750-04-02",
        "1582-10-15",
        "7750-12-31",
        "8103-07-26",
        "9999-12-31",
    ],
)
def test_integer_prefix_never_moves_or_replaces_any_requested_epoch(date):
    center = ticks(date + "T12:20:34")
    primary = [center + k * 1000000 for k in [-1440, -1430, -1140, 0, 1440]]
    wire, auxiliary = wire_epochs(policy(), primary)
    assert wire == [auxiliary, *primary]
    assert len(set(wire)) == len(primary) + 1
    jd = julian_day(auxiliary)
    assert jd.denominator == 1 and Fraction(float(jd)) == jd
    assert 1 <= julian_day(min(primary)) - jd < 2


def test_unguarded_historical_wire_protocol_stays_identical():
    primary = [3, 1, 2]
    assert wire_epochs({}, primary) == (primary, None)


@pytest.mark.parametrize("change", ["method", "encoding", "budget", "empty"])
def test_inapplicable_or_changed_guard_is_never_silently_ignored(change):
    p = policy()
    primary = [1, 2]
    if change == "method":
        p["first_tlist_epoch_guard"] = {"method_id": "other"}
    if change == "encoding":
        # CAL now serializes the same integer-JD prefix explicitly; unknown
        # encodings still fail before any request is sent.
        p["reference_parameters"]["TLIST_TYPE"] = "'SECONDS'"
    if change == "budget":
        p["maximum_labels_per_batch"] = 1
    if change == "empty":
        primary = []
    with pytest.raises(ValueError, match="Invalid first-TLIST-epoch guard"):
        wire_epochs(p, primary)
