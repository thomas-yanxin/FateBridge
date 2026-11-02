"""Independent wire reads and exact field comparisons keep unknown scope."""

import json
from fractions import Fraction as Q

import pytest

from scripts.verify_astrodice_observer_timescale import expected_clock, inspect
from tests.test_astrodice_observer_timescale import CASE, PLAN, calibration, raw


@pytest.mark.parametrize("tt", ["TT", "TDB"])
def test_independent_reader_preserves_actual_time_header_and_raw_delta(tt):
    result = inspect(raw(tt), 200, {"time_type": tt}, [CASE], PLAN)
    assert result["status"] == "supported"
    assert result["actual_time_type"] == tt
    assert result["rows"][0]["TDB_minus_UT_seconds"] == "69.185000"


@pytest.mark.parametrize(
    "payload,status",
    [
        (b"[]", "invalid_response"),
        (b'{"result":null}', "invalid_response"),
        (
            json.dumps(
                {"error": "Only UT or TT are allowed for observer table TIME_TYPE"}
            ).encode(),
            "service_refused",
        ),
    ],
)
def test_independent_reader_does_not_promote_invalid_or_refused_responses(
    payload, status
):
    assert inspect(payload, 200, {"time_type": "TDB"}, [CASE], PLAN)["status"] == status


def test_independent_field_comparison_does_not_insert_unpublished_error_budgets():
    epoch = Q(CASE["nominal_JD"])
    row = {"nominal_JD": str(epoch), "TDB_minus_UT_seconds": "69.185000"}
    result = expected_clock(
        row,
        calibration(epoch + Q(1005, 1000000 * 86400)),
        calibration(epoch),
        "printing_only",
        PLAN,
    )
    assert result["status"] == "conditional_leap_hold_comparison"
    assert result["overlap_nominal_state"] is False
    assert result["overlap_paired_state"] is False
    assert result["time_field_is_internal_clock_bound_certified"] is False
    assert result["TT_geometric_six_not_refuted"] is False
