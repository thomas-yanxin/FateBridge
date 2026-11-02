"""Frozen two-clock comparison retains failed models and independent proofs."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_astrodice_receiver_clock import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-receiver-clock-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_frozen_original_inputs_plan_results_and_fixed_lines_are_unchanged():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "dd774393c148fb6e0dbf951c654e925db34b696ecbaabcff2bbf57b5a4180c31"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 311
    for name, expected in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    audit = load("first-audit.json")
    assert audit["original_position_arcsec"] == 0.02
    assert audit["original_daily_rate_arcsec_per_day"] == 0.002
    assert audit["production_acceptance_exit_code"] == 2
    assert audit["retained_overall_numeric_gate_exit_code"] == 1
    assert audit["new_frozen_TT_conditions"] == 4
    assert audit["candidate_calls"] == audit["new_candidate_holdouts"] == 0


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_direct_basis_endpoint_and_bit_lattice_replay_matches_first_receipt(cohort):
    assert verify(FIXTURE, cohort) == load(cohort + "-independent-replay-first.json")


def test_new_et_grid_agreement_never_replaces_failed_field_or_old_grid_rows():
    b = load("B-independent-replay-first.json")
    for group in b["groups"]:
        for models in group["profiles"].values():
            vector = models["vector_TT_source_epoch"]
            field = models["quantity30_current_leap_hold"]
            assert vector["primary"] == 4
            assert vector["continuous_overlap"] == 0
            assert vector["lattices"]["seconds_from_J2000_binary64"]["unique"] == 4
            assert vector["lattices"]["absolute_JD_binary64"]["refuted"] == 4
            assert field["primary"] == 4 and field["available"] == 3
            assert field["not_assessed_pre_1962"] == 1
            assert field["lattices"]["seconds_from_J2000_binary64"]["refuted"] == 3
    a = load("A-independent-replay-first.json")
    for group in a["groups"][1:]:
        for models in group["profiles"].values():
            assert (
                models["vector_TT_source_epoch"]["lattices"][
                    "seconds_from_J2000_binary64"
                ]["refuted"]
                == 1
            )
    assert (
        load("controls/B-independent-replay-first.json")["profiles"]["printing_only"][
            "TDB_state_six_not_refuted"
        ]
        == 11
    )


def test_unbracketed_old_8103_field_model_is_unknown_without_widening_the_search():
    old = next(
        row
        for row in load("A-first-analysis.json")["groups"][0]["rows"]
        if row["case_id"] == "seen-8103-center"
    )
    for models in old["profiles"].values():
        value = models["quantity30_current_leap_hold"]["inference"]
        assert value["status"] == "source_range_unbracketed"
        assert "lattices" not in value
    assert (
        load("plan-before-queries.json")["emission_search_radius_seconds"] == "1/1000"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "drop_group",
        "drop_row",
        "clock_shift",
        "qualify_field",
        "hide_failure",
        "unchecked_unknown",
        "lattice_count",
        "inverse_endpoint",
        "B_binding",
        "collector",
        "swap_receivers",
        "printed_field",
    ],
)
def test_independent_replay_rejects_model_score_scope_and_provenance_tampering(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    cohort = "B" if mutation in {"B_binding", "collector"} else "A"
    path = tmp_path / (cohort + "-first-analysis.json")
    data = load(path.name, tmp_path)
    row = next(
        r for r in data["groups"][0]["rows"] if r["role"] != "auxiliary_not_primary"
    )
    models = row["profiles"]["printing_only"]
    vector = models["vector_TT_source_epoch"]
    modern = (
        next(
            r for r in data["groups"][0]["rows"] if r["case_id"] == "seen-new-window-4"
        )
        if cohort == "A"
        else None
    )
    if mutation == "promote":
        data["full_goal_complete"] = True
    elif mutation == "drop_group":
        data["groups"].pop()
    elif mutation == "drop_row":
        data["groups"][0]["rows"].pop()
    elif mutation == "clock_shift":
        modern["profiles"]["printing_only"]["quantity30_current_leap_hold"][
            "calibration"
        ]["effective_JD"][0] = "0"
    elif mutation == "qualify_field":
        modern["profiles"]["printing_only"]["quantity30_current_leap_hold"][
            "calibration"
        ]["all_six_compatible"] = True
    elif mutation == "hide_failure":
        failed = next(
            r for r in data["groups"][1]["rows"] if r["case_id"] == "new-window-6"
        )
        failed["profiles"]["printing_only"]["vector_TT_source_epoch"]["inference"][
            "lattices"
        ]["seconds_from_J2000_binary64"]["unique_not_refuted"] = True
    elif mutation == "unchecked_unknown":
        vector["inference"]["status"] = "source_model_unknown"
    elif mutation == "lattice_count":
        vector["inference"]["lattices"]["seconds_from_J2000_binary64"][
            "points_in_effective_interval"
        ] += 1
    elif mutation == "inverse_endpoint":
        vector["inference"]["inverse"]["boundary_brackets_JD"][0][0] = "0"
    elif mutation in {"B_binding", "collector"}:
        p = tmp_path / "before-B-queries.json"
        before = load(p.name, tmp_path)
        before[
            "prior_A_analysis_sha256" if mutation == "B_binding" else "collector_sha256"
        ] = ("0" * 64)
        p.write_text(json.dumps(before))
    elif mutation == "swap_receivers":
        models["vector_TT_source_epoch"], models["quantity30_current_leap_hold"] = (
            models["quantity30_current_leap_hold"],
            models["vector_TT_source_epoch"],
        )
    else:
        row["TDB_minus_UT_seconds"] = "69.184000"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(tmp_path, cohort)
