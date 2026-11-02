"""Clock shifts cannot be hidden by a passing radial interval or subset."""

import copy
import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_geometric_rr import clock_proof, verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-geometric-rr-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_first_raw_outputs_failures_fixed_lines_and_adaptive_plans_are_sealed():
    assert (
        sha(FIXTURE / "manifest.json")
        == "f91d885b91d28f9f399e9e5b0a155559a3197ec24b9ac8cdf5d4df35d1b300ce"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 155
    for name, digest in files.items():
        assert sha(FIXTURE / name) == digest
    a = load("first-audit.json")
    assert (
        a["original_position_arcsec"] == 0.02
        and a["original_daily_rate_arcsec_per_day"] == 0.002
    )
    assert a["original_label_budget_days"] == "1/1000000000"
    assert (
        a["production_acceptance_exit_code"] == 2
        and a["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert (
        a["candidate_calls"] == a["new_candidate_holdouts"] == 0
        and not a["full_goal_complete"]
    )
    assert load("prior-leaves/original-A-proof-failure.json")["exit_code"] == 1
    assert (FIXTURE / "prior-leaves/original-A-proof-empty.json").read_bytes() == b""
    assert load("prior-leaf-binding.json")["not_a_relocated_full_prior_project"]


@pytest.mark.parametrize(
    "cohort,points,steps,boxes,parent_pairs",
    [("A", 24, 96, 600, 9), ("B", 64, 288, 1800, 33)],
)
def test_independent_raw_source_grid_and_radial_transfer_replay(
    cohort, points, steps, boxes, parent_pairs
):
    d = verify(FIXTURE, cohort)
    assert d == load(cohort + "-independent-replay-first.json")
    assert (
        d["clock_grid_candidates_checked"],
        d["joint_steps_checked"],
        d["source_boxes_checked"],
        d["exact_parent_grid_pairs_checked"],
    ) == (points, steps, boxes, parent_pairs)
    assert not d["refinement_rows"] and not d["physical_time_model_certified"]


def test_five_new_dates_and_every_query_stage_are_bound_without_model_change():
    p = load("plan-before-queries.json")
    assert [c.get("nominal_calendar_TT") for c in p["cohorts"]["B"]][1:] == [
        "1431-03-18T02:07:32.234791",
        "3431-06-18T02:07:32.234791",
        "6431-09-18T02:07:32.234791",
        "9431-12-18T02:07:32.234791",
        "8103-07-26T23:17:43.345791",
    ]
    binding = load("before-B-open-binding.json")
    assert not binding["B_results_opened"] and not binding["model_changed_after_A"]
    assert binding["A_proof_sha256"] == sha(FIXTURE / "A-independent-replay-first.json")
    assert binding["A_analysis_sha256"] == sha(FIXTURE / "A-first-analysis.json")
    assert binding["at_utc"] < load("before-B-queries.json")["at_utc"]
    for prefix, c in [("geometry-A/", "A"), ("", "B"), ("geometry-B/", "B")]:
        receipts = load(prefix + c + "-collection.json")["receipts"]
        assert len(receipts) == 6 and all(
            r["status"] == 200 and r["attempt"] == 1 for r in receipts
        )
    assert (
        sha(FIXTURE / "geometry-B/A-first-analysis.json")
        == binding["A_analysis_sha256"]
    )


def test_original_8103_explicit_geometry_clock_shifts_do_not_qualify_transfer():
    rows = load("A-geometric-clock-displacements.json")["rows"]
    wide = [r for r in rows if r["profile"] == "printing_plus_64_ULP_hypothesis"]
    expected = [
        Q(1, 16384),
        Q(-1, 16384),
        Q(1, 16384),
        Q(-1, 16384),
        Q(1, 16384),
        Q(1, 32768),
    ]
    assert [list(map(Q, r["match_minus_intended_seconds"])) for r in wide] == [
        [v] for v in expected
    ]
    for d in load("A-independent-replay-first.json")["profiles"].values():
        assert (
            d["primary"] == 3
            and d["transfer_qualified"] == d["geometric_state_and_RR_not_refuted"] == 0
        )
        assert (
            d["LT_printed_projection_RR_overlap"] == 3
            and d["exact_source_RR_matches_LT"] == 0
        )


def test_new_B_keeps_seven_qualified_records_and_eight_unqualified_records():
    p = load("B-independent-replay-first.json")["profiles"]
    wide = p["printing_plus_64_ULP_hypothesis"]
    narrow = p["printing_only"]
    assert wide["primary"] == narrow["primary"] == 15
    assert wide["transfer_qualified"] == wide["geometric_state_and_RR_not_refuted"] == 7
    assert (
        narrow["transfer_qualified"]
        == narrow["geometric_state_and_RR_not_refuted"]
        == 0
    )
    assert (
        wide["exact_source_RR_matches_LT"] == 12
        and narrow["exact_source_RR_matches_LT"] == 4
    )
    assert (
        wide["LT_printed_projection_RR_overlap"]
        == narrow["LT_printed_projection_RR_overlap"]
        == 15
    )


def test_new_8103_MJD_and_CAL_can_propagate_rounding_while_exact_RR_still_fails():
    rows = [
        t
        for t in load("B-first-analysis.json")["transfers"]
        if t["case_id"] == "geo-new-window-2"
    ]
    assert len(rows) == 3
    for t in rows:
        p = t["profiles"]["printing_plus_64_ULP_hypothesis"]
        assert not p["exact_source_RR_matches_LT"]
        assert p["qualified_geometric_state_and_RR_not_refuted"] == (
            t["LT_query"] != "B-LT-TT-JD"
        )
        assert not p["physical_or_internal_algorithm_certified"]


@pytest.mark.parametrize(
    "mutation", ["geometry_epoch", "source_stage", "A_binding", "scope"]
)
def test_source_epoch_adaptation_provenance_and_scope_tampering_is_rejected(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    if mutation == "geometry_epoch":
        p = tmp_path / "geometry-B/plan-before-queries.json"
        d = load("geometry-B/plan-before-queries.json", tmp_path)
        d["queries"][0]["cases"][1]["intended_ET_hex"] = "0x1p0"
        p.write_text(json.dumps(d))
    elif mutation == "source_stage":
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
        d["full_goal_complete"] = True
        p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        verify(tmp_path, "B")


@pytest.mark.parametrize(
    "mutation", ["grid", "axis", "indices", "source_state", "intended_green", "support"]
)
def test_monotone_source_grid_certificates_reject_missing_or_false_witnesses(mutation):
    plan = load("plan-before-queries.json")
    q = load("geometry-A/plan-before-queries.json")["queries"][0]
    case = q["cases"][1]
    row = load("A-first-analysis.json")["geometry"][0]["rows"][1]
    s = copy.deepcopy(row["profiles"]["printing_plus_64_ULP_hypothesis"])
    if mutation == "grid":
        s["grid_hex"].pop()
    elif mutation == "axis":
        s["axis"] = (s["axis"] + 1) % 3
    elif mutation == "indices":
        s["axis_indices"] = [0, 0]
    elif mutation == "source_state":
        s["candidates"][0]["source_state"][0] = "0"
    elif mutation == "intended_green":
        s["unique_at_intended_epoch"] = True
    else:
        s["support_JD"][0] = str(Q(s["support_JD"][0]) - Q(1, 86400))
    with pytest.raises(ValueError):
        clock_proof(
            FIXTURE / "source-records",
            case,
            row,
            "Earth",
            "printing_plus_64_ULP_hypothesis",
            s,
            plan,
        )


@pytest.mark.parametrize("mutation", ["transfer_green", "exact_RR_green"])
def test_unqualified_clock_or_exact_source_failure_cannot_be_promoted(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    p = tmp_path / "A-first-analysis.json"
    d = load(p.name, tmp_path)
    row = d["transfers"][0]["profiles"]["printing_plus_64_ULP_hypothesis"]
    if mutation == "transfer_green":
        row["conditional_transfer_qualified"] = True
    else:
        row["exact_source_RR_matches_LT"] = True
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        verify(tmp_path, "A")


def test_widened_diagnostic_cannot_hide_independent_RR_refutation(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    p = tmp_path / "A-first-analysis.json"
    d = load(p.name, tmp_path)
    row = d["transfers"][0]["profiles"]["printing_plus_64_ULP_hypothesis"]
    row["geometric_projection_RR"] = ["-1", "1"]
    row["geometric_projection_RR_overlap"] = True
    p.write_text(json.dumps(d))
    proof = verify(tmp_path, "A")
    assert proof["profiles"] == load("A-independent-replay-first.json")["profiles"]
    assert proof["refinement_rows"][0]["refinements"] == [
        {
            "field": "geometric.RR",
            "reported_not_refuted": True,
            "independently_refuted": True,
        }
    ]
