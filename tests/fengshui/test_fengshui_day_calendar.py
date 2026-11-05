"""Independent calendar inputs must not certify an ambiguous source selector."""

import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.validation import fengshui_day_calendar as audit
from fatebridge.validation.fengshui_day_hour import load_day_hour_reference

FOLDER = Path(__file__).parents[1] / "data/fengshui_day_calendar_v1"
TABLES = Path(__file__).parents[1] / "data/fengshui_day_hour_tables_v1"


def reference():
    return audit.load_day_calendar_reference(FOLDER)


@pytest.fixture(scope="module")
def result():
    return audit.audit_calendar_selection_hypotheses(
        reference(), load_day_hour_reference(TABLES)
    )


def test_capture_precedes_candidate_model():
    assert hashlib.sha256((FOLDER / "reference.json").read_bytes()).hexdigest() == (
        "6961056b2e02c14345854983ef888cd05570672a5738de02c6f97930b269979d"
    )
    assert reference()["frozen_before_candidate_probe"] is True


def test_independent_published_calendars_conform_only_at_declared_granularity(result):
    assert result["independent_published_day_cases"] == 730
    assert result["day_ganzhi_differences"] == []
    assert result["independent_published_term_date_cases"] == 48
    assert result["term_date_differences"] == []
    assert result["independent_calendar_comparison_passed"] is True
    assert "not_second_precision" in result["astronomical_acceptance_scope"]
    assert len(result["term_resolutions"]) == 48
    assert all(
        "provider" in r and "time_basis" in r for r in result["term_resolutions"]
    )


def test_first_column_policy_discards_most_source_cells(result):
    policy = result["latest_first_column"]
    assert result["civil_dates_probed"] == 365
    assert policy["distinct_printed_day_cells_reached"] == 360
    assert policy["of_total_printed_day_cells"] == 1080
    assert len(policy["unreached_inverted_cells"]) == 36
    assert policy["complete_table_coverage"] is False


def test_full_window_policy_has_actual_date_counterexample(result):
    policy = result["retained_full_windows"]
    assert policy["ambiguous_civil_dates"] == 245
    assert policy["uncovered_civil_dates"] == []
    assert policy["sufficient_for_unique_selection"] is False
    witness = policy["ambiguity_witness"]
    assert (witness["date"], witness["ganzhi"]) == ("2026-06-19", "甲子")
    candidates = witness["full_window_candidates"]
    assert [(c["anchor_date"], c["table"], c["cycle"]) for c in candidates] == [
        ("2026-02-19", "middle_yang", 2),
        ("2026-04-20", "lower_yang", 1),
        ("2026-06-19", "upper_yin", 0),
    ]
    assert [c["palaces"]["C"] for c in candidates] == [1, 1, 9]
    assert [c["palaces"]["NW"] for c in candidates] == [2, 2, 8]
    assert witness["distinct_full_charts"] == 2
    assert witness["source_certified_selection"] is False


def test_table_header_carry_preserves_real_early_entry_date(result):
    # HKO gives 夏至 on June 21; the source heading admits Jiazi after 芒种.
    # This tests the stated hypothesis, never certifies actual hour/day policy.
    row = next(
        r for r in result["daily_hypothesis_results"] if r["date"] == "2026-06-19"
    )
    assert row["latest_first_column"]["table"] == "upper_yin"
    assert all(
        r["source_certified_selection"] is False
        for r in result["daily_hypothesis_results"]
    )


def test_successful_civil_calendar_never_awards_other_axes(result):
    for key in (
        "calendar_table_selection_verified",
        "day_hour_boundary_policy_verified",
        "included_in_complete_calendar_acceptance",
        "whole_book_conformity_established",
        "real_world_prediction_established",
    ):
        assert result[key] is False


