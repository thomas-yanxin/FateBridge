"""Original failures stay visible; a historical amendment is only conditional."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_depth import line_fixings
from fatebridge.core.human_design_historical_polarity import (
    METHOD,
    comparison_report,
    source_records,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

FIXTURE = Path(__file__).parents[1] / "data/human_design/historical_polarity"
REFERENCE = json.loads((FIXTURE / "independent-plan-and-reference.json").read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_independent_240_case_oracle_is_frozen_before_production_changes():
    assert (
        hashlib.sha256(
            (FIXTURE / "independent-plan-and-reference.json").read_bytes()
        ).hexdigest()
        == "f90c6401401de1757fd5d3fd0ba37e6eb4c2a7d59a3c48541c1aa12554347e95"
    )
    assert REFERENCE["reference_imports_fatebridge"] is False
    assert len(REFERENCE["cases"]) == 240


@pytest.mark.parametrize("start", range(0, 240, 30))
def test_all_independent_same_gate_harmonic_other_side_and_node_cases(start):
    for case in REFERENCE["cases"][start : start + 30]:
        chart = {"activations": case["activations"]}
        selected = line_fixings(chart["activations"])
        actual = comparison_report(chart)
        target = next(
            r
            for r in actual["nominal_recipients"]
            if r["side"] == case["target_side"] and r["calculation_path"].endswith(".0")
        )
        assert (
            target["selected_2001_fixing_state"] == case["expected_selected_state"]
        ), case["id"]
        assert (
            target["conditional_2002_fixing_state"]
            == case["expected_conditional_state"]
        ), case["id"]
        assert line_fixings(chart["activations"]) == selected
        for row in actual["nominal_recipients"]:
            assert all(
                d["body"] not in {"NorthNode", "SouthNode"}
                for p in row["conditional_2002_fixing_planets"].values()
                for d in p
            )
            for donors in row["conditional_2002_fixing_planets"].values():
                for donor in donors:
                    _, side, index = donor["calculation_path"].split(".")
                    assert (
                        donor["body"] == chart["activations"][side][int(index)]["body"]
                    )
        assert actual["default_changed"] is False
        assert actual["source_conflict_resolved"] is False


def test_no_recipient_is_distinct_from_resolved_source_conflict():
    report = comparison_report(
        {
            "activations": {
                "personality": [{"body": "Sun", "gate": 58, "line": 4}],
                "design": [],
            }
        }
    )
    assert (
        report["nominal_recipient_count"] == report["nominal_changed_state_count"] == 0
    )
    assert report["status"] == "unresolved_historical_source_conflict"


def test_reviewed_official_markers_contradict_the_conditional_notice():
    observed = json.loads((FIXTURE / "visible-marker-observations.json").read_text())
    assert len(observed["observations"]) == 2
    assert observed["resolved"] is False
    for source, fact in zip(
        source_records()[1:], observed["observations"], strict=True
    ):
        assert source["pdf_sha256"] == fact["source_pdf_sha256"]
        assert fact["observed_marker"] == "downward_triangle"
        assert fact["literal2001_prediction_matches"] is True
        assert fact["conditional2002_prediction_matches"] is False
    assert "not an authenticated" in source_records()[0]["attribution"]
    assert source_records()[0]["applicability_to_selected_2001_edition"] == "unresolved"


@pytest.fixture(scope="module")
def complete(native_ephemeris_files_module):
    inputs = json.loads(
        (
            Path(__file__).parents[1] / "data/human_design/regression-inputs.json"
        ).read_text()
    )
    return execute_tool(SPEC, SPEC.request_model(**inputs["historical_polarity"]))


def test_current_complete_reading_preserves_actual_calculation_and_selected_fixings(
    complete,
):
    report = complete["historical_polarity_context"]
    assert (
        report["nominal_recipient_count"] == report["nominal_changed_state_count"] == 1
    )
    row = report["nominal_recipients"][0]
    assert row["selected_2001_fixing_state"] == "detriment"
    assert row["conditional_2002_fixing_state"] == "exaltation"
    assert (
        row["conditional_2002_fixing_planets"]["exaltation"][0]["calculation_path"]
        == "activations.personality.0"
    )
    assert (
        verify_human_design_reading(complete)["status"]
        == "verified_fixed_template_reading"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_context",
        "drop_all_regions",
        "unknown_contract_drop_all",
        "source_hash",
        "resolved",
        "default_switch",
        "donor_path",
        "conditional_state",
        "selected_state",
        "missing_recipient",
        "interpretation_text",
        "reading_count",
    ],
)
def test_rehashed_forgeries_and_new_contract_omissions_are_rejected(complete, mutation):
    run = deepcopy(complete)
    context = run["historical_polarity_context"]
    if mutation in {"drop_context", "drop_all_regions", "unknown_contract_drop_all"}:
        run.pop("historical_polarity_context")
        if mutation != "drop_context":
            run["interpretation"].pop("historical_polarity_context")
            run["interpretation"]["basis"].remove("historical_polarity_context")
            run["rulesets"] = [r for r in run["rulesets"] if r["id"] != METHOD]
            run["rule_trace"] = [
                r for r in run["rule_trace"] if r["ruleset_id"] != METHOD
            ]
        if mutation == "unknown_contract_drop_all":
            run["run_metadata"]["contract_sha256"] = "0" * 64
    elif mutation == "source_hash":
        context["ruleset"]["source_records"][0]["pdf_sha256"] = "0" * 64
    elif mutation == "resolved":
        context["source_conflict_resolved"] = True
    elif mutation == "default_switch":
        context["default_changed"] = True
    elif mutation == "donor_path":
        context["nominal_recipients"][0]["conditional_2002_fixing_planets"][
            "exaltation"
        ][0]["calculation_path"] = "activations.design.0"
    elif mutation == "conditional_state":
        context["nominal_recipients"][0]["conditional_2002_fixing_state"] = "detriment"
    elif mutation == "selected_state":
        context["nominal_recipients"][0]["selected_2001_fixing_state"] = "exaltation"
    elif mutation == "missing_recipient":
        context["nominal_recipients"] = []
    elif mutation == "interpretation_text":
        run["interpretation"]["historical_polarity_context"][
            "text"
        ] = "已获得完整原典认证。"
    else:
        context["nominal_changed_state_count"] = 0
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    proof = verify_human_design_reading(run)
    assert proof["status"] == "rejected", (mutation, proof)
