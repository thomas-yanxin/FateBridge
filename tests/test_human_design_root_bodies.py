"""Frozen public-second counterexamples, complete root replay and raw controls."""

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design_native_positions import (
    decode_native_positions,
    pack_native_positions,
)
from fatebridge.core.human_design_root_bodies import (
    derive_root_body_assessment,
    root_body_summary,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_solar_root import verify_solar_root_context

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "tests/fixtures/human-design-root-body-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
BEFORE_PATH = ROOT / "docs/validation/human-design-root-body-before.json"
BEFORE = json.loads(BEFORE_PATH.read_text())
LINUX_BEFORE_PATH = (
    ROOT / "tests/fixtures/human-design-root-body-linux-1.31-baseline.json"
)
LINUX_BEFORE = json.loads(LINUX_BEFORE_PATH.read_text())
# Raw native floats are platform-bound, as are the repository's Linux golden
# locks. The Linux baseline was captured from the actual OLD1.31wheel in that
# runtime, independently of the NEW producer. Both captures remain immutable.
NATIVE_BEFORE = LINUX_BEFORE if sys.platform == "linux" else BEFORE
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Verification called a native producer")


def rehash(run):
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    return run


def test_before_cases_and_acceptance_thresholds_stay_frozen():
    assert (
        hashlib.sha256(BEFORE_PATH.read_bytes()).hexdigest()
        == "4a8216de9d70c0a35a2f15b948ae9bc12cf515bf4e97d72b1c1dcd60c41fddd3"
    )
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "dd02d66b4cba690c521de79a2c6fe945a609cf936a728fffedb1e7dfab6387ac"
    )
    assert (
        hashlib.sha256(LINUX_BEFORE_PATH.read_bytes()).hexdigest()
        == "c6a18e33ab46ba62d21aba966e81b2eb01dc0abbcf2dd71b3b1ae419086b58bb"
    )
    assert LINUX_BEFORE["old_ruleset"] == "1.31.0"
    assert (
        LINUX_BEFORE["old_wheel_sha256"]
        == "9150b51acaafe407c4206655d1bf4213a3c0be5f8ff068e964ff56da524c6218"
    )
    assert [c["input"] for c in LINUX_BEFORE["cases"]] == [
        c["input"] for c in BEFORE["cases"]
    ]
    assert len(PLAN["cases"]) == len(BEFORE["cases"]) == 7
    assert sum(c["mechanics_changed"] for c in BEFORE["cases"]) == 3
    assert all(
        c["old_complete_verification"]["status"] == "verified_fixed_template_reading"
        for c in BEFORE["cases"]
    )
    assert all(
        c["original_solver"]["numerical_precision"][
            "other_bodies_bracket_sensitivity_assessed"
        ]
        is False
        for c in BEFORE["cases"]
    )
    assert PLAN["unchanged_thresholds"] == {
        "astronomy_arcsec": 2.0,
        "physical_design_root_seconds": 5.0,
        "clock_seconds": 0.0002,
    }


