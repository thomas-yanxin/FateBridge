"""Frozen table disagreement switches encoding; no favorable-path selection."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_retarded_table import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-retarded-table-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_frozen_leaves_raw_tables_sources_failures_and_fixed_lines_are_unchanged():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "20d1773a579da98a0873bdf5061e61a6997920433b172698b73faad69de8b9c3"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 71
    for name, sha in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    a = load("first-audit.json")
    assert a["new_frozen_TT_conditions"] == 4
    assert a["candidate_calls"] == a["new_candidate_holdouts"] == 0
    assert (
        a["original_position_arcsec"] == 0.02
        and a["original_daily_rate_arcsec_per_day"] == 0.002
    )
    assert (
        a["production_acceptance_exit_code"] == 2
        and a["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert load("prior-source-binding.json")["not_a_relocated_full_prior_project"]


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_independent_raw_units_and_scalar_interval_replay(cohort):
    actual = verify(FIXTURE, cohort)
    assert actual == load(cohort + "-independent-replay-first.json")
    assert actual["scalar_enclosures_checked"] == 360


def test_failed_9431_jd_development_row_is_preserved_with_original_observation():
    group = load("A-first-analysis.json")["groups"][0]
    row = next(r for r in group["rows"] if r["vector"]["case_id"] == "B-clock-6")
    for p in row["profiles"].values():
        assert not p["checks"]["observer_range_matches_vector_RG"]
        assert Q(p["vector_minus_observer_range_meters"][1]) < 0
    old = load("prior-leaves/B-batch-bound-analysis.json")["transfers"][0]
    original = next(r for r in old["rows"] if r["case_id"] == "B-clock-6")
    assert original["range_AU"] == row["observer"]["range_AU"]
    for p in original["profiles"].values():
        assert p["common_clock"]["inference"]["lattices"][
            "seconds_from_J2000_binary64"
        ]["conditional_refuted"]


def test_new_holdouts_keep_mjd_and_calendar_failures_when_jd_agrees():
    data = load("B-first-analysis.json")
    for group in data["groups"]:
        row = next(
            r for r in group["rows"] if r["vector"]["case_id"] == "new-LT-window-6"
        )
        for p in row["profiles"].values():
            assert p["checks"]["observer_range_matches_vector_RG"] == (
                group["encoding"] == "JD"
            )
            assert p["checks"]["observer_range_matches_vector_position_norm"] == (
                group["encoding"] == "JD"
            )
            assert p["checks"]["observer_light_time_matches_vector_LT"]
            assert p["checks"]["observer_RR_matches_vector_RR"]
            if group["encoding"] != "JD":
                assert Q(p["vector_minus_observer_range_meters"][0]) > 0


def test_internal_lt_vector_algebra_and_coarse_observables_do_not_certify_range():
    for cohort in ["A", "B"]:
        for group in load(cohort + "-independent-replay-first.json")["groups"]:
            assert group["primary"] == 4
            for p in group["profiles"].values():
                for k in [
                    "vector_RG_matches_position_norm",
                    "vector_LT_matches_norm_over_c",
                    "vector_LT_matches_RG_over_c",
                    "vector_RR_matches_state_projection",
                    "observer_light_time_matches_vector_LT",
                    "observer_RR_matches_vector_RR",
                    "observer_RR_matches_state_projection",
                    "observer_direction_components_match_LT_vector",
                ]:
                    assert p[k] == 4


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "green_range",
        "wide_boxes_and_green",
        "rate_units",
        "drop_row",
        "cross_batch",
        "profile",
        "hide_error_status",
    ],
)
def test_independent_raw_replay_rejects_units_failures_scope_and_binding_tampering(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "A-first-analysis.json"
    data = load(path.name, tmp_path)
    row = next(
        r for r in data["groups"][0]["rows"] if r["vector"]["case_id"] == "B-clock-6"
    )
    p = row["profiles"]["printing_only"]
    if mutation == "promote":
        data["full_goal_complete"] = True
    elif mutation == "green_range":
        p["checks"]["observer_range_matches_vector_RG"] = True
    elif mutation == "wide_boxes_and_green":
        p["position_norm_AU"] = ["-1000", "1000"]
        p["vector_minus_observer_range_meters"] = ["-1000000", "1000000"]
        p["checks"]["observer_range_matches_vector_position_norm"] = True
    elif mutation == "rate_units":
        row["observer"]["deldot_km_per_second"] = row["vector"]["range_rate_AU_per_day"]
    elif mutation == "drop_row":
        data["groups"][0]["rows"].pop()
    elif mutation == "cross_batch":
        before = load("before-A-queries.json", tmp_path)
        before["plan_sha256"] = "0" * 64
        (tmp_path / "before-A-queries.json").write_text(json.dumps(before))
    elif mutation == "profile":
        row["profiles"].pop("printing_plus_64_ULP_hypothesis")
    else:
        data["groups"][0]["status"] = "unavailable_or_contract_unverified"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(tmp_path, "A")
