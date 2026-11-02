"""Frozen initial/internal/final-boundary future-gap range counterexamples."""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo

FIXTURE = Path(__file__).parent / "fixtures/bazi_dayun_future_gaps_v1"
REFERENCE = FIXTURE / "reference.json.gz"
assert (
    hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    == REFERENCE.with_suffix(".sha256").read_text().strip()
)
DATA = json.loads(gzip.decompress(REFERENCE.read_bytes()))
KNOWN = [r for r in DATA["rows"] if r["status"] == "resolved_source_control"]
INITIAL = [KNOWN[0], next(r for r in KNOWN if r["input"]["birth_year"] >= 2000)]
LATER_PATH = FIXTURE / "later-period-controls.json"
assert (
    hashlib.sha256(LATER_PATH.read_bytes()).hexdigest()
    == LATER_PATH.with_suffix(".sha256").read_text().strip()
)
LATER = json.loads(LATER_PATH.read_text())["controls"]


@pytest.mark.parametrize("row", INITIAL, ids=lambda row: row["id"])
def test_future_gap_initial_boundary_keeps_the_source_before_dayun_witness(row):
    person = PersonInfo(**row["input"])
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
def test_future_gap_internal_and_final_boundaries_keep_adjacent_period_candidates(row):
    person = PersonInfo(**row["input"])
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


def test_source_reference_retains_all_declared_interactions_and_import_boundary():
    assert len(DATA["rows"]) == 22162
    assert DATA["counts"]["resolved_source_controls"] == 22035
    assert DATA["counts"]["unresolved_interaction"] == 127
    assert DATA["no_application_dateutil_zoneinfo_imported"] is True
