"""Reference conversion/parser and anti-fitting interval comparison controls."""

import copy
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.validation import guolao_phase_reference as subject

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-nasa-phase-reference-v1"


def test_original_reference_bytes_and_precomparison_subset_pinned():
    ref = json.loads((FIXTURE / "reference.json").read_text())
    for row in ref["artifacts"]:
        raw = (FIXTURE / row["path"]).read_bytes()
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert (
        hashlib.sha256(subject.DATA.read_bytes()).hexdigest()
        == ref["reference_subset_sha256"]
    )
    assert (
        subject.DATA.read_bytes()
        == (FIXTURE / "reference-subset-before-comparison.json").read_bytes()
    )
    assert (
        ref["comparison_policy_sha256"]
        == "b6c10ecb3861ee59383c21c97e21e7e15fc6e4d1e57bff2b4bbb3024c5cb372d"
    )


@pytest.mark.parametrize(
    "date,calendar,expected",
    [
        ((2000, 1, 1, 12, 0), "gregorian", F(2451545)),
        ((1970, 1, 1, 0, 0), "gregorian", F("2440587.5")),
        ((1582, 10, 4, 0, 0), "julian", F("2299159.5")),
        ((1582, 10, 15, 0, 0), "gregorian", F("2299160.5")),
    ],
)
def test_independent_jd_anchors_and_hybrid_reform_continuity(date, calendar, expected):
    assert subject.calendar_jd(*date, calendar=calendar) == expected


def test_julian_century_leap_is_kept_and_gregorian_century_nonleap_rejected():
    assert (
        subject.calendar_jd(1300, 3, 1, calendar="julian")
        - subject.calendar_jd(1300, 2, 29, calendar="julian")
        == 1
    )
    with pytest.raises(ValueError):
        subject.calendar_jd(1300, 2, 29, calendar="gregorian")
    with pytest.raises(ValueError):
        subject.calendar_jd(1900, 2, 29, calendar="gregorian")


@pytest.mark.parametrize(
    "start,count",
    [(1201, 4947), (1301, 4948), (1401, 4947), (1501, 4946), (1601, 4947)],
)
def test_every_published_century_cell_is_parsed_instead_of_selecting_favorable_rows(
    start, count
):
    result = subject.parse_nasa_century(
        (FIXTURE / f"nasa-phases{start}.html").read_bytes(), start
    )
    assert len(result["events"]) == count
    assert len(result["delta_t_minutes_by_year"]) == 100
    if start == 1301:
        row = next(
            r for r in result["events"] if r["event_id"] == "1301-01-10T23:37:new_moon"
        )
        assert row["calendar"] == "julian"
        assert (row["year"], row["month"], row["day"], row["hour"], row["minute"]) == (
            1301,
            1,
            10,
            23,
            37,
        )
        assert result["delta_t_minutes_by_year"]["1301"] == 8


@pytest.mark.parametrize(
    "old,new",
    [
        (b"Jan  6  15:25 P", b"Jan  6  25:25 P"),
        (b"Jan  6  15:25 P", b"Foo  6  15:25 P"),
        (b"Jan  6  15:25 P", b"              "),
        (b"00h12m", b"unknown"),
    ],
)
def test_malformed_missing_or_wrong_units_reference_cells_do_not_get_filled(old, new):
    raw = (FIXTURE / "nasa-phases1201.html").read_bytes()
    assert old in raw
    raw = raw.replace(old, new, 1)
    with pytest.raises(ValueError):
        subject.parse_nasa_century(raw, 1201)


