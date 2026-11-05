"""The restoration grader must retain failures and unresolved uncertainty."""

import math

import pytest

from scripts.audit_astrodice_de441_restore import (
    FAIL,
    PASS,
    UNRESOLVED,
    grade_frames,
    reference_axes,
)


def frame(low, high, qualified=True):
    return {
        "conditional_error_lower_arcsec_per_day": low,
        "conditional_error_upper_arcsec_per_day": high,
        "reference": {"frame_check_qualified": qualified},
    }


def test_failure_cannot_be_hidden_by_other_frame_uncertainty():
    assert (
        grade_frames({"tropical": frame(0.0021, 0.003), "lahiri": frame(0, 1)}) == FAIL
    )


@pytest.mark.parametrize("other", [frame(0.001, 0.00201), frame(0, 0.001, False)])
def test_midpoint_alone_or_unqualified_frame_cannot_pass(other):
    assert grade_frames({"tropical": frame(0, 0.001), "lahiri": other}) == UNRESOLVED


def test_whole_error_interval_must_satisfy_original_line():
    assert (
        grade_frames({"tropical": frame(0, 0.002), "lahiri": frame(0, 0.002)}) == PASS
    )


def test_observed_reference_spread_is_not_discarded_or_halved():
    samples = {
        str(k * h): {"printed_angles": ["0.000000000", "0.000000000"]}
        for h in (21600, 43200)
        for k in range(-6, 7)
    }
    row = {
        "body": "Moon",
        "samples": samples,
        "derivatives_per_tt_day": {"43200": [0, math.radians(1), 0]},
        "step_difference_arcsec_per_day": 0.001,
    }
    axes, policy = reference_axes(
        row,
        {
            "steps_seconds": {"Moon": [21600, 43200]},
            "selected_step_seconds": {"Moon": 43200},
        },
    )
    assert float(sum(axes[0]) / 2) == pytest.approx(3600)
    assert float((axes[0][1] - axes[0][0]) / 2) > 0.001
    assert policy["physical_truncation_bound_certified"] is False
