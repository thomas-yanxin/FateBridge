"""Exercise real saved evidence and reject broken event/clock bindings."""

from __future__ import annotations

import copy
import json
import shutil

import pytest

from scripts import audit_ren_pmo_clock_basis as audit


@pytest.fixture(scope="module")
def inputs():
    return audit.saved_inputs()


def test_complete_saved_evidence_retains_original_failures_and_unknowns(inputs):
    result = audit.diagnose(*inputs)
    assert [
        (
            p["profile"],
            p["retained_events"],
            p["dut1_unknown_count"],
            p["all_original_civil_numeric_failures"],
            p["known_dut1_utc_failures"],
            p["known_dut1_hypothetical_ut1_failures"],
        )
        for p in result["profiles"]
    ] == [
        ("native_swiss", 113, 33, 21, 11, 6),
        ("native_moshier", 113, 33, 17, 10, 10),
        ("analytic", 113, 33, 21, 11, 8),
        ("de440", 113, 33, 21, 11, 6),
        ("spk", 113, 33, 21, 11, 6),
    ]
    assert result["new_unique_events"] == 0
    assert result["production_calculations_performed"] is False
    assert result["original_minute_gate_reclassified"] is False
    assert result["ut1_adopted_as_beijing_time"] is False
    assert result["goal_complete"] is False


def test_opposite_signed_dut1_and_historical_unknown(inputs):
    result = audit.diagnose(*inputs)
    rows = {(r["year"], r["term"]): r for r in result["profiles"][3]["rows"]}
    assert rows[1972, "大暑"]["hypothetical_ut1_delta_seconds"] == -29.944078
    assert rows[2011, "夏至"]["hypothetical_ut1_delta_seconds"] == 29.964092
    assert rows[2014, "寒露"]["hypothetical_ut1_delta_seconds"] == 30.024132
    assert rows[1900, "立春"]["original_civil_numeric_pass"] is False
    assert rows[1900, "立春"]["hypothetical_ut1_pass"] is None
    assert rows[1900, "立春"]["hypothetical_ut1_delta_seconds"] is None


@pytest.mark.parametrize(
    "damage",
    [
        "remove_event",
        "remove_anchor",
        "remove_profile",
        "reorder_profiles",
        "remove_saved_row",
        "duplicate_event",
        "wrong_event",
        "wrong_anchor",
        "missing_offset",
        "saved_error",
        "wrong_source",
        "wrong_delta",
        "nonfinite_delta",
        "wrong_grade",
        "nonfinite_dut1",
        "boolean_dut1",
    ],
)
def test_corrupted_bindings_fail_instead_of_shortening_or_rescoring(inputs, damage):
    reference, reports = copy.deepcopy(inputs)
    rows = reports["profiles"][0]["comparisons"]
    if damage == "remove_event":
        reference["protocol"]["cohort"].pop()
    elif damage == "remove_anchor":
        reference["rows"].pop()
    elif damage == "remove_profile":
        reports["profiles"].pop()
    elif damage == "reorder_profiles":
        reports["profiles"].reverse()
    elif damage == "remove_saved_row":
        rows.pop()
    elif damage == "duplicate_event":
        reference["protocol"]["cohort"][1] = reference["protocol"]["cohort"][0]
    elif damage == "wrong_event":
        rows[0]["term"] = "冬至"
    elif damage == "wrong_anchor":
        reference["rows"][0]["timestamp_label"] = "1900-01-01 00:00:00.000"
    elif damage == "missing_offset":
        rows[0]["actual"]["civil_datetime"] = "1900-01-01T00:00:00"
    elif damage == "saved_error":
        rows[0]["error"] = "calculation unavailable"
    elif damage == "wrong_source":
        rows[0]["source_identity_matches"] = False
    elif damage == "wrong_delta":
        rows[0]["actual_minus_printed_civil_seconds"] += 1
    elif damage == "nonfinite_delta":
        rows[0]["actual_minus_printed_civil_seconds"] = float("nan")
    elif damage == "wrong_grade":
        rows[0]["within_original_pmo_numeric_criterion"] = False
    elif damage == "nonfinite_dut1":
        reference["rows"][0]["UT1-UTC"] = float("inf")
    elif damage == "boolean_dut1":
        reference["rows"][0]["UT1-UTC"] = True
    with pytest.raises(ValueError):
        audit.diagnose(reference, reports)


def test_primary_reading_keeps_requirement_distinct_from_source_uncertainty():
    reading = audit.source_reading()
    assert reading["minute_table_physical_uncertainty_seconds"] is None
    assert reading["minute_rounding_algorithm_established"] is False
    assert reading["normative_requirement_is_not_measured_source_error"] is True
    assert reading["standard"]["full_12_page_standard_read"] is False


@pytest.mark.parametrize("rehash", [False, True])
def test_official_reading_rejects_changed_source_and_coordinated_rehash(
    tmp_path, rehash
):
    folder = tmp_path / "reading"
    shutil.copytree(audit.CORPUS, folder)
    target = folder / "reading.json"
    target.write_text(
        target.read_text().replace(
            '"minute_rounding_algorithm_established": false',
            '"minute_rounding_algorithm_established": true',
        )
    )
    if rehash:
        manifest = json.loads((folder / "freeze.json").read_text())
        manifest["files"]["reading.json"] = audit.sha(target)
        (folder / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit.source_reading(folder)
