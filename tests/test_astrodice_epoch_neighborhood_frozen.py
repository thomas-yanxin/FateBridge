"""Keep unavailable B rows, collapsed batches and successful TT controls apart."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.audit_astrodice_epoch_isolation import audit as audit_isolation
from scripts.audit_astrodice_epoch_neighborhood import audit
from scripts.verify_astrodice_epoch_neighborhood import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-epoch-neighborhood-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_raw_first_failures_original_code_plans_and_fixed_lines_are_sealed():
    assert (
        sha(FIXTURE / "manifest.json")
        == "e70e75d1a189c81cf235391f4c5436e74c160d8127d412dd63e69f41daf93d85"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 337
    for name, digest in files.items():
        assert sha(FIXTURE / name) == digest
    a = load("first-audit.json")
    assert a["total_requests"] == 40 and a["original_HTTP502_unavailable"] == 5
    assert (
        a["original_position_arcsec"] == 0.02
        and a["original_daily_rate_arcsec_per_day"] == 0.002
    )
    assert a["original_label_budget_days"] == "1/1000000000"
    assert (
        a["production_acceptance_exit_code"] == 2
        and a["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert a["new_TT_source_conditions"] == a["new_candidate_holdouts"] == 0
    assert (
        not a["overall_frozen_neighborhood_acceptance"] and not a["full_goal_complete"]
    )


def test_independent_A_source_grid_and_Hall_label_replay():
    d = verify(FIXTURE, "A")
    assert d == load("A-independent-replay-first.json")
    assert d["clock_candidates_checked"] == 120
    for p in d["profiles"].values():
        assert p["primary_target_groups"] == 6
        assert (
            p["target_observed_groups"]
            == p["qualified_target_groups"]
            == p["label_matching_groups"]
            == 0
        )


def test_strict_B_failure_is_not_replaced_by_a_passing_subset_or_empty_result():
    receipt = load("B-analysis-first-process.json")
    assert (
        receipt["exit_code"] == 1
        and "Unavailable or changed neighborhood response" in receipt["stderr"]
    )
    assert not (FIXTURE / "B-first-analysis.json").exists()
    assert not (FIXTURE / "B-independent-replay-first.json").exists()
    with pytest.raises(FileNotFoundError):
        verify(FIXTURE, "B")


def test_posthoc_population_and_source_diagnostics_replay_without_regrading():
    d = audit(FIXTURE)
    assert d == load("posthoc-transport-population-audit.json")
    assert sum(q["availability"] == "HTTP_unavailable" for q in d["cohorts"]["B"]) == 5
    assert sum(q["availability"] == "valid_table" for q in d["cohorts"]["B"]) == 13
    assert d["B_independent_numerical_acceptance"] == "not_tested"
    assert (
        d["original_B_analysis_exit_code"] == 1
        and not d["overall_frozen_neighborhood_acceptance"]
    )


def test_isolated_complete_grid_and_same_TT_controls_replay():
    d = audit_isolation(FIXTURE)
    assert d == load("posthoc-isolated-and-TT-audit.json")
    assert len(d["isolated_original_grid"]) == 9
    assert (
        d["original_A_B_scores_unchanged"]
        and not d["overall_frozen_neighborhood_acceptance"]
    )


def test_all_nine_original_batch_rows_stay_visible_when_their_states_are_equal():
    for q in load("posthoc-transport-population-audit.json")["cohorts"]["A"]:
        g = next(g for g in q["groups"] if g["role"] != "auxiliary_not_primary")
        assert g["distinct_requested_epochs"] == g["returned_rows"] == 9
        assert g["distinct_printed_epochs"] == g["distinct_printed_states"] == 1
        assert len(g["all_raw_rows"]) == 9 and not g["complete_label_matching"]


def test_space_and_comma_do_not_restore_this_batch_and_single_inputs_differ():
    queries = load("posthoc-transport-population-audit.json")["development_controls"]
    separators = [q for q in queries if q["comparison"] == "separator_only"]
    assert len(separators) == 4
    for q in separators:
        g = next(g for g in q["groups"] if g["role"] != "auxiliary_not_primary")
        assert (
            g["returned_rows"] == 9
            and g["distinct_printed_states"] == 1
            and not g["complete_label_matching"]
        )
    singles = [
        q
        for q in queries
        if q["comparison"] == "one_primary_epoch_with_original_auxiliary"
    ]
    states = []
    for q in singles:
        g = next(g for g in q["groups"] if g["role"] != "auxiliary_not_primary")
        assert g["returned_rows"] == 1 and g["complete_label_matching"]
        states.append(tuple(g["all_raw_rows"][0]["printed_state"]))
    assert len(set(states)) == 3


def test_all_original_isolated_offsets_are_tested_and_scope_stays_finite():
    rows = load("posthoc-isolated-and-TT-audit.json")["isolated_original_grid"]
    assert [r["input_ET_ULP_offset"] for r in rows] == list(range(-4, 5))
    actual = [
        list(
            map(
                Q,
                r["profiles"]["printing_plus_64_ULP_hypothesis"][
                    "match_minus_intended_seconds"
                ],
            )
        )
        for r in rows
    ]
    assert actual == [
        [v]
        for v in [
            Q(-5, 32768),
            Q(-1, 16384),
            Q(-1, 16384),
            Q(1, 16384),
            Q(1, 16384),
            Q(1, 16384),
            Q(5, 32768),
            Q(5, 32768),
            Q(5, 32768),
        ]
    ]
    assert all(
        not r["profiles"]["printing_plus_64_ULP_hypothesis"]["target_observed"]
        for r in rows
    )
    assert len({tuple(v) for v in actual}) == 4


def test_TT_input_labels_and_TDB_source_targets_remain_separate():
    controls = [
        q
        for q in load("posthoc-isolated-and-TT-audit.json")["additional_controls"]
        if q.get("input_scale") == "TT"
    ]
    assert len(controls) == 3
    for q in controls:
        assert q["source_scale"] == "TDB" and q["same_original_TT_time_batch"]
        row = q["rows"][0]
        delta = (
            Q(row["TDB_source_target"]["nominal_JD"])
            - Q(row["TT_input_row"]["nominal_JD"])
        ) * 86400
        assert Q(1, 1000) < delta < Q(2, 1000)
        assert row["TT_input_row"]["original_label_budget_pass"]
        assert row["profiles"]["printing_plus_64_ULP_hypothesis"]["clock"][
            "unique_at_intended_epoch"
        ]
        assert not row["profiles"]["printing_only"]["clock"]["unique_at_intended_epoch"]
        assert not row["profiles"]["printing_plus_64_ULP_hypothesis"]["clock"][
            "physical_time_model_certified"
        ]


def test_label_bijection_does_not_certify_independent_source_time_samples():
    queries = load("posthoc-transport-population-audit.json")["cohorts"]["B"]
    examples = [
        g
        for q in queries
        for g in q["groups"]
        if g["role"] != "auxiliary_not_primary"
        and g["complete_label_matching"]
        and g["distinct_printed_states"] == 1
    ]
    assert examples and all(g["distinct_requested_epochs"] == 9 for g in examples)
    assert all(
        q["numeric_result"] in {"not_assessed", "population_diagnostic_only"}
        for q in queries
    )


@pytest.mark.parametrize(
    "mutation", ["drop_row", "frame_override", "scope", "B_query_plan"]
)
def test_independent_A_replay_rejects_population_frame_scope_and_query_tampering(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    if mutation == "B_query_plan":
        p = tmp_path / "geometry-B/plan-before-queries.json"
        d = load("geometry-B/plan-before-queries.json", tmp_path)
        d["queries"].pop()
    else:
        p = tmp_path / "A-first-analysis.json"
        d = load(p.name, tmp_path)
        if mutation == "drop_row":
            d["queries"][0]["groups"][1]["rows"].pop()
        elif mutation == "frame_override":
            d["queries"][0]["groups"][1]["rows"][0]["profiles"][
                "printing_plus_64_ULP_hypothesis"
            ]["grid_hex"] = []
        else:
            d["full_goal_complete"] = True
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        verify(tmp_path, "A")


def test_posthoc_auditor_refuses_an_invented_B_numerical_result(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    (tmp_path / "B-first-analysis.json").write_text("{}")
    with pytest.raises(ValueError, match="Original B failure"):
        audit(tmp_path)


def test_HTTP200_label_does_not_launder_an_error_HTML_into_a_valid_table(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    path = next(
        p
        for p in (tmp_path / "geometry-B/responses").glob("*.receipt.json")
        if json.loads(p.read_text())["status"] == 502
    )
    data = json.loads(path.read_text())
    data["status"] = 200
    path.write_text(json.dumps(data))
    result = audit(tmp_path)
    q = next(q for q in result["cohorts"]["B"] if q["id"] == data["id"])
    assert (
        q["availability"] == "invalid_table" and q["numeric_result"] == "not_assessed"
    )
    assert not result["overall_frozen_neighborhood_acceptance"]
