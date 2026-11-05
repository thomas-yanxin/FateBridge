"""Retain inconsistent primary-source arithmetic instead of certifying it."""

import copy
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro import progression_key_sources as runtime_source
from fatebridge.core.output_midpoints import ProgressionKeySourceComparison
from fatebridge.utils.errors import handle_calculation_error
from scripts.western import replay_witte_progression_constant as independent


def test_each_printed_operand_is_checked_with_independent_timedelta_arithmetic():
    record = json.loads(independent.RECORD.read_text())
    result = runtime_source.progression_key_source_comparison()
    ProgressionKeySourceComparison.model_validate(result)
    rows = {row["id"]: row for row in result["operations"]}
    for source_row in record["operations"]:
        expected = sum(
            (
                term["sign"]
                * timedelta(
                    hours=term["hms"][0], minutes=term["hms"][1], seconds=term["hms"][2]
                )
                for term in source_row["terms"]
            ),
            timedelta(),
        )
        assert (
            rows[source_row["id"]]["computed_time_seconds"] == expected.total_seconds()
        )
    assert len(rows) == 8
    assert rows["event_time_arc"]["printed_minus_computed_time_seconds"] == -60
    assert (
        rows["progressed_meridian_sum"]["printed_minus_computed_time_seconds"] == 3600
    )
    assert sum(row["arithmetic_matches_print"] for row in rows.values()) == 6
    assert result["printed_arithmetic_consistent"] is False
    assert result["computed_for_current_chart"] is False
    assert result["selected_key_from_compared_source"] is False
    assert result["original_progression_time_key_accepted"] is False
    assert result["residuals_applied_as_corrections"] is False


def test_independent_replay_retains_both_failed_rows_and_conditional_dates():
    result = independent.replay(json.loads(independent.RECORD.read_text()))
    assert result["printed_arithmetic_consistent"] is False
    assert result["inconsistent_operation_ids"] == [
        "event_time_arc",
        "progressed_meridian_sum",
    ]
    diagnostic = result["fully_propagated_diagnostic"]
    assert diagnostic["computed_reduced_meridian_time_seconds"] == 38504  # 10:41:44
    assert diagnostic["printed_minus_propagated_time_seconds"] == 3540
    assert diagnostic["adopted_as_original_correction"] is False
    clocks = result["conditional_clock_labels"]
    assert clocks["civil_early_morning_then_printed_longitude"] == "1870-01-13T02:34:00"
    assert (
        clocks["printed_date_noon_plus_astronomical_hours_then_longitude"]
        == "1870-01-14T02:34:00"
    )
    assert clocks["difference_seconds"] == 86400
    assert clocks["either_interpretation_adopted"] is False
    assert result["authority_certified"] is False
    assert result["all_four_objectives_validated"] is False


def test_cli_writes_a_negative_conformance_result_and_returns_failure(tmp_path):
    target = tmp_path / "source.json"
    command = [sys.executable, str(Path(independent.__file__)), "--output", str(target)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 1
    report = json.loads(target.read_text())
    assert report["printed_arithmetic_consistent"] is False
    before = target.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0
    assert target.read_bytes() == before


def test_modified_transcription_is_rejected_before_writing_any_receipt(
    tmp_path, monkeypatch
):
    bad = tmp_path / "modified.json"
    source = json.loads(independent.RECORD.read_text())
    source["operations"][5]["printed_result_hms"] = [12, 50, 1]
    bad.write_text(json.dumps(source))
    monkeypatch.setattr(runtime_source, "RECORD", bad)
    with pytest.raises(RuntimeError, match="checksum") as failure:
        runtime_source.progression_key_source_comparison()
    envelope = handle_calculation_error(failure.value, "年长钥匙来源核查")
    assert envelope["error_code"] == "internal_error"
    assert envelope["status_code"] == 500
    target = tmp_path / "unearned-pass.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(independent.__file__)),
            "--source-record",
            str(bad),
            "--output",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0 and not target.exists()


@pytest.mark.parametrize(
    "parts", [[True, 0, 0], [-1, 0, 0], [1, 60, 0], [1, 0, 60], [1, 2], [1.0, 0, 0]]
)
def test_source_units_reject_silent_coercion(parts):
    for read in (runtime_source._time_seconds, independent.seconds):
        with pytest.raises(ValueError):
            read(parts)


def test_public_typed_source_evidence_rejects_corrupted_units_and_boolean():
    row = runtime_source.progression_key_source_comparison()
    invalid = copy.deepcopy(row)
    invalid["operations"][0]["computed_time_seconds"] = "52440"
    with pytest.raises(ValidationError):
        ProgressionKeySourceComparison.model_validate(invalid)
    invalid = copy.deepcopy(row)
    invalid["printed_arithmetic_consistent"] = "true"
    with pytest.raises(ValidationError):
        ProgressionKeySourceComparison.model_validate(invalid)