def test_real_day_algorithm_regression_turns_calendar_gate_red(monkeypatch):
    original = audit.almanac.get_day_ganzhi
    monkeypatch.setattr(
        audit.almanac,
        "get_day_ganzhi",
        lambda y, m, d: "乙丑" if (y, m, d) == (2026, 6, 19) else original(y, m, d),
    )
    output = audit.audit_calendar_selection_hypotheses(
        reference(), load_day_hour_reference(TABLES)
    )
    assert output["day_ganzhi_differences"] == [
        {"date": "2026-06-19", "ganzhi": "甲子", "engine_ganzhi": "乙丑"}
    ]
    assert output["independent_calendar_comparison_passed"] is False
    # Selection hypotheses continue to use the independent observation.
    assert output["retained_full_windows"]["ambiguity_witness"]["ganzhi"] == "甲子"


def test_term_algorithm_regression_turns_calendar_gate_red(monkeypatch):
    original = audit.solar_term_resolution

    def shifted(year, name, zone):
        resolution = original(year, name, zone)
        if (year, name) == (2026, "夏至"):
            resolution = {
                **resolution,
                "moment": (
                    datetime.fromisoformat(resolution["moment"]) + timedelta(days=1)
                ).isoformat(),
            }
        return resolution

    monkeypatch.setattr(audit, "solar_term_resolution", shifted)
    output = audit.audit_calendar_selection_hypotheses(
        reference(), load_day_hour_reference(TABLES)
    )
    assert len(output["term_date_differences"]) == 1
    assert output["term_date_differences"][0]["date"] == "2026-06-21"
    assert output["independent_calendar_comparison_passed"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "empty_days",
        "missing_day",
        "duplicate_day",
        "bad_ganzhi",
        "broken_day_sequence",
        "missing_term",
        "duplicate_term",
        "term_order",
        "short_probe",
    ],
)
def test_incomplete_or_malformed_reference_cannot_turn_green(mutation):
    data = reference()
    if mutation == "empty_days":
        data["days"] = []
    elif mutation == "missing_day":
        data["days"].pop()
    elif mutation == "duplicate_day":
        data["days"][1] = deepcopy(data["days"][0])
    elif mutation == "bad_ganzhi":
        data["days"][0]["ganzhi"] = "甲丑"
    elif mutation == "broken_day_sequence":
        data["days"][1]["ganzhi"] = data["days"][0]["ganzhi"]
    elif mutation == "missing_term":
        data["terms"].pop()
    elif mutation == "duplicate_term":
        data["terms"][1] = deepcopy(data["terms"][0])
    elif mutation == "term_order":
        data["terms"][0]["date"] = "2026-01-01"
    else:
        data["probe_end"] = "2026-06-30"
    with pytest.raises(ValueError):
        audit.audit_calendar_selection_hypotheses(data, load_day_hour_reference(TABLES))


@pytest.mark.parametrize("file", sorted(audit._CAPTURE_NAMES))
def test_capture_byte_changes_rejected(tmp_path, file):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    (folder / file).write_bytes(b"changed")
    with pytest.raises(ValueError, match="capture changed"):
        audit.load_day_calendar_reference(folder)


def test_omitted_capture_manifest_entry_rejected(tmp_path):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest.pop("naoj-days-2026.html")
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Incomplete"):
        audit.load_day_calendar_reference(folder)


def test_rehashed_transcription_must_still_match_raw_primary_capture(tmp_path):
    folder = tmp_path / "capture"
    shutil.copytree(FOLDER, folder)
    data = reference()
    data["days"][0]["ganzhi"] = "甲子"
    path = folder / "reference.json"
    path.write_text(json.dumps(data))
    manifest = json.loads((folder / "hashes.json").read_text())
    manifest["reference.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (folder / "hashes.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="transcription differs"):
        audit.load_day_calendar_reference(folder)


def test_research_does_not_mutate_primary_observations():
    data, tables = reference(), load_day_hour_reference(TABLES)
    before = deepcopy((data, tables))
    audit.audit_calendar_selection_hypotheses(data, tables)
    assert (data, tables) == before
