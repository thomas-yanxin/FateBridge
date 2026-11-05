"""Frozen explicit source clauses, public regressions and conditional donors."""

import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design_depth import line_fixings
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-additional-poles-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Pure verification called a native producer")


def records(sides):
    return line_fixings(sides)


def recipient(sides):
    result = next(
        r for r in records(sides) if r["calculation_path"] == "activations.design.0"
    )
    assert result["side"] == "design" and result["body"] == sides["design"][0]["body"]
    return result


def test_original_source_catalogue_and_preregistered_inputs_remain_immutable():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "d44b2199c8c2cf8bff6f2b0efe1ed2baf9280aed6a2c66dbd67c3f28c6c91da1"
    )
    legacy = ROOT / "src/fatebridge/data/human_design/rave-2001-depth.json"
    assert (
        hashlib.sha256(legacy.read_bytes()).hexdigest()
        == PLAN["original_glyph_catalog_sha256"]
        == "6fd06279b49f071dabb34aa293070f51f840cd1773986304aecbbbaa6be2270b"
    )
    p = ROOT / "src/fatebridge/data/human_design/additional-polarities-2001.json"
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == PLAN["source_catalog_sha256"]
        == "2bdfaabbe3ab98b43eac457ad5545c4ccee8205e6d0c7fc760cf1e95029bd262"
    )
    ref = json.loads(p.read_text())
    assert ref["scanned_line_count"] == 384
    assert [
        (
            f["gate"],
            f["line"],
            f["primary_marker_planet"],
            f["additional_planet"],
            f["source_pdf_page_one_based"],
        )
        for f in ref["facts"]
    ] == [(11, 4, "Moon", "Venus", 27), (25, 4, "Venus", "Jupiter", 55)]
    assert [f["source_clause_sha256"] for f in ref["facts"]] == [
        hashlib.sha256(s.encode()).hexdigest()
        for s in ("Venus is also exalted.", "Jupiter is also exalted.")
    ]
    assert (
        ref["full_line_meanings_accepted"]
        is ref["publisher_master_authenticated"]
        is False
    )
    tree = ast.parse(
        (
            ROOT / "scripts/human_design/build_human_design_additional_polarities.py"
        ).read_text()
    )
    assert not any(
        isinstance(n, ast.ImportFrom) and (n.module or "").startswith("fatebridge")
        for n in ast.walk(tree)
    )
    assert len(PLAN["public_cases"]) == 6
    assert sum(c["old_fixing_state"] == "unfixed" for c in PLAN["public_cases"]) == 5
    assert PLAN["unchanged_thresholds"] == {
        "astronomy_arcsec": 2.0,
        "physical_design_root_seconds": 5.0,
        "clock_seconds": 0.0002,
    }


@pytest.mark.parametrize("fact", PLAN["facts"], ids=lambda f: f["fact_id"])
@pytest.mark.parametrize("case", PLAN["matrix_requirements"])
def test_all_preregistered_planet_gate_line_and_side_conditions(fact, case):
    gate, line = fact["gate"], fact["line"]
    harmonic = {11: 56, 25: 51}[gate]
    donor = fact["additional_planet"]
    primary = fact["primary_marker_planet"]
    sides = {
        "design": [{"body": "Mercury", "gate": gate, "line": line}],
        "personality": [{"body": donor, "gate": gate, "line": line}],
    }
    if case == "same_gate_other_line":
        sides["personality"][0]["line"] = 1
    elif case == "harmonic_gate":
        sides["personality"][0]["gate"] = harmonic
    elif case == "both_sides":
        sides["design"].append({"body": donor, "gate": harmonic, "line": 6})
    elif case == "base_marker_still_valid":
        sides["personality"][0]["body"] = primary
    elif case == "wrong_body_rejected":
        sides["personality"][0]["body"] = "Saturn"
    elif case == "wrong_gate_rejected":
        sides["personality"][0]["gate"] = 1
    elif case == "wrong_line_rejected":
        sides["design"][0]["line"] = 5
    elif case == "node_donor_rejected":
        sides["personality"][0]["body"] = "NorthNode"
    elif case == "node_recipient_accepted":
        sides["design"][0]["body"] = "NorthNode"
        sides["personality"][0]["gate"] = harmonic
    elif case == "dual_juxtaposition_preserved":
        sides["design"].append({"body": "Sun", "gate": harmonic, "line": 1})
    r = recipient(sides)
    reject = case in {
        "wrong_body_rejected",
        "wrong_gate_rejected",
        "wrong_line_rejected",
        "node_donor_rejected",
    }
    if reject:
        assert all(x["body"] != donor for x in r["fixing_planets"]["exaltation"])
        assert "additional_polarity_basis" not in r
    else:
        assert r["fixing_planets"]["exaltation"]
        assert r["fixing_state"] == (
            "juxtaposition"
            if case == "dual_juxtaposition_preserved" and gate == 11
            else "exaltation"
        )
        if case != "base_marker_still_valid":
            assert r["additional_polarity_basis"][0]["fact_id"] == fact["fact_id"]
            assert "正文另将" in r["reading"]
            assert (
                r["additional_polarity_basis"][0]["source_catalog_sha256"]
                == PLAN["source_catalog_sha256"]
            )
    assert r["polarity_kind"] == (
        "unitary" if gate == 25 and r["line"] == 4 else "dual"
    )
    if case == "node_recipient_accepted":
        assert r["recipient_kind"] == "node_activation"
    assert r["exaltation_planet"] == primary if r["line"] == line else True


