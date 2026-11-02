"""Frozen rounding hypotheses retain narrow-tube and 8103 counterexamples."""

import hashlib
import json
import math
import shutil
from pathlib import Path

import pytest

from scripts.verify_astrodice_discrete_lt import check_candidate, verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-discrete-lt-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_raw_sources_old_failures_first_outputs_and_fixed_lines_remain_sealed():
    assert (
        sha(FIXTURE / "manifest.json")
        == "23dbae3b1479ca4ee6b0971db402abf9f4471db7dd687dda3836368fb961d962"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 129
    for name, digest in files.items():
        assert sha(FIXTURE / name) == digest
    a = load("first-audit.json")
    assert a["original_position_arcsec"] == 0.02
    assert a["original_daily_rate_arcsec_per_day"] == 0.002
    assert a["original_returned_label_match_budget_days"] == "1/1000000000"
    assert a["production_acceptance_exit_code"] == 2
    assert a["retained_overall_numeric_gate_exit_code"] == 1
    assert a["candidate_calls"] == a["new_candidate_holdouts"] == 0
    assert not a["full_goal_complete"]
    assert load("prior-leaf-binding.json")["not_a_relocated_full_prior_project"]
    assert load("prior-leaves/A-independent-first-process.json")["exit_code"] == 1
    assert (
        FIXTURE / "prior-leaves/A-independent-replay-first.json"
    ).read_bytes() == b""


@pytest.mark.parametrize(
    "cohort,steps,boxes,pairs", [("A", 336, 2100, 39), ("B", 240, 1500, 27)]
)
def test_independent_exact_source_rounding_cells_and_joint_proof(
    cohort, steps, boxes, pairs
):
    actual = verify(FIXTURE, cohort)
    assert actual == load(cohort + "-independent-replay-first.json")
    assert actual["joint_steps_checked"] == steps
    assert actual["source_boxes_checked"] == boxes
    assert actual["exact_grid_pairs_checked"] == pairs
    assert not actual["physical_time_model_certified"]


def test_queries_bind_fresh_dates_to_A_proof_without_model_adjustment():
    p = load("plan-before-queries.json")
    assert [c.get("nominal_calendar_TT") for c in p["cohorts"]["B"]][1:] == [
        "1431-03-18T00:22:22.891357",
        "3431-06-18T00:22:22.891357",
        "6431-09-18T00:22:22.891357",
        "9431-12-18T00:22:22.891357",
    ]
    assert p["new_requests_A"] == 0 and p["new_requests_B"] == 6
    before = load("before-B-open-binding.json")
    collected = load("before-B-queries.json")
    assert before["A_proof_sha256"] == sha(FIXTURE / "A-independent-replay-first.json")
    assert (
        before["A_analysis_sha256"]
        == collected["prior_A_analysis_sha256"]
        == sha(FIXTURE / "A-first-analysis.json")
    )
    assert (
        before["plan_sha256"]
        == collected["plan_sha256"]
        == sha(FIXTURE / "plan-before-queries.json")
    )
    assert collected["collector_sha256"] == sha(
        FIXTURE / "frozen-source/scripts/astrodice_vector_clock.py"
    )
    assert before["at_utc"] < collected["at_utc"]
    assert (
        not before["B_results_opened"] and not before["source_or_model_changed_after_A"]
    )
    receipts = load("B-collection.json")["receipts"]
    assert len(receipts) == 6 and all(
        r["status"] == 200 and r["attempt"] == 1 for r in receipts
    )


def test_both_coordinates_both_profiles_and_both_models_are_kept():
    for g in load("B-independent-replay-first.json")["groups"]:
        for profile, models in g["profiles"].items():
            assert set(models) == {
                "absolute_JD_binary64",
                "seconds_from_J2000_binary64",
            }
            absolute = models["absolute_JD_binary64"]
            assert (
                absolute["primary"] == 4
                and absolute["one_round_source_norm"]
                == absolute["two_round_source_norm"]
                == 0
            )
            et = models["seconds_from_J2000_binary64"]
            assert (
                et["primary"] == 4
                and et["input_family_unknown"] == et["enumeration_limit"] == 0
            )
            assert (
                et["one_round_source_norm"]
                == et["two_round_source_norm"]
                == et["source_vector_qualified"]
            )
            if profile == "printing_plus_64_ULP_hypothesis":
                assert (
                    et["one_round_source_norm"] == 4
                    and et["source_range_matches_observer"] == 3
                )
    assert not load("first-audit.json")["fixed_rounding_hypotheses_distinguished"]


def test_narrow_B_failures_include_encoding_specific_and_empty_grid_records():
    failed = []
    for g in load("B-first-analysis.json")["groups"]:
        for r in g["rows"]:
            if r["role"] == "auxiliary_not_primary":
                continue
            m = r["profiles"]["printing_only"]["models"]["seconds_from_J2000_binary64"]
            if m["conditional_refuted"]["one_round_source_norm"]:
                failed.append((g["encoding"], r["case_id"], len(m["candidates"])))
    assert failed == [
        ("JD", "discrete-new-window-4", 1),
        ("JD", "discrete-new-window-6", 0),
        ("MJD", "discrete-new-window-6", 0),
        ("CAL", "discrete-new-window-3", 1),
        ("CAL", "discrete-new-window-6", 0),
    ]


def test_8103_rate_failure_stays_failed_even_when_components_and_rounding_fit():
    for g in load("A-first-analysis.json")["groups"]:
        if g["id"] != "seen-8103-center":
            continue
        r = next(r for r in g["rows"] if r["case_id"] == "seen-8103-original-center")
        m = r["profiles"]["printing_plus_64_ULP_hypothesis"]["models"][
            "seconds_from_J2000_binary64"
        ]
        assert len(m["candidates"]) == 1
        c = m["candidates"][0]
        assert all(c["source_component_compatible"])
        assert c["source_range_compatible"]["vector_RG"]
        assert all(c["rounding_hypotheses"].values())
        assert not c["source_RR_matches_vector"] and not c["source_vector_qualified"]
        assert all(m["conditional_refuted"].values())


@pytest.mark.parametrize(
    "mutation", ["source", "joint", "A_binding", "drop_encoding", "scope"]
)
def test_independent_replay_rejects_provenance_scope_and_subset_tampering(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    if mutation == "source":
        p = tmp_path / "frozen-source/scripts/astrodice_discrete_lt.py"
        p.write_bytes(p.read_bytes() + b" ")
    elif mutation == "joint":
        p = tmp_path / "B-joint-first-analysis.json"
        p.write_bytes(p.read_bytes() + b" ")
    elif mutation == "A_binding":
        p = tmp_path / "before-B-open-binding.json"
        d = load(p.name, tmp_path)
        d["A_proof_sha256"] = "0" * 64
        p.write_text(json.dumps(d))
    else:
        p = tmp_path / "B-first-analysis.json"
        d = load(p.name, tmp_path)
        if mutation == "scope":
            d["full_goal_complete"] = True
        else:
            d["groups"].pop()
        p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        verify(tmp_path, "B")


@pytest.mark.parametrize(
    "mutation", ["rounded_LT", "source_state", "square", "physical_scope", "component"]
)
def test_exact_candidate_checker_rejects_arithmetic_or_predicate_changes(mutation):
    p = load("plan-before-queries.json")
    row = load("B-joint-first-analysis.json")["groups"][0]["rows"][1]
    r = load("B-first-analysis.json")["groups"][0]["rows"][1]
    c = r["profiles"]["printing_plus_64_ULP_hypothesis"]["models"][
        "seconds_from_J2000_binary64"
    ]["candidates"][0]
    case = next(k for k in p["cohorts"]["B"] if k["id"] == r["case_id"])
    if mutation == "rounded_LT":
        c["rounded_light_time_hex"] = math.nextafter(
            float.fromhex(c["rounded_light_time_hex"]), math.inf
        ).hex()
    elif mutation == "source_state":
        c["source_difference_AU_and_AU_per_day"][0] = "0"
    elif mutation == "square":
        c["squared_range_AU2"] = "0"
    elif mutation == "physical_scope":
        c["physical_or_internal_algorithm_certified"] = True
    else:
        c["source_component_compatible"][0] = False
    with pytest.raises(ValueError):
        check_candidate(
            FIXTURE / "source-records",
            case,
            row["vector"],
            row["observer"],
            64,
            "seconds_from_J2000_binary64",
            float.fromhex(c["reception_hex"]),
            float.fromhex(c["emission_hex"]),
            c,
        )