@pytest.fixture
def synthetic(monkeypatch):
    events = [
        {
            "event_id": f"ref{i}",
            "phase_kind": subject.KINDS[i % 4],
            "jd_ut_exact": str(F(990) + F(15, 2) * i),
            "calendar": "julian",
        }
        for i in range(84)
    ]
    reference = {
        "source_elapsed_years": [0],
        "delta_t_minutes_by_year": {"1280": 0},
        "events": events,
    }
    state = {
        "common_shift": F(),
        "missing": set(),
        "mean_gap": F(10),
        "winter": F(1000),
        "per_index_shift": {},
    }

    def anchor(*_):
        return {
            "approximate_ut_jd_exact": str(state["winter"]),
            "backend": "synthetic_only",
        }

    def phase(_, index):
        return {
            "phase_kind": subject.KINDS[index % 4],
            "mean_phase_offset_from_winter_days_exact": str(-state["mean_gap"]),
            "research_phase_offset_from_winter_days_exact": (
                None
                if index in state["missing"]
                else str(
                    F(-10)
                    + F(15, 2) * index
                    + state["common_shift"]
                    + state["per_index_shift"].get(index, F())
                )
            ),
        }

    monkeypatch.setattr(subject, "winter_anchor", anchor)
    monkeypatch.setattr(subject, "source_lunar_phase", phase)
    return reference, state


def test_anchor_zero_is_not_counted_and_exact_interval_agreement_is_not_absolute_validation(
    synthetic,
):
    ref, _ = synthetic
    result = subject.compare_phase_intervals(ref, 0)
    assert result["status_counts"] == {
        "anchor_excluded_from_interval_statistics": 1,
        "interval_residual_measured": 71,
    }
    assert result["rows"][0]["residual_minutes_exact"] is None
    assert result["descriptive_residuals"]["maximum_absolute_minutes"] == "0.000000"
    assert not result["physical_absolute_phase_time_validated"]
    assert not result["absolute_source_epoch_fitted_or_calibrated"]


def test_any_common_absolute_source_shift_cancels_and_remains_unvalidated(synthetic):
    ref, state = synthetic
    initial = subject.compare_phase_intervals(ref, 0)
    state["common_shift"] = F("123.456")
    shifted = subject.compare_phase_intervals(ref, 0)
    assert initial["descriptive_residuals"] == shifted["descriptive_residuals"]
    assert (
        shifted["rows"][1]["source_phase_offset_days_exact"]
        != initial["rows"][1]["source_phase_offset_days_exact"]
    )
    assert not shifted["absolute_source_epoch_fitted_or_calibrated"]


def test_missing_source_time_preserved_without_reference_or_mean_replacement(synthetic):
    ref, state = synthetic
    state["missing"] = {6}
    result = subject.compare_phase_intervals(ref, 0)
    assert len(result["rows"]) == 72
    assert result["source_unavailable_phase_indices_independent_of_alignment"] == [6]
    assert result["rows"][6]["source_phase_offset_days_exact"] is None
    assert result["rows"][6]["residual_minutes_exact"] is None
    assert result["descriptive_residuals"]["compared_intervals"] == 70


@pytest.mark.parametrize("field,value", [("mean_gap", F(1)), ("winter", F(991))])
def test_unresolved_alignment_never_selects_another_cycle_to_get_a_match(
    synthetic, field, value
):
    ref, state = synthetic
    state[field] = value
    state["missing"] = {6}
    result = subject.compare_phase_intervals(ref, 0)
    assert not result["cycle_alignment_resolved_under_declared_policy"]
    assert result["descriptive_residuals"] is None
    assert result["reference_new_moon_before_winter"] == "ref0"
    assert len(result["rows"]) == 72
    assert result["source_unavailable_phase_indices_independent_of_alignment"] == [6]


def test_incomplete_reference_chain_is_not_joined_across_a_missing_month(synthetic):
    ref, _ = synthetic
    ref = copy.deepcopy(ref)
    del ref["events"][8:12]
    with pytest.raises(ValueError):
        subject.compare_phase_intervals(ref, 0)


def test_non_declared_year_is_not_accepted_after_inspecting_fit(synthetic):
    ref, _ = synthetic
    with pytest.raises(ValueError):
        subject.compare_phase_intervals(ref, 1)