@pytest.mark.parametrize("case", PLAN["public_cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("mode", PLAN["modes"])
@pytest.mark.parametrize("empty_files", [False, True])
def test_every_original_public_case_both_modes_and_backends(
    case, mode, empty_files, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(SPEC, SPEC.request_model(**case["input"], node_mode=mode))
    r = next(
        r
        for r in run["depth_evidence"]["line_fixings"]
        if r["side"] == "personality" and r["body"] == case["recipient_body"]
    )
    assert r["fixing_state"] == case["expected_fixing_state"]
    assert any(
        t["body"] == case["recipient_body"] for t in r["fixing_planets"]["exaltation"]
    )
    assert (
        r["additional_polarity_basis"][0]["additional_planet"] == case["recipient_body"]
    )
    summary = run["depth_evidence"]["additional_polarity_summary"]
    assert summary["matched_recipient_count"] == 1
    assert summary["recipients"][0]["body"] == case["recipient_body"]
    assert summary["full_line_meanings_accepted"] is False
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(
            SPEC,
            SPEC.request_model(
                **PLAN["public_cases"][0]["input"], birth_time_uncertainty_minutes=1
            ),
        )


@pytest.mark.parametrize("bad", PLAN["negative_receipts"])
def test_rehashed_missing_or_forged_source_and_donor_receipts_are_rejected(
    complete, bad, monkeypatch
):
    run = deepcopy(complete)
    depth = run["depth_evidence"]
    r = next(
        r
        for r in depth["line_fixings"]
        if r["side"] == "personality" and r["body"] == "Venus"
    )
    if bad == "missing_catalog":
        del depth["additional_polarity_sources"]
    elif bad == "wrong_source_hash":
        depth["additional_polarity_sources"]["source"]["pdf_sha256"] = "0" * 64
    elif bad == "wrong_additional_planet":
        depth["additional_polarity_sources"]["facts"][0]["additional_planet"] = "Mars"
    elif bad == "removed_new_donor":
        r["fixing_planets"]["exaltation"] = []
    elif bad == "wrong_new_donor_path":
        r["fixing_planets"]["exaltation"][0][
            "calculation_path"
        ] = "activations.design.0"
    elif bad == "forged_additional_basis":
        r["additional_polarity_basis"][0]["source_pdf_page_one_based"] = 1
    elif bad == "changed_new_reading":
        r["reading"] = "金星单独保证现实成功"
    elif bad == "removed_from_interval":
        sample = run["time_sensitivity"]["classification_variants"][0]["value"][
            "depth_evidence"
        ]
        del sample["additional_polarity_sources"]
    elif bad == "removed_from_backend_reference":
        del run["ephemeris_backend_comparison"]["mechanical_comparison"][
            "reference_structure"
        ]["depth_evidence"]["additional_polarity_sources"]
    else:
        raise AssertionError(bad)
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    assert verify_human_design_reading(run)["status"] == "rejected"


def test_returned_catalog_and_basis_cannot_mutate_later_source_results():
    sides = {
        "design": [{"body": "Mercury", "gate": 11, "line": 4}],
        "personality": [{"body": "Venus", "gate": 11, "line": 1}],
    }
    r = recipient(sides)
    r["additional_polarity_basis"][0]["additional_planet"] = "Saturn"
    assert (
        recipient(sides)["additional_polarity_basis"][0]["additional_planet"] == "Venus"
    )


def test_forged_additional_polarity_summary_rejected(complete, monkeypatch):
    run = deepcopy(complete)
    run["depth_evidence"]["additional_polarity_summary"]["matched_recipient_count"] = 0
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    assert verify_human_design_reading(run)["status"] == "rejected"
