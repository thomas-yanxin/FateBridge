"""An omitted source second must not erase derived actual-time seconds."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.services import timing_uncertainty as module
from fatebridge.utils.birth_input import PersonInfo

FIXTURE = (
    Path(__file__).parent
    / "data/bazi_uncertainty_events_v1/unknown-second-transition.json"
)


def reference():
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == FIXTURE.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(FIXTURE.read_text())


@pytest.mark.parametrize("second", [None, 0])
def test_derived_grid_preserves_actual_instants_across_historical_second_offset(
    second, monkeypatch
):
    ref = reference()
    person = PersonInfo(**ref["birth_input"], birth_second=second)
    before = person.model_dump()
    seen = []
    original = module.normalize_birth_time

    def observe(sample, **kwargs):
        result = original(sample, **kwargs)
        seen.append(result)
        return result

    monkeypatch.setattr(module, "normalize_birth_time", observe)
    actual = module.analyze_birth_time_range(
        person, 1, analysis_moment=datetime(2026, 1, 1)
    )
    assert [
        r.input_datetime.astimezone(timezone.utc).isoformat() for r in seen[1:]
    ] == ref["expected_grid_utc"]
    assert seen[-1].input_datetime.isoformat() == ref["expected_last_civil_clock"]
    assert (
        abs(
            (
                seen[-1].corrected_datetime
                - datetime.fromisoformat(ref["expected_last_corrected_clock"])
            ).total_seconds()
        )
        <= ref["corrected_absolute_tolerance_seconds"]
    )
    assert actual["sample_count"] == 3
    # The selected BaZi policy rolls the day at23h, so crossing midnight is
    # a clock-date regression, not evidence of two different day pillars.
    assert person.model_dump() == before
    assert person.birth_second == second


def test_omitted_and_explicit_zero_share_the_same_nominal_grid_calculation():
    ref = reference()
    a = module.analyze_birth_time_range(
        PersonInfo(**ref["birth_input"]), 1, analysis_moment=datetime(2026, 1, 1)
    )
    b = module.analyze_birth_time_range(
        PersonInfo(**ref["birth_input"], birth_second=0),
        1,
        analysis_moment=datetime(2026, 1, 1),
    )
    assert a == b


@pytest.mark.parametrize("second", [None, 0])
def test_discarded_seconds_cannot_invent_an_extra_hour_candidate(second, monkeypatch):
    path = FIXTURE.with_name("unknown-second-hour-transition.json")
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    ref = json.loads(path.read_text())
    person = PersonInfo(**ref["birth_input"], birth_second=second)
    seen = []
    original = module.normalize_birth_time

    def observe(sample, **kwargs):
        actual = original(sample, **kwargs)
        seen.append(actual)
        return actual

    monkeypatch.setattr(module, "normalize_birth_time", observe)
    result = module.analyze_birth_time_range(
        person, 1, analysis_moment=datetime(2026, 1, 1)
    )
    assert [
        n.input_datetime.astimezone(timezone.utc).isoformat() for n in seen[1:]
    ] == ref["expected_grid_utc"]
    assert seen[1].input_datetime.isoformat() == ref["expected_first_civil_clock"]
    assert (
        abs(
            (
                seen[1].corrected_datetime
                - datetime.fromisoformat(ref["expected_first_corrected_clock"])
            ).total_seconds()
        )
        <= ref["corrected_absolute_tolerance_seconds"]
    )
    assert len(result["pillars_candidates"]) == ref["expected_grid_candidate_count"]
    assert {r["pillars"]["hour"][-1] for r in result["pillars_candidates"]} == {
        ref["expected_hour_branch_on_all_grid_points"]
    }
    assert person.birth_second == second
