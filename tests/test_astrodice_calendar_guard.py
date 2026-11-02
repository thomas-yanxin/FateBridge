"""The documented CAL path must retain the same physical prefix epoch."""

from fractions import Fraction as Q

import pytest

from scripts.audit_astrodice_horizons_wide_reference import DAY_US, input_tick
from scripts.gen_astrodice_horizons_wide import (
    calendar_label,
    julian_input_label,
    wire_epochs,
)


@pytest.mark.parametrize("encoding", ["JD", "MJD", "CAL"])
def test_calendar_and_numeric_paths_keep_identical_guard_and_primary_epochs(encoding):
    center = input_tick("8103ad-Jul-26 18:51:11.123456")
    primary = [center + t * 1000000 for t in [-1435, 0, 1435]]
    plan = {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": repr(encoding)},
        "maximum_labels_per_batch": 19,
    }
    wire, auxiliary = wire_epochs(plan, primary)
    assert wire == [auxiliary, *primary]
    # An independently fixed civil/JD identity: no calendar-midnight substitute.
    assert calendar_label(auxiliary) == "8103ad-Jul-25 12:00:00.000000"
    assert Q(julian_input_label(auxiliary)) == 4680825
    assert Q(julian_input_label(auxiliary, modified=True)) == Q(4561649, 2)
    for epoch in wire:
        assert input_tick(calendar_label(epoch)) == epoch
        assert abs(
            (Q(julian_input_label(epoch)) - Q(3442849, 2)) * DAY_US - epoch
        ) <= Q(1, 10**30)


def test_calendar_guard_does_not_admit_an_undocumented_encoding():
    plan = {
        "first_tlist_epoch_guard": {"method_id": "integer_jd_prefix_v1"},
        "reference_parameters": {"TLIST_TYPE": "'SECONDS'"},
        "maximum_labels_per_batch": 19,
    }
    with pytest.raises(ValueError, match="guard protocol"):
        wire_epochs(plan, [input_tick("2000ad-Jan-01 12:00:00.000000")])
