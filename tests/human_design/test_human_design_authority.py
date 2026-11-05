"""Frozen independent rare branches, actual graph witnesses and hostile claims."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import bodygraph
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_official import (
    combine_official_chart_cohorts,
    official_chart_checks,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
NEW = json.loads((FIXTURES / "human-design-official-authority-charts.json").read_text())
OLD = json.loads((FIXTURES / "human-design-official-charts.json").read_text())
COMBINED = combine_official_chart_cohorts(OLD, NEW)
SPEC = next(s for s in CATALOG if s.key == "human_design")


def test_frozen_plan_covers_all_observations_without_using_engine_diagnostics_as_expected():
    plan_path = ROOT / NEW["plan_reference"]["path"]
    plan = json.loads(plan_path.read_text())
    assert (
        hashlib.sha256(plan_path.read_bytes()).hexdigest()
        == NEW["plan_reference"]["sha256"]
    )
    assert datetime.fromisoformat(plan["declared_at"]) < datetime.fromisoformat(
        NEW["source"]["collected_at"]
    )
    assert len(plan["cases"]) == len(NEW["cases"]) == 11
    for selected, observed in zip(plan["cases"], NEW["cases"]):
        assert selected["id"] == observed["id"]
        assert selected["birth_input"] == observed["birth_input"]
        assert "engine_diagnostic" not in observed
        assert len(observed["pdf_sha256"]) == 64
    assert "not a blind" in plan["selection_method"]


def test_combined_cohort_keeps_all_name_discrepancies_and_finite_coverage():
    result = official_chart_checks(COMBINED)
    assert result["gate_lines_checked"] == result["gate_lines_matched"] == 494
    assert len(result["cohorts"]) == 2
    coverage = result["coverage"]
    assert len(coverage["displayed_types"]) == 5
    assert len(coverage["authority_ids"]) == 8
    assert len(coverage["profiles"]) == 12
    assert len(coverage["variable_codes"]) == 16
    assert coverage["cross_angles"] == ["juxtaposition", "left", "right"]
    assert coverage["definitions"] == ["None", "Single", "Split", "Triple Split"]
    assert result["cross_names_exactly_matched"] == 4
    differences = [
        c for c in result["cases"] if not c["structure_checks"]["cross_name"]
    ]
    assert len(differences) == 15
    names = {c["cross_name_comparison"]["primary_2001_name"] for c in differences}
    assert {"CONTAGEN (4)", "MAIA (4)", "UPHEAVEL", "TENSION (4)"} <= names
    assert result["status"] == "failed"
    assert result["full_original_text_certified"] is False
    assert result["physical_subdivision_accuracy_certified"] is False
    for case in result["cases"]:
        failures = {
            key for key, passed in case["structure_checks"].items() if not passed
        }
        assert failures <= {"cross_name", "variables"}
        if "variables" in failures:
            assert "moshier" in case["observed_ephemeris_models"]


@pytest.mark.parametrize("case", NEW["cases"], ids=lambda c: c["id"])
def test_each_authority_and_path_quote_comes_from_its_original_full_run(case):
    run = execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))
    assert (
        verify_human_design_reading(run)["status"] == "verified_fixed_template_reading"
    )
    graph = run["bodygraph"]
    evidence = graph["classification_evidence"]
    assert evidence["selected_authority"] == graph["authority"]
    assert evidence["defined_centers"] == sorted(
        center for center, row in graph["centers"].items() if row["status"] == "defined"
    )
    assert bool(evidence["motor_to_throat_paths"]) == graph["motor_to_throat"]
    by_id = {c["id"]: c for c in graph["channels"]}
    for path in evidence["motor_to_throat_paths"] + evidence["authority_paths"]:
        assert len(path["centers"]) == len(path["channel_ids"]) + 1
        assert len(set(path["centers"])) == len(path["centers"])
        for index, channel_id in enumerate(path["channel_ids"]):
            assert set(path["centers"][index : index + 2]) == set(
                by_id[channel_id]["centers"]
            )
    statement = next(
        s for s in run["interpretation"]["statements"] if s["id"] == "authority"
    )
    assert statement["basis"][1] == {
        "path": "bodygraph.classification_evidence",
        "value": evidence,
    }
    assert run["interpretation"]["authority_structure"] in statement["text"]


@pytest.mark.parametrize(
    "p,d,authority,path,has_motor",
    [
        ([21, 45], [], "ego_manifested", ["21-45"], True),
        ([25, 10], [51, 20], "ego_manifested", ["25-51", "10-20"], True),
        ([25, 51, 10], [], "ego_projected", ["25-51"], False),
        ([1, 8], [], "self_projected", ["1-8"], False),
        ([64, 47], [], "environment_no_inner_authority", [], False),
        ([1], [], "lunar_no_inner_authority", [], False),
        ([21, 45, 12, 22], [], "emotional", [], True),
        ([5, 15, 21, 45], [], "sacral", [], True),
    ],
)
def test_priority_and_complete_channel_counterexamples(
    p, d, authority, path, has_motor
):
    graph = bodygraph(p, d)
    evidence = graph["classification_evidence"]
    assert graph["authority"] == authority
    assert bool(evidence["motor_to_throat_paths"]) is has_motor
    paths = evidence["authority_paths"]
    assert (paths[0]["channel_ids"] if paths else []) == path
    checks = evidence["authority_priority_checks"]
    assert all(not check["defined"] for check in checks[:-1])
    assert checks[-1]["defined"] is (not evidence["no_inner_authority"])
    if authority == "environment_no_inner_authority":
        assert graph["centers"]["throat"]["status"] == "completely_open"


@pytest.mark.parametrize(
    "tamper", ["path", "priority", "boolean_type", "missing", "text"]
)
def test_forged_path_or_priority_cannot_pass_even_with_a_new_business_hash(tamper):
    case = NEW["cases"][-1]  # frozen official indirect Ego -> G -> Throat
    run = deepcopy(execute_tool(SPEC, SPEC.request_model(**case["birth_input"])))
    evidence = run["bodygraph"]["classification_evidence"]
    if tamper == "path":
        evidence["authority_paths"][0]["channel_ids"] = ["21-45"]
    elif tamper == "priority":
        evidence["authority_priority_checks"][0]["defined"] = True
    elif tamper == "boolean_type":
        evidence["no_inner_authority"] = 0
    elif tamper == "missing":
        run["bodygraph"].pop("classification_evidence")
    else:
        run["interpretation"]["authority_structure"] = "仅由21-45直接通道形成。"
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    check = verify_human_design_reading(run)
    assert check["status"] == "rejected"
    if tamper != "text":
        assert any(
            e["code"] == "bodygraph_derivation_mismatch" for e in check["errors"]
        )


@pytest.mark.parametrize(
    "key,value",
    [("Authority", "Mind"), ("Definition", "Quadruple Split"), ("Type", "Unknown")],
)
def test_unobserved_official_labels_require_source_expansion_before_comparison(
    key, value
):
    ref = deepcopy(NEW)
    ref["cases"] = [ref["cases"][0]]
    ref["cases"][0]["properties"][key] = value
    with pytest.raises(ValueError, match="Unknown official property"):
        official_chart_checks(ref)


def test_unknown_or_malformed_cross_and_duplicate_or_different_cohorts_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        official_chart_checks(combine_official_chart_cohorts(NEW, NEW))
    changed = deepcopy(NEW)
    changed["planet_order"].reverse()
    with pytest.raises(ValueError, match="different source"):
        combine_official_chart_cohorts(OLD, changed)
    changed = deepcopy(NEW)
    changed["cases"] = [changed["cases"][0]]
    changed["cases"][0]["properties"][
        "Incarnation Cross"
    ] = "Left Angle Cross of Dominion (65/63 | 45/26)"
    with pytest.raises(ValueError, match="Invalid official incarnation"):
        official_chart_checks(changed)
