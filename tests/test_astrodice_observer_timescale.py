"""Contract refusal and time-field comparisons must not promote clock scope."""

import json
from fractions import Fraction as Q

import pytest

from scripts.astrodice_observer_timescale import (
    classify,
    compare_field,
    selected_queries,
)

CASE = {"id": "one", "role": "new_frozen_timescale_condition", "nominal_JD": "4680826"}
PLAN = {
    "row_assignment_radius_seconds": "1",
    "returned_label_match_budget_days": "1/1000000000",
    "quantity30_modern_cutoff_JD": "4875369/2",
    "future_current_leap_hold_hypothesis_seconds": "69.184",
    "latest_known_TAI_minus_UTC_seconds": "37",
    "TT_minus_TAI_seconds": "32.184",
    "numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}},
}


def raw(tt="TT", delta="69.185000", stamp="4680826.000000000"):
    text = f"""Target body name: Venus (299) {{source: DE441}}
Center body name: Earth (399) {{source: DE441}}
Calendar mode : Gregorian
EOP file : frozen-EOP
EOP coverage : PREDICTS-> 2027-JAN-21
Date__({tt}) JD{tt} R.A.___(ICRF) RA_(ICRF-a-app) 1-way_down_LT TDB-UT
$$SOE
8103-Jul-26,{stamp}, , ,1.000000000,2.000000000,1.23456789012345,3.0000000,10.00000000,{delta},1.000000000,2.000000000,
$$EOE
"""
    return json.dumps({"result": text, "signature": {"version": "observed"}}).encode()


def test_actual_tdb_header_can_be_observed_without_claiming_documented_support():
    result = classify(raw("TDB"), 200, {"time_type": "TDB"}, [CASE], PLAN)
    assert result["status"] == "supported" and result["actual_time_type"] == "TDB"
    assert result["rows"][0]["TDB_minus_UT_seconds"] == "69.185000"
    assert result["EOP_file"] == "frozen-EOP"


def test_requested_tdb_never_falls_back_to_a_returned_tt_header():
    assert (
        classify(raw("TT"), 200, {"time_type": "TDB"}, [CASE], PLAN)["status"]
        == "contract_unverified"
    )


def test_explicit_time_type_refusal_is_distinct_from_unrelated_service_error():
    refused = json.dumps(
        {"error": "Only UT or TT are allowed for observer time types"}
    ).encode()
    other = json.dumps({"error": "Missing LTKERNL file"}).encode()
    assert (
        classify(refused, 200, {"time_type": "TDB"}, [CASE], PLAN)["status"]
        == "service_refused"
    )
    assert (
        classify(other, 200, {"time_type": "TDB"}, [CASE], PLAN)["status"]
        == "service_error_unclassified"
    )


@pytest.mark.parametrize(
    "payload",
    [b"[]", b"null", b"<html>error</html>", b"bad", b"{}", b'{"result":null}'],
)
def test_invalid_success_payloads_are_not_treated_as_a_supported_contract(payload):
    assert (
        classify(payload, 200, {"time_type": "TT"}, [CASE], PLAN)["status"]
        == "invalid_response"
    )


def test_unavailable_time_field_does_not_erase_supported_position_quantities():
    value = classify(raw(delta="n.a."), 200, {"time_type": "TT"}, [CASE], PLAN)
    assert value["status"] == "supported"
    assert value["rows"][0]["TDB_minus_UT_seconds"] is None
    assert value["rows"][0]["range_AU"] == "1.23456789012345"


def test_diagnostic_row_assignment_keeps_original_label_match_failure():
    value = classify(
        raw(stamp="4680826.000000002"), 200, {"time_type": "TT"}, [CASE], PLAN
    )
    assert value["status"] == "supported"
    assert value["rows"][0]["original_label_budget_pass"] is False


def calibration(epoch):
    return {
        "profiles": {
            "printing_only": {
                "status": "bracketed",
                "effective_JD": [str(epoch), str(epoch)],
                "all_six_compatible": False,
            }
        }
    }


def test_nominal_and_paired_clock_comparisons_are_separate_uncertified_models():
    epoch = Q(CASE["nominal_JD"])
    row = {"nominal_JD": str(epoch), "TDB_minus_UT_seconds": "69.185000"}
    result = compare_field(
        row,
        calibration(epoch + Q(1, 1000 * 86400)),
        calibration(epoch + Q(20, 1000000 * 86400)),
        "printing_only",
        PLAN,
    )
    assert result["status"] == "conditional_leap_hold_comparison"
    assert result["overlap_nominal_state"] is True
    assert result["overlap_paired_state"] is False
    assert result["TT_geometric_six_not_refuted"] is False
    assert result["time_field_is_internal_clock_bound_certified"] is False


def test_pre_1962_field_does_not_get_modern_leap_or_tt_tdb_interpretation():
    epoch = Q(2243797)
    value = compare_field(
        {"nominal_JD": str(epoch), "TDB_minus_UT_seconds": "69.185000"},
        calibration(epoch),
        calibration(epoch),
        "printing_only",
        PLAN,
    )
    assert value["status"] == "not_assessed_pre_1962"
    assert "reported_TDB_minus_TT_hypothesis_seconds" not in value


def test_published_rss_is_not_inserted_as_a_strict_accuracy_allowance():
    epoch = Q(CASE["nominal_JD"])
    value = compare_field(
        {"nominal_JD": str(epoch), "TDB_minus_UT_seconds": "69.185000"},
        calibration(epoch + Q(1005, 1000000 * 86400)),
        calibration(epoch),
        "printing_only",
        PLAN,
    )
    assert value["overlap_nominal_state"] is False


@pytest.mark.parametrize(
    "status,tdb_dispatch",
    [
        ("supported", True),
        ("service_refused", False),
        ("transport_unavailable", False),
        ("contract_unverified", False),
    ],
)
def test_conditional_branch_preserves_unavailable_requests_without_parameter_substitution(
    status, tdb_dispatch
):
    queries = [
        {"id": "TT", "cohort": "B", "conditional_on_A_TDB_support": False},
        {"id": "TDB", "cohort": "B", "conditional_on_A_TDB_support": True},
    ]
    selection = selected_queries(
        {"queries": queries}, "B", {"TDB_OBSERVER_contract_status": status}
    )
    assert selection == [(queries[0], True), (queries[1], tdb_dispatch)]
