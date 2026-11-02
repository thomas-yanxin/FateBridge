"""Frozen source witnesses for a state hidden between natal/minute probes."""

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo

REFERENCE = (
    Path(__file__).parent / "fixtures/bazi_dayun_calendar_carries_v1/reference.json.gz"
)
assert (
    hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    == REFERENCE.with_suffix(".sha256").read_text().strip()
)
DATA = json.loads(gzip.decompress(REFERENCE.read_bytes()))
SELECTED = [
    DATA["rows"][0],
    next(r for r in DATA["rows"] if r["input"]["birth_year"] >= 2000),
]


@pytest.mark.parametrize("row", SELECTED, ids=lambda r: r["id"])
def test_range_retains_the_source_witness_before_dayun_state(row):
    person = PersonInfo(**row["input"])
    original = person.model_dump()
    result = analyze_birth_time_range(
        person, 1, analysis_moment=datetime.fromisoformat(row["analysis_at"])
    )
    assert (
        sorted({p["status"] for p in result["current_dayun_candidates"]})
        == row["expected_statuses"]
    )
    assert "current_dayun" in result["affected_fields"]
    assert result["sample_count"] == 3
    first = next(p for p in result["dayun_boundary_ranges"] if p["period"] == 1)
    witness = datetime.fromisoformat(row["expected_witnesses"][0]["manual_start_at"])
    assert (
        datetime.fromisoformat(first["earliest_start_at"])
        <= witness
        <= datetime.fromisoformat(first["latest_start_at"])
    )
    assert person.model_dump() == original
    assert result["event_analysis"]["continuous_completeness_certified"] is False


def test_reference_keeps_all_negative_carries_and_the_corrected_initial_hypothesis():
    assert DATA["counts"]["nominal_month_carries_in_birth_domain"] == 291964
    assert len(DATA["rows"]) == DATA["counts"]["negative_calendar_carry_jumps"] == 23794
    assert DATA["no_application_or_dateutil_imported"] is True
    assert DATA["rows"][0]["input"]["birth_day"] == 3
    assert DATA["rows"][0]["negative_jump_seconds"] < -86400
    assert all(r["missing_from_minute_grid"] == ["before_dayun"] for r in DATA["rows"])
