"""Preserve the new wider template, including every unresolved endpoint."""

import json
from pathlib import Path

import pytest

from scripts.astrodice.audit_astrodice_lunar_precision import digest, validate_reference

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "tests/data/astrodice/tables/lunar-wide-protocol.json"
R = ROOT / "tests/data/astrodice/tables/lunar-wide-reference.json"


def test_raw_reference_and_all_centers_remain_frozen_with_missing_endpoints():
    assert (
        digest(P) == "0d5b8f8addd380a21de536cdb731dbfbcb68af6798e25f4c802ca1f7ffe63bbc"
    )
    assert (
        digest(R) == "ae75eb1365bfa5a4b502519a597bfbb3aaf1ac085b453890e230135fe94abfc9"
    )
    result = validate_reference(json.loads(P.read_text()), json.loads(R.read_text()))
    assert result["centers"] == 137 and result["available"] == 135
    assert result["position_probes"] == 2590 and not result["template_failures"]
    assert [r["date_tt"] for r in result["incomplete"]] == [
        "0001-01-01T12:00:00",
        "9999-12-29T12:00:00",
    ]
    assert all(
        r["status"] == "incomplete" and r["missing_probes"]
        for r in result["incomplete"]
    )


@pytest.mark.parametrize("problem", ["raw", "time", "rate", "missing", "cohort"])
def test_reference_tampering_cannot_turn_into_an_acceptance(problem):
    protocol = json.loads(P.read_text())
    reference = json.loads(R.read_text())
    if problem == "raw":
        reference["batches"][0]["raw_response_utf8"] += " "
    elif problem == "time":
        reference["batches"][0]["parameters"]["TIME_TYPE"] = "'UT'"
    elif problem == "rate":
        next(r for r in reference["rows"] if r["status"] == "available")[
            "icrf_direction_derivative_per_day"
        ][0] += 0.001
    elif problem == "missing":
        reference["rows"][0]["status"] = "available"
    else:
        reference["rows"][1]["cohort"] = "holdout"
    with pytest.raises(ValueError):
        validate_reference(protocol, reference)


def test_fractional_boundary_holdout_is_frozen_and_complete():
    p = ROOT / "tests/data/astrodice/tables/lunar-fractional-window-protocol.json"
    r = ROOT / "tests/data/astrodice/tables/lunar-fractional-window-reference.json"
    assert (
        digest(p) == "14cb0db262edb01b245bed8b60beea593f7f9e29ec7497329a08739ef5d9079c"
    )
    assert (
        digest(r) == "71b14119a99fd0c709817e3c1f7dab0df1773f9b39431642ae0dd2c4cea9dfd2"
    )
    result = validate_reference(json.loads(p.read_text()), json.loads(r.read_text()))
    assert result["centers"] == result["available"] == 51
    assert result["position_probes"] == 969
    assert not result["incomplete"] and not result["template_failures"]


def test_fractional_tt_calendar_labels_preserve_microseconds():
    from scripts.astrodice.audit_astrodice_position_motion import parse_date

    assert (
        parse_date("600ad-Jan-01 00:00:00.250000", True) == "0600-01-01T00:00:00.250000"
    )
    assert parse_date(" 9600-Jan-01 00:00:00.750 ") == "9600-01-01T00:00:00.750000"
    with pytest.raises(ValueError):
        parse_date(" 9600-Jan-01 00:00:00.0000001 ")


def test_new_precise_source_holdouts_keep_the_original_horizons_parameters():
    directory = ROOT / "tests/data/astrodice/precise-source-holdout"
    protocol = json.loads((directory / "protocol.json").read_text())
    reference = json.loads((directory / "reference.json").read_text())
    assert (
        digest(directory / "protocol.json")
        == "d966d6ebecf1af716ad3d291a0abd7d6d34ebf3c8d7f43552a80c177e5dc0d1e"
    )
    assert (
        digest(directory / "reference.json")
        == "0dd3025a7ef448894329e2019eb74fbf76819ac55d2e9a493c299a7bb7631c58"
    )
    original = json.loads(P.read_text())
    for key in [
        "reference_parameters",
        "steps_seconds",
        "chosen_step_seconds",
        "offsets_seconds",
    ]:
        assert protocol[key] == original[key]
    assert not protocol["development_dates_tt"]
    assert not set(protocol["holdout_dates_tt"]) & set(
        original["development_dates_tt"] + original["holdout_dates_tt"]
    )
    result = validate_reference(protocol, reference)
    assert result["centers"] == result["available"] == 12
    assert result["position_probes"] == 228
    assert not result["incomplete"] and not result["template_failures"]


def test_precision_audit_grades_the_current_complete_source_derivative(monkeypatch):
    from scripts.astrodice.audit_astrodice_lunar_precision import audit

    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    protocol = json.loads(P.read_text())
    reference = json.loads(R.read_text())
    row = next(r for r in reference["rows"] if r["date_tt"] == "3000-12-07T04:07:32")
    result = audit(protocol, {"rows": [row]}, production_order=True)
    assert (
        result["gated_rate_metric"] == "current_fixed_source_rate_error_arcsec_per_day"
    )
    assert result["fixed_line_arcsec_per_day"] == 0.002
    assert result["fixed_position_line_arcsec"] == 0.02
    actual = result["cases"][0]
    assert actual["source_motion_status"] == "applied"
    assert (
        actual["current_source_method_id"]
        == "lunar_fixed_frame_source_derivative_with_observer_acceleration_v1"
    )
    assert (
        actual["native_icrf_rate_error_arcsec_per_day"]
        > actual["current_fixed_source_rate_error_arcsec_per_day"]
    )
    failed = (
        actual["current_fixed_source_rate_error_arcsec_per_day"] > 0.002
        or actual["icrf_position_error_arcsec"] > 0.02
    )
    assert result["exit_code"] == (1 if failed else 0)
    assert result["summary"]["all"][result["gated_rate_metric"]][
        "above_fixed_line"
    ] == int(actual["current_fixed_source_rate_error_arcsec_per_day"] > 0.002)
