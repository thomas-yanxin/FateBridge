"""Probe contracts distinguish refusal, unavailable output and valid tables."""

import json

from scripts.astrodice_observer_origin import classify

QUERY = {
    "origin": "SSB",
    "cases": [{"id": "p", "role": "primary", "nominal_JD": "2451545"}],
}
PLAN = {
    "row_assignment_radius_seconds": "1",
    "returned_label_match_budget_days": "1/1000000000",
}


def raw(center="Solar System Barycenter (0)"):
    return json.dumps({"result": f"""Target body name: Earth (399) DE441
Center body name: {center} DE441
Calendar mode : Gregorian
Date__(TT) JDTT R.A.___(ICRF) RA_(ICRF-a-app) 1-way_down_LT delta, deldot
$$SOE
2000-Jan-01 12:00:00,2451545.000000000,,,120.000000000,20.000000000,1.00000000000000,0.1200000,8.31674640,120.000000000,20.000000000,
$$EOE"""}).encode()


def test_supported_origin_has_explicit_clock_and_quantity_scope():
    d = classify(raw(), 200, QUERY, PLAN)
    assert d["status"] == "supported" and len(d["rows"]) == 1
    assert d["rows"][0]["original_label_budget_pass"]
    assert not d["physical_time_model_certified"]


def test_service_errors_and_other_origin_cannot_be_promoted():
    assert (
        classify(b'{"error":"unsupported observer"}', 200, QUERY, PLAN)["status"]
        == "service_error"
    )
    assert classify(raw(), 502, QUERY, PLAN)["status"] == "transport_unavailable"
    assert (
        classify(raw("Sun (10)"), 200, QUERY, PLAN)["status"] == "contract_unverified"
    )
    assert (
        classify(b"<html>failure</html>", 200, QUERY, PLAN)["status"]
        == "invalid_response"
    )


def test_unavailable_numeric_columns_are_unverified():
    value = raw().replace(b"1.00000000000000", b"n.a.")
    assert classify(value, 200, QUERY, PLAN) == {
        "status": "contract_unverified",
        "reason": "nonnumeric_quantity",
    }