@pytest.mark.parametrize("mode", PLAN["required_modes"])
@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_every_frozen_public_second_on_both_conventions_and_backends(
    case, empty_files, mode, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(SPEC, SPEC.request_model(**case["input"], node_mode=mode))
    proof = run["design_solver"]["numerical_precision"][
        "design_body_endpoint_assessment"
    ]
    assert proof["node_mode"] == mode
    assert proof["evaluated_tt_count"] in (1, 2)
    assert proof["continuous_interval_stability_certified"] is False
    assert proof["physical_time_accuracy_certified"] is False
    assert run["validation"]["all_three_axes_full_marks"] is False
    if not empty_files and mode == "true":
        before = next(c for c in BEFORE["cases"] if c["id"] == case["id"])
        native_before = next(c for c in NATIVE_BEFORE["cases"] if c["id"] == case["id"])
        assert native_before["input"] == before["input"]
        assert (
            run["activations"]["personality"] == native_before["original_personality"]
        )
        assert run["activations"]["design"] == native_before["original_selected_design"]
        assert run["bodygraph"] == before["original_selected_graph"]
        assert {
            k: v for k, v in run["variables"].items() if k != "personality_colors"
        } == before["original_variables"]
        for row, original in zip(
            proof["observed_activation_changes"],
            case["Swiss_true_node_expected_changes"],
        ):
            assert row["body"] == original["body"]
            assert row["levels"] == original["levels"]
            for level in original["levels"]:
                assert row["lower"][level] == original["lower"][level]
                assert row["upper"][level] == original["upper"][level]
        assert len(proof["observed_activation_changes"]) == len(
            case["Swiss_true_node_expected_changes"]
        )
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        case = PLAN["cases"][2]
        return execute_tool(
            SPEC, SPEC.request_model(**case["input"], birth_time_uncertainty_minutes=1)
        )


def test_complete_sample_roots_and_subtype_difference_are_preserved(
    complete, monkeypatch
):
    proof = complete["design_solver"]["numerical_precision"][
        "design_body_endpoint_assessment"
    ]
    assert [r["subtype"] for r in proof["endpoint_structures"]] == [
        "pure_generator",
        "manifesting_generator",
    ]
    assert "subtype" in proof["observed_structure_changed_fields"]
    assert "子型" in complete["interpretation"]["design_time_precision_meaning"]
    samples = complete["time_sensitivity"]["evaluation_witnesses"]["samples"]
    assert len(samples) >= 13
    assert all("design_solver" in row for row in samples)
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    check = verify_human_design_reading(complete)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.mark.parametrize("bad", PLAN["required_negative_receipts"])
def test_all_preregistered_rehashed_corruptions_fail(complete, monkeypatch, bad):
    run = deepcopy(complete)
    s = run["design_solver"]
    p = s["numerical_precision"]["design_body_endpoint_assessment"]
    other = next(e for e in p["evaluations"] if e["jd_tt"] != s["design_jd_tt"])
    if bad == "missing_endpoint":
        p["evaluations"].remove(other)
    elif bad == "wrong_epoch":
        other["jd_tt"] += 0.01
    elif bad == "changed_native_flag":
        other["native_positions"][1][2] |= 2048
    elif bad == "changed_derived_body":
        other["native_positions"].append([0.0, 1.0, 258])
    elif bad == "changed_gate_or_subdivision":
        p["observed_activation_changes"][0]["lower"]["gate"] = 63
    elif bad == "wrong_structure":
        p["endpoint_structures"][0]["authority"] = "invented"
    elif bad == "changed_personality_basis":
        run["activations"]["personality"][1]["gate"] = 63
    elif bad == "changed_selected_native_position":
        p["evaluations"][p["selected_evaluation_index"]]["native_positions"][1][
            0
        ] += 0.1
    elif bad == "forged_scope_or_certificate":
        p["continuous_interval_stability_certified"] = True
    else:
        sample = next(
            r
            for r in run["time_sensitivity"]["evaluation_witnesses"]["samples"]
            if r["birth_utc"] != run["birth_utc"]
        )
        if bad == "missing_sample_solver":
            del sample["design_solver"]
        else:
            sample["design_solver"]["numerical_precision"][
                "design_body_endpoint_assessment"
            ]["evaluations"][0]["jd_tt"] += 0.01
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    assert verify_human_design_reading(rehash(run))["status"] == "rejected"


def test_derived_bodies_and_selected_epoch_are_exact_and_replayable(complete):
    chart = complete
    s = chart["design_solver"]
    proof = s["numerical_precision"]["design_body_endpoint_assessment"]
    rebuilt = derive_root_body_assessment(
        s,
        chart["activations"]["personality"],
        chart["activations"]["design"],
        "true",
        proof["evaluations"],
        require_swiss_files=False,
    )
    assert rebuilt == proof
    selected = proof["evaluations"][proof["selected_evaluation_index"]]
    assert selected["native_positions"] == pack_native_positions(
        chart["activations"]["design"]
    )
    assert (
        decode_native_positions(
            selected["native_positions"], "true", require_swiss_files=False
        )
        == chart["activations"]["design"]
    )
    assert (
        root_body_summary(rebuilt)
        == s["numerical_precision"]["design_body_endpoint_summary"]
    )
    assert not verify_solar_root_context(chart)["errors"]


def test_singleton_endpoint_layout_does_not_invent_a_second_evaluation(complete):
    # Pure layout oracle; this does not assert an exact astronomical root.
    s = deepcopy(complete["design_solver"])
    root = s["numerical_precision"]
    root["lower"] = root["upper"] = deepcopy(root["selected"])
    evaluation = {
        "jd_tt": s["design_jd_tt"],
        "source_role": "activation",
        "native_positions": pack_native_positions(complete["activations"]["design"]),
    }
    proof = derive_root_body_assessment(
        s,
        complete["activations"]["personality"],
        complete["activations"]["design"],
        "true",
        [evaluation],
        require_swiss_files=False,
    )
    assert proof["evaluated_tt_count"] == 1
    assert proof["selected_evaluation_index"] == 0
    assert proof["observed_activation_changes"] == []
    assert proof["observed_structure_changed_fields"] == []
    assert proof["physical_time_accuracy_certified"] is False


def test_missing_new_role_cannot_be_hidden_by_rebuilding_source_summary(
    complete, monkeypatch
):
    from fatebridge.core.human_design_natal_sources import natal_source_summary

    run = deepcopy(complete)
    source = run["ephemeris_source_evidence"]
    original = len(source["contexts"])
    source["contexts"] = [
        c for c in source["contexts"] if c["role"] != "root_bracket_activation"
    ]
    assert len(source["contexts"]) < original
    source["observed_native_position_evaluations"] = sum(
        c["observed_evaluation_count"] for c in source["contexts"]
    )
    run["ephemeris_source_summary"] = natal_source_summary(source)
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    check = verify_human_design_reading(rehash(run))
    assert check["status"] == "rejected"
    assert any(
        e["code"] == "natal_file_context_or_policy_mismatch" for e in check["errors"]
    )