def test_unfavorable_phase_residual_kept_with_sign_and_without_a_fitted_threshold(
    synthetic,
):
    ref, state = synthetic
    state["per_index_shift"] = {3: F(1, 10)}
    result = subject.compare_phase_intervals(ref, 0)
    assert result["rows"][3]["residual_minutes_exact"] == "144"
    assert result["rows"][3]["residual_minutes_display"] == "144.000000"
    assert result["descriptive_residuals"]["maximum_absolute_minutes"] == "144.000000"
    assert result["descriptive_residuals"]["compared_intervals"] == 71
    assert not result["physical_absolute_phase_time_validated"]


def test_missing_source_anchor_does_not_turn_other_available_times_into_individual_gaps(
    synthetic,
):
    ref, state = synthetic
    state["missing"] = {0}
    result = subject.compare_phase_intervals(ref, 0)
    assert result["source_unavailable_phase_indices_independent_of_alignment"] == [0]
    assert result["rows"][1]["source_phase_time_available"]
    assert not result["rows"][1]["source_anchor_time_available"]
    assert result["rows"][1]["status"] == "source_anchor_time_unavailable"
    assert result["descriptive_residuals"] is None


def test_all_declared_source_slots_and_adverse_phase_residuals_remain_visible():
    result = subject.audit_phase_reference()
    assert result["declared_cases"] == 17
    assert result["declared_positions"] == 1224
    assert result["planned_nonanchor_interval_positions"] == 1207
    assert result["counts"] == {
        "anchor_excluded_from_interval_statistics": 17,
        "cycle_alignment_unresolved": 70,
        "interval_residual_measured": 1126,
        "source_time_unavailable": 11,
    }
    assert result["source_time_unavailable_independent_of_alignment"] == 11
    unresolved = [
        c["elapsed_years"]
        for c in result["cases"]
        if not c["cycle_alignment_resolved_under_declared_policy"]
    ]
    assert unresolved == [362]
    counts = {
        k: v["sample_count"]
        for k, v in result["descriptive_interval_residuals_by_phase_minutes"].items()
    }
    assert counts == {
        "new_moon": 270,
        "first_quarter": 285,
        "full_moon": 285,
        "last_quarter": 286,
    }
    assert result["retrospectively_fitted_pass_tolerance"] is None
    assert not result["physical_absolute_phase_time_validated"]
    assert result["real_world_prediction_subjects"] == 0


def test_modern_full_window_reference_coverage_is_not_a_physical_pass_rate():
    result = subject.audit_modern_phase_reference()
    assert result["merged_windows"] == 14
    assert result["compared_unique_events"] == result["reference_unique_events"] == 1302
    assert result["unresolved_windows"] == 0
    assert sum(len(c["rows"]) for c in result["cases"]) == 1302
    assert all(c["computed_count"] == c["reference_count"] for c in result["cases"])
    assert result["retrospectively_fitted_pass_tolerance"] is None
    assert result["same_reference_previously_used_for_source_diagnosis"]
    assert not result["unseen_holdout_claimed"]
    assert not result["direct_observations"]
    assert result["real_world_prediction_subjects"] == 0


def test_modern_sequence_mismatch_preserves_both_lists_without_best_fit_matching(
    monkeypatch,
):
    from fatebridge.core import lunar_phase_events

    monkeypatch.setattr(
        lunar_phase_events,
        "phase_events_tt",
        lambda a, b: {
            "events": [{"phase_kind": "full_moon", "julian_day_tt_exact": str(F(a))}]
        },
    )
    result = subject.audit_modern_phase_reference()
    assert result["unresolved_windows"] == result["merged_windows"] == 14
    assert result["compared_unique_events"] == 0
    assert all(
        v is None
        for v in result[
            "descriptive_absolute_event_residuals_by_phase_minutes"
        ].values()
    )
    assert sum(len(c["unmatched_reference_events"]) for c in result["cases"]) == 1302
    assert sum(len(c["unmatched_computed_events"]) for c in result["cases"]) == 14
    assert all(not c["rows"] for c in result["cases"])
