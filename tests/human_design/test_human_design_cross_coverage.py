"""New all-gate/angle observations retain every original literal failure."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_cross_coverage import (
    cross_coverage_reference,
    expanded_cross_audit,
    expanded_cross_evidence,
)
from fatebridge.core.human_design_source_variants import source_variant_audit
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_official import official_chart_checks
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
REFERENCE_PATH = FIXTURES / "human-design-official-cross-charts.json"
REFERENCE = json.loads(REFERENCE_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_all193_original_observations_and_predeclared_inputs_are_preserved():
    assert (
        hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
        == "fb77fbc137d6ebb83a9781b0558b4b9c5d7c411f1f3fce7b0ac54cf5d0510c89"
    )
    plan_path = FIXTURES / "human-design-cross-coverage-plan.json"
    plan = json.loads(plan_path.read_text())
    assert (
        hashlib.sha256(plan_path.read_bytes()).hexdigest()
        == REFERENCE["source"]["plan_sha256"]
    )
    assert datetime.fromisoformat(plan["declared_at_utc"]) < datetime.fromisoformat(
        REFERENCE["source"]["collected_at"]
    )
    assert len(plan["cases"]) == len(REFERENCE["cases"]) == 193
    for selected, observed in zip(plan["cases"], REFERENCE["cases"]):
        assert selected["id"] == observed["id"]
        assert selected["birth_input"] == observed["birth_input"]
        assert "engine_diagnostic_not_official_expected_values" not in observed
    observations = FIXTURES / "human-design-cross-coverage-observations.json"
    assert (
        hashlib.sha256(observations.read_bytes()).hexdigest()
        == "46d801f0c468f1b87096ac6951cd2352cddf440af25cc57875f70a631f5da22c"
    )
    source = json.loads(observations.read_text())
    assert len(source["sources"]) == len(source["observations"]) == 193
    assert source["transcription_crosscheck"]["raw_facts_fnv1a32"] == "589642e0"
    assert (
        source["transcription_crosscheck"]["normalized_properties_fnv1a32"]
        == "2397b0ad"
    )
    assert len(source["transcription_crosscheck"]["whitespace_changes"]) == 18
    catalog = cross_coverage_reference()
    assert (
        catalog["cohort_sha256"]
        == hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
    )
    assert len(catalog["observations"]) == 193
    assert {r["case_id"] for r in catalog["observations"]} == {
        r["id"] for r in REFERENCE["cases"]
    }


def test_all5018_gate_lines193_mechanics_and86_literal_failures_remain():
    check = official_chart_checks(REFERENCE)
    assert check["gate_lines_checked"] == check["gate_lines_matched"] == 5018
    assert check["charts_with_all_mechanics_matched"] == 193
    assert all(c["structure_checks"]["strategy"] for c in check["cases"])
    assert check["cross_names_exactly_matched"] == check["charts_matched"] == 107
    assert check["status"] == "failed"
    assert sum(not c["structure_checks"]["cross_name"] for c in check["cases"]) == 86
    assert (
        sum(
            c["properties"]["Definition"] == "Quadruple Split"
            for c in REFERENCE["cases"]
        )
        == 4
    )
    names = expanded_cross_audit()
    assert names["all_192_gate_angle_strata_observed"] is True
    assert names["gate_angle_strata_checked"] == 192
    assert names["literal_name_matches"] == 107
    assert names["all_disagreements_resolved"] is False
    old = source_variant_audit()
    assert old["observed_label_count"] == 19 and old["literal_name_matches"] == 4
    assert len([r for r in old["name_comparisons"] if not r["literal_match"]]) == 15


def test_every_new_official_case_has_complete_source_bound_reading():
    count = 0
    for case in REFERENCE["cases"]:
        run = execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))
        proof = run["source_consistency"]["expanded_cross_name_comparison"]
        assert case["id"] in {r["case_id"] for r in proof["observations"]}
        assert all(r["pdf_sha256"] for r in proof["observations"])
        assert proof["primary_2001_name"] == run["incarnation_cross"]["name"]
        check = verify_human_design_reading(run)
        assert check["status"] == "verified_fixed_template_reading", (case["id"], check)
        assert check["checked_expanded_cross_observation_count"] == len(
            proof["observations"]
        )
        diagram_case = case["id"] in {"cross-left-09", "cross-left-16"}
        assert check["checked_statement_count"] == (11 if diagram_case else 10)
        if diagram_case:
            assert (
                run["interpretation"]["statements"][-1]["id"]
                == "primary_transcript_diagram"
            )
        assert check["checked_fixing_reading_count"] == 26
        assert run["validation"]["all_three_axes_full_marks"] is False
        summary, ruleset = run["source_summary"], run["rulesets"][0]
        assert summary["version"] == ruleset["version"]
        assert summary["author"] == ruleset["author"]
        assert summary["scope"] == ruleset["scope"]
        assert summary["primary_source_url"] == ruleset["sources"]["rave_2001"]
        assert summary["full_source_acceptance_passed"] is False
        count += 1
    assert count == 193


def test_course_list_conflict_is_retained_without_overwriting_the_actual_quartet():
    ref = cross_coverage_reference()
    course = ref["course_list_disagreement"]
    assert course["printed_course_personality_pair"] == [16, 6]
    assert course["official_chart_personality_pair"] == [16, 9]
    assert course["resolved"] is course["publisher_erratum_obtained"] is False
    case = next(c for c in REFERENCE["cases"] if c["id"] == "cross-left-16")
    run = execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))
    assert run["incarnation_cross"]["gates"] == [16, 9, 63, 64]
    assert (
        run["source_consistency"]["expanded_cross_name_comparison"][
            "course_list_disagreement"
        ]
        == course
    )
    assert "16/6" in run["interpretation"]["expanded_cross_name_meaning"]
    assert "16/9" in run["interpretation"]["expanded_cross_name_meaning"]


def test_unobserved_quartet_is_not_inferred_from_gate_alone_and_outputs_do_not_alias():
    chart = {
        "incarnation_cross": {
            "gates": [16, 9, 63, 64],
            "angle": "left",
            "name": "IDENTIFICATION",
        }
    }
    first = expanded_cross_evidence(chart)
    first["observations"][0]["gates"][0] = 1
    first["course_list_disagreement"]["resolved"] = True
    second = expanded_cross_evidence(chart)
    assert second["observations"][0]["gates"][0] == 16
    assert second["course_list_disagreement"]["resolved"] is False
    chart["incarnation_cross"]["gates"] = [16, 6, 63, 64]
    absent = expanded_cross_evidence(chart)
    assert absent["status"] == "not_observed_in_expanded_cohort"
    assert absent["observed_labels"] == [] and absent["observations"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        "alias",
        "name",
        "quartet",
        "pdf",
        "text",
        "course",
        "acceptance",
        "summary_version",
        "summary_author",
    ],
)
def test_rehashed_forged_modern_labels_and_source_conflicts_are_rejected(mutation):
    case = next(c for c in REFERENCE["cases"] if c["id"] == "cross-left-16")
    run = execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))
    forged = deepcopy(run)
    proof = forged["source_consistency"]["expanded_cross_name_comparison"]
    if mutation == "alias":
        proof["observed_labels"][0]["alias_accepted"] = True
    elif mutation == "name":
        proof["primary_2001_name"] = "Modern preferred name"
    elif mutation == "quartet":
        proof["observations"][0]["gates"] = [16, 6, 63, 64]
    elif mutation == "pdf":
        proof["observations"][0]["pdf_sha256"] = "0" * 64
    elif mutation == "text":
        forged["interpretation"][
            "expanded_cross_name_meaning"
        ] = "所有名称和原典均已通过。"
    elif mutation == "course":
        proof["course_list_disagreement"]["resolved"] = True
    elif mutation == "acceptance":
        proof["full_source_acceptance_passed"] = True
    elif mutation == "summary_version":
        forged["source_summary"]["version"] = "publisher-certified"
    else:
        forged["source_summary"]["author"] = "Official original producer"
    forged["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in forged.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(forged)["status"] == "rejected"
