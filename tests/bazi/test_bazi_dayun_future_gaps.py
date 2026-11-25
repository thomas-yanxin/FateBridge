"""Frozen initial/internal/final-boundary future-gap range counterexamples."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo
from tests.unit_test.fixtures.dayun_future_gap_reference import (
    FIXTURE,
    FUTURE_GAP_REFERENCE,
    INITIAL_BOUNDARY_CONTROLS,
    FutureGapControl,
)

LATER_PATH = FIXTURE / "later-period-controls.json"
assert (
    hashlib.sha256(LATER_PATH.read_bytes()).hexdigest()
    == LATER_PATH.with_suffix(".sha256").read_text().strip()
)
LATER = json.loads(LATER_PATH.read_text())["controls"]


@pytest.mark.parametrize("row", INITIAL_BOUNDARY_CONTROLS, ids=lambda row: row["id"])
def test_future_gap_initial_boundary_keeps_the_source_before_dayun_witness(
    row: FutureGapControl,
) -> None:
    person = PersonInfo.model_validate(row["input"])
    before = person.model_dump()
    result = analyze_birth_time_range(
        person, 1, analysis_moment=datetime.fromisoformat(row["analysis_at"])
    )
    assert (
        sorted({p["status"] for p in result["current_dayun_candidates"]})
        == row["expected_statuses"]
    )
    assert "current_dayun" in result["affected_fields"]
    assert result["sample_count"] == 3
    assert person.model_dump() == before
    assert result["event_analysis"]["continuous_completeness_certified"] is False


@pytest.mark.parametrize("row", LATER, ids=lambda row: row["id"])
def test_future_gap_internal_and_final_boundaries_keep_adjacent_period_candidates(
    row,
) -> None:
    person = PersonInfo.model_validate(row["input"])
    before = person.model_dump()
    result = analyze_birth_time_range(
        person, 1, analysis_moment=datetime.fromisoformat(row["analysis_at"])
    )
    actual = sorted(
        {(p["status"], p["period"]) for p in result["current_dayun_candidates"]}
    )
    assert actual == [tuple(p) for p in row["expected_current_candidates"]]
    assert "current_dayun" in result["affected_fields"]
    assert person.model_dump() == before
    assert result["sample_count"] == 3


def test_source_reference_retains_all_declared_interactions_and_import_boundary() -> (
    None
):
    assert len(FUTURE_GAP_REFERENCE["rows"]) == 22162
    assert FUTURE_GAP_REFERENCE["counts"]["resolved_source_controls"] == 22035
    assert FUTURE_GAP_REFERENCE["counts"]["unresolved_interaction"] == 127
    assert FUTURE_GAP_REFERENCE["no_application_dateutil_zoneinfo_imported"] is True
