"""Frozen time-source evidence retains explicit refusal and clock mismatches."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_astrodice_observer_timescale import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-observer-timescale-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_frozen_source_failures_prior_scores_and_original_lines_remain_sealed():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "a0f59e762d027188869e895f2033088f7b1ef36800e7528d8b20dc8ac1cf0b79"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 167
    for name, expected in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert load("first-audit.json")["production_acceptance_exit_code"] == 2
    assert load("first-audit.json")["retained_overall_numeric_gate_exit_code"] == 1
    assert load("prior-emission-audit.json")["full_goal_complete"] is False
    assert (
        load("collector-preflight-semantic-diff.json")[
            "numerical_or_label_matching_code_changed"
        ]
        is False
    )
    assert len(load("first-source-attempt-failures.json")["attempts"]) == 2
    assert load("first-unit-fixture-failure.json")["failed"] == 1


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_full_wire_contract_and_clock_field_arithmetic_replay(cohort):
    actual = verify(FIXTURE, cohort)
    assert actual == load(cohort + "-independent-replay-first.json")
    assert actual["exact_clock_comparisons_replayed"] == (12 if cohort == "A" else 30)


def test_actual_refusal_and_conditional_unsent_requests_are_not_accepted_tables():
    raw = json.loads((FIXTURE / "responses/A-TDB-CAL.raw").read_bytes())
    assert raw["error"] == "Only UT or TT are allowed for observer table TIME_TYPE"
    assert (
        load("A-first-analysis.json")["TDB_OBSERVER_contract_status"]
        == "service_refused"
    )
    b = load("B-first-analysis.json")
    skipped = [
        q
        for q in b["observer_queries"]
        if q["status"] == "not_dispatched_A_contract_unverified"
    ]
    assert len(skipped) == 3
    for q in skipped:
        assert not (FIXTURE / "responses" / (q["id"] + ".raw")).exists()
    assert load("first-audit.json")["new_frozen_timescale_conditions"] == 4
    assert load("first-audit.json")["candidate_calls"] == 0


def test_both_profiles_keep_modern_mismatches_ancient_unknowns_and_state_failure():
    data = load("B-independent-replay-first.json")
    for name, p in data["profiles"].items():
        assert p["primary_rows"] == 12 and p["conditional_model_assessed"] == 9
        assert p["not_assessed_pre_1962"] == 3
        assert p["overlap_nominal_state"] == p["overlap_paired_state"] == 0
        assert p["TT_state_six_not_refuted"] == 12
        assert p["TDB_state_six_not_refuted"] == (11 if name == "printing_only" else 12)
    assert not data["TT_OBSERVER_vector_clock_equivalence_certified"]


def test_web_excerpt_never_gets_a_raw_download_checksum_or_future_utc_claim():
    source = load("tai-utc-source.json")
    assert source["original_raw_download_available"] is False
    assert source["original_raw_sha256"] is None
    assert source["future_UTC_certified"] is False
    assert source["observed_TAI_minus_UTC_seconds"] == "37.0"


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "delta_value",
        "mask_mismatch",
        "drop_clock",
        "drop_observer",
        "modernize_ancient",
        "branch",
        "raw_claim",
        "label_budget",
        "field_certification",
    ],
)
def test_replay_rejects_altered_clock_scope_or_hidden_failures(tmp_path, mutation):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    cohort = "B" if mutation == "branch" else "A"
    path = tmp_path / (cohort + "-first-analysis.json")
    data = load(path.name, tmp_path)
    if mutation == "promote":
        data["TT_OBSERVER_vector_clock_equivalence_certified"] = True
    elif mutation == "delta_value":
        q = next(q for q in data["observer_queries"] if q["status"] == "supported")
        q["rows"][1]["TDB_minus_UT_seconds"] = "69.184000"
    elif mutation == "mask_mismatch":
        row = next(
            r
            for r in data["clock_rows"]
            if r["profiles"]["printing_only"]["status"]
            == "conditional_leap_hold_comparison"
        )
        row["profiles"]["printing_only"]["overlap_nominal_state"] = True
    elif mutation == "drop_clock":
        data["clock_rows"].pop()
    elif mutation == "drop_observer":
        next(q for q in data["observer_queries"] if q["status"] == "supported")[
            "rows"
        ].pop()
    elif mutation == "modernize_ancient":
        data["clock_rows"][0]["profiles"]["printing_only"][
            "status"
        ] = "conditional_leap_hold_comparison"
    elif mutation == "branch":
        q = next(
            q
            for q in data["observer_queries"]
            if q["status"] == "not_dispatched_A_contract_unverified"
        )
        q["status"] = "supported"
    elif mutation == "raw_claim":
        p = tmp_path / "tai-utc-source.json"
        source = load(p.name, tmp_path)
        source["original_raw_download_available"] = True
        p.write_text(json.dumps(source))
    elif mutation == "label_budget":
        p = tmp_path / "plan-before-queries.json"
        plan = load(p.name, tmp_path)
        plan["returned_label_match_budget_days"] = "1"
        p.write_text(json.dumps(plan))
    else:
        row = next(
            r
            for r in data["clock_rows"]
            if r["profiles"]["printing_only"]["status"]
            == "conditional_leap_hold_comparison"
        )
        row["profiles"]["printing_only"][
            "time_field_is_internal_clock_bound_certified"
        ] = True
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(tmp_path, cohort)
