"""Physical budget arithmetic never certifies effective root force or passage."""

import asyncio
import copy
import gzip
import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_strength_thresholds import (
    PhysicalRootUnitComparison,
    StrengthThresholdArithmetic,
)
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate
from fatebridge.core.strength_thresholds import threshold_snapshot_lines
from tests.fixtures.bazi_root_predicate_v1.transport_reader import (
    cli_payload,
    file_payload,
    native_with_manifest,
    save_json,
    verify_identity,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_predicate_v1"
FILES = ROOT / "docs/validation/bazi-root-predicate-files-v1"
PLAN = json.loads((FIXTURE / "implementation-plan-first.json").read_bytes())
PUBLIC = json.loads((FIXTURE / "public-inputs-first.json").read_bytes())["cases"]
SELECTED = set(PLAN["public_input_selection"]["indexes"])
with gzip.open(FILES / "baseline-first-disagreements.jsonl.gz", "rt") as handle:
    EXAMPLES = {
        r["index"]: r for line in handle if (r := json.loads(line))["index"] in SELECTED
    }


def evaluate(values, policy=DEFAULT_POLICY):
    ps = dict(zip(("year", "month", "day", "hour"), map(tuple, values)))
    return _evaluate(
        ps,
        ElementAnalysis.seasonal_phases(values[1][1]),
        policy,
        stem_effect_mode="precise_binding_only_v1",
    )


@pytest.mark.parametrize("index", sorted(SELECTED))
def test_first_counterexamples_follow_frozen_independent_exact_expectation(index):
    first = EXAMPLES[index]
    current = evaluate(first["pillars"])
    receipt = current["threshold_arithmetic"]
    root = receipt["physical_root_unit_comparison"]
    assert root["masses_exact"] == first["exact_root_masses"]
    assert root["rooted_controller_stems"] == first["expected_controller_count"]
    assert root["rooted_wealth_visible"] == first["expected_wealth"]
    assert current["strength_level"] == first["expected_grade"]
    assert current["root_qualifications"] == first["before"]["root_qualifications"]
    assert current["relations"] == first["before"]["relations"]
    assert (
        current["effective_elements_unrounded"]
        == first["before"]["effective_elements_unrounded"]
    )
    assert (
        receipt["energies_exact"]
        == first["before"]["threshold_arithmetic"]["energies_exact"]
    )
    assert root["effective_classical_root_force"] == "not_adjudicated"
    StrengthThresholdArithmetic.model_validate(receipt)
    legacy = first["before"]["structural_decision"]
    assert (
        root["legacy_float_rooted_controller_stems"]
        == legacy["rooted_controller_stems"]
    )
    assert root["legacy_float_rooted_wealth_visible"] == legacy["rooted_wealth_visible"]
    lines = threshold_snapshot_lines(current)
    consumed_changed = (
        first["changes"]["rooted_controller_count"] or first["changes"]["rooted_wealth"]
    )
    assert any("财官根量的工程比较" in line for line in lines) == consumed_changed


@pytest.mark.parametrize(
    "case", PLAN["expected_final_changes"], ids=lambda r: str(r["index"])
)
@pytest.mark.parametrize("budget,expected", [(1.7, False), (2.0, True), (2.3, True)])
def test_same_existing_unit_boundary_is_bracketed_without_an_epsilon(
    case, budget, expected
):
    current = evaluate(case["pillars"], replace(DEFAULT_POLICY, branch_budget=budget))
    root = current["threshold_arithmetic"]["physical_root_unit_comparison"]
    assert root["unit_threshold_exact"] == "1"
    element = "土" if case["index"] == 494165 else "金"
    assert (
        root["masses_exact"][element] == {1.7: "17/20", 2.0: "1", 2.3: "23/20"}[budget]
    )
    assert root["at_least_unit"][element] == expected
    if element == "土":
        assert root["rooted_wealth_visible"] == expected
    else:
        assert root["rooted_controller_stems"] == (2 if expected else 0)


@pytest.mark.parametrize(
    "patch",
    [
        {"unit_threshold_exact": "999/1000"},
        {"unit_threshold_exact": "1001/1000"},
        {"unit_threshold_exact": "1/0"},
        {"masses_exact": {"金": "-1"}},
        {"masses_exact": {"金": "1/0"}},
        {"masses_exact": {"金": "1"}, "at_least_unit": {"金": False}},
        {"masses_exact": {"金": "999/1000"}, "at_least_unit": {"金": True}},
        {"rooted_controller_stems": 4},
        {"rooted_controller_stems": True},
        {"effective_classical_root_force": "adjudicated"},
        {"quantity_kind": "classical_effective_root_force"},
    ],
)
def test_root_receipt_cannot_move_thresholds_or_invent_classical_force(patch):
    with pytest.raises(ValidationError):
        PhysicalRootUnitComparison.model_validate(patch)
    PhysicalRootUnitComparison.model_validate({"masses_exact": {"金": "1"}})
    PhysicalRootUnitComparison.model_validate({"at_least_unit": {"金": True}})


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("field", ["rooted_controller_stems", "rooted_wealth_visible"])
def test_complete_receipt_cannot_miscount_same_run_visible_financial_or_control_stems(
    legacy, field
):
    receipt = copy.deepcopy(
        evaluate(EXAMPLES[399737]["pillars"])["threshold_arithmetic"]
    )
    name = ("legacy_float_" if legacy else "") + field
    current = receipt["physical_root_unit_comparison"][name]
    receipt["physical_root_unit_comparison"][name] = (
        not current if type(current) is bool else (current + 1) % 4
    )
    with pytest.raises(ValidationError):
        StrengthThresholdArithmetic.model_validate(receipt)


@pytest.mark.parametrize("case", PUBLIC, ids=lambda r: r["id"])
def test_all_selected_calendar_reproductions_and_eleven_entries_actual_transports(
    case, rest, tmp_path, capsys
):
    spec = SPECS[case["tool"]]
    fields = suggested_fields(spec, view="root_predicates")
    assert len(fields) == 5
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 8192,
    }
    result, manifest = asyncio.run(
        native_with_manifest(spec, case["arguments"], case["as_of"], flags, tmp_path)
    )
    assert not result.is_error
    payloads = [file_payload(result.structured_content, manifest, tmp_path, "mcp")]
    code, local = call_cli(
        spec,
        case["arguments"],
        tmp_path,
        capsys,
        flags=[
            "--strict-fields",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )
    save_json(tmp_path / "cli-original-response.json", local)
    assert code == 0
    payloads.append(cli_payload(local, tmp_path, capsys))
    if spec.rest_path:
        response = rest.post(spec.rest_path, json=case["arguments"], params=flags)
        value = response.json()
        save_json(tmp_path / "rest-original-response.json", value)
        assert response.status_code == 200
        rest_manifest = None
        if value.get("result_delivery"):
            response = rest.get("/api/results/" + value["result_delivery"]["result_id"])
            save_json(tmp_path / "rest-manifest.json", response.json())
            assert response.status_code == 200
            rest_manifest = response.json()
            verify_identity(
                value["result_delivery"], value["run_metadata"], rest_manifest
            )
        payloads.append(file_payload(value, rest_manifest, tmp_path, "rest"))
    for value in payloads:
        spec.output_model.model_validate(value)
    assert all(business(value) == business(payloads[0]) for value in payloads)
    facts = []
    for path in fields:
        value = payloads[0]
        for name in path.split("."):
            value = value[name]
        facts.append(value)
    receipt, strength, force, duty, passage = facts
    first = EXAMPLES[case["index"]]
    assert (
        receipt["physical_root_unit_comparison"]["masses_exact"]
        == first["exact_root_masses"]
    )
    assert strength == first["expected_grade"]
    assert set(force.values()) == {"not_adjudicated"}
    assert (
        duty == "not_adjudicated" and passage["effective_passage"] == "not_adjudicated"
    )
