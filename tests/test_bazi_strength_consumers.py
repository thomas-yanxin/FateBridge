"""Consumer arithmetic and same-result explanations; no force or efficacy labels."""

import asyncio
import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.classical_force import build_force_components
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import StrengthContext
from fatebridge.core.output_classical_force import EngineeringForceComposition
from fatebridge.core.output_strength_thresholds import StrengthThresholdArithmetic
from fatebridge.core.strength_thresholds import threshold_snapshot_lines
from tests.bazi_refactor_reference import exact_digest
from tests.fixtures.bazi_strength_threshold_v1.independent_reference_v2 import (
    reconstruct,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _rest_fixture
from tests.test_bazi_strength_thresholds import delivered_payload

rest = _rest_fixture
FIXTURE = Path(__file__).parent / "fixtures/bazi_strength_consumers_v1"


def read(name):
    path = FIXTURE / name
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


BODY = read("body-builder-confirmed-before-first.json.gz")["cases"]
SPECIAL = read("special-cases-before-first.json.gz")["cases"]
CLIMATE = read("climate-source-first.json")["cases"]
PUBLIC = read("public-inputs-first.json")["cases"]


def assess(values):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, values)))
    return pillars, ElementAnalysis.analyze_day_master_strength(pillars)


@pytest.mark.parametrize("row", BODY, ids=lambda r: str(r["index"]))
def test_all_187_actual_first_comparison_errors_use_same_assessment_exact_budget(row):
    pillars, strength = assess(row["pillars"])
    force = build_natal_evidence(pillars, strength)["force_components"]
    after = force["engineering_composition"]
    before = row["force_before"]["engineering_composition"]
    if row["index"] in {241988, 336427, 440107}:
        # The subsequently adopted same-target affiliation rule changes these
        # three original samples. Keep their original equal-budget counterexample
        # intact, and require full pre-repair objects plus independent exact math.
        path = (
            Path(__file__).parent
            / "fixtures/architecture_refactor_v1/strength-consumer-revisions-before.json"
        )
        raw = path.read_bytes()
        assert (
            hashlib.sha256(raw).hexdigest()
            == "3a26bf900329ade2af1ebe3fe4e4c30cfc38cec835dee865ea289547081fe9eb"
        )
        accepted = json.loads(raw)
        source = FIXTURE / "body-builder-confirmed-before-first.json.gz"
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest()
            == accepted["original_source_sha256"]
        )
        assert {r["index"] for r in accepted["rows"]} == {241988, 336427, 440107}
        expected = next(r for r in accepted["rows"] if r["index"] == row["index"])
        assert row["pillars"] == expected["pillars"]
        assert (
            exact_digest({"strength": strength, "force": force})
            == expected["business_sha256"]
        )
        exact = reconstruct(row["pillars"], strength["assessment"]["relations"])[
            "energies"
        ]
        assert {e: str(v) for e, v in exact.items()} == strength["assessment"][
            "threshold_arithmetic"
        ]["energies_exact"]
        body = exact[force["components"]["body"]["element"]]
        seal = exact[force["components"]["seal"]["element"]]
        assert after["body_energy_exact"] == str(body)
        assert after["seal_energy_exact"] == str(seal)
        assert after["body_within_support_exact"] == str(body / (body + seal))
        assert after["body_seal_energy_relation"] == (
            "body_greater"
            if body > seal
            else "seal_greater" if seal > body else "equal"
        )
        assert row["expected"]["relation"] == "equal"
        EngineeringForceComposition.model_validate(after)
        StrengthThresholdArithmetic.model_validate(
            strength["assessment"]["threshold_arithmetic"]
        )
        return
    assert after["body_seal_energy_relation"] == row["expected"]["relation"] == "equal"
    assert after["comparison_basis"] == "exact_rational_same_assessment"
    assert (
        after["legacy_float_body_seal_energy_relation"]
        == before["body_seal_energy_relation"]
    )
    assert (
        after["body_within_support_exact"]
        == row["expected"]["body_within_support_exact"]
        == "1/2"
    )
    assert after["body_within_support_share"] == before["body_within_support_share"]
    assert after["ratio_basis"] == before["ratio_basis"]
    for key in (
        "effective_elements_unrounded",
        "relations",
        "hidden_stem_ledger",
        "support_share",
        "strength_level",
    ):
        assert strength["assessment"][key] == row["strength_before"]["assessment"][key]
    assert (
        force["classical_adjudication"] == row["force_before"]["classical_adjudication"]
    )
    assert set(force["classical_adjudication"].values()) == {"not_adjudicated"}
    EngineeringForceComposition.model_validate(after)
    StrengthThresholdArithmetic.model_validate(
        strength["assessment"]["threshold_arithmetic"]
    )


@pytest.mark.parametrize("row", SPECIAL, ids=lambda r: str(r["index"]))
def test_three_first_strict_boundary_misclassifications_are_corrected_and_explained(
    row,
):
    pillars, strength = assess(row["pillars"])
    assessment = strength["assessment"]
    old = row["actual_strength_result"]["assessment"]
    assert old["requires_special_structure_review"] is True
    assert assessment["requires_special_structure_review"] is False
    assert assessment["threshold_arithmetic"]["share_exact"] == row["share_exact"]
    assert assessment["support_share"] == old["support_share"]
    assert assessment["strength_level"] == old["strength_level"]
    original = copy.deepcopy(assessment)
    lines = threshold_snapshot_lines(assessment)
    assert any(
        row["share_exact"] in line and "严格小于3/20或大于17/20" in line
        for line in lines
    )
    assert assessment == original
    assert ElementAnalysis.get_favorable_elements(strength)


@pytest.mark.parametrize("row", CLIMATE, ids=lambda r: r["id"])
def test_complete_climate_units_preserve_unknowns_and_distinct_root_actors(row):
    pillars, strength = assess(row["pillars"])
    evidence = build_natal_evidence(pillars, strength)
    assert row["expected_strength"] is None
    assert row["day_after_term"] is None and row["absolute_birth_datetime"] is None
    assert set(evidence["force_components"]["classical_adjudication"].values()) == {
        "not_adjudicated"
    }
    roots = evidence["force_components"]["source_root_observations"]["stems"]
    by_stem = {r["stem"]: r for r in roots}
    if row["id"] == "ZS03":
        assert any(r["hidden_element_present"] for r in by_stem["甲"]["roots"])
        assert not any(r["hidden_element_present"] for r in by_stem["癸"]["roots"])
    if row["id"] == "HN04":
        assert not any(r["hidden_element_present"] for r in by_stem["癸"]["roots"])
    if row["id"] == "ZS04":
        assert any(r["hidden_element_present"] for r in by_stem["癸"]["roots"])
        assert any(r["hidden_element_present"] for r in by_stem["甲"]["roots"])


def test_missing_or_partial_exact_evidence_is_never_recalculated_or_promoted():
    pillars, strength = assess(BODY[0]["pillars"])
    original = copy.deepcopy(strength["assessment"])
    for patch in (
        {"energies_exact": {"水": "2"}},
        {"day_element": "火"},
        {"energies_exact": {"木": "nan"}},
    ):
        assessment = copy.deepcopy(original)
        assessment["threshold_arithmetic"].update(patch)
        before = copy.deepcopy(assessment)
        result = build_force_components(pillars, assessment, {})[
            "engineering_composition"
        ]
        assert result["comparison_basis"] == "unrounded_same_assessment"
        assert result["body_energy_exact"] is None
        assert assessment == before
    empty = build_force_components(pillars, {}, {})["engineering_composition"]
    assert (
        empty["status"] == "not_supplied"
        and empty["body_seal_energy_relation"] == "not_supplied"
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"requires_special_structure_review": True},
        {"energies_exact": {"木": "-1"}},
        {"energies_exact": {"木": "nan"}},
        {"support_exact": "0"},
        {"special_lower_threshold_exact": "1/5"},
    ],
)
def test_contradictory_exact_receipts_rejected_while_partial_projection_allowed(patch):
    _, strength = assess(SPECIAL[0]["pillars"])
    receipt = strength["assessment"]["threshold_arithmetic"]
    with pytest.raises(ValidationError):
        StrengthThresholdArithmetic.model_validate({**receipt, **patch})
    assert StrengthThresholdArithmetic.model_validate(
        {"energies_exact": {"水": "1/2"}}
    ).energies_exact == {"水": "1/2"}
    with pytest.raises(ValidationError):
        StrengthContext.model_validate(
            {"threshold_arithmetic": receipt, "requires_special_structure_review": True}
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"body_seal_energy_relation": "seal_greater"},
        {"body_within_support_exact": "2/3"},
        {"body_energy_exact": "nan"},
        {"seal_energy_exact": "-1"},
    ],
)
def test_comparison_receipt_rejects_contradictory_explanation_fields(patch):
    pillars, strength = assess(BODY[0]["pillars"])
    composition = build_natal_evidence(pillars, strength)["force_components"][
        "engineering_composition"
    ]
    with pytest.raises(ValidationError):
        EngineeringForceComposition.model_validate({**composition, **patch})
    EngineeringForceComposition.model_validate({"body_energy_exact": "1/3"})


@pytest.mark.parametrize("case", PUBLIC, ids=lambda r: r["id"])
def test_five_fictional_identities_across_eleven_published_tools_and_transports(
    case, rest, tmp_path, capsys
):
    selected = SPECS[case["tool"]]
    fields = suggested_fields(selected, view="force_arithmetic")
    assert len(fields) == 3
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 8192,
    }
    protocol = asyncio.run(native(selected, case["arguments"], **flags))
    code, local = call_cli(
        selected,
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
    assert not protocol.is_error and code == 0
    responses = [("mcp", protocol.structured_content), ("cli", local)]
    if selected.rest_path:
        response = rest.post(selected.rest_path, json=case["arguments"], params=flags)
        assert response.status_code == 200, response.text
        responses.append(("rest", response.json()))
    payloads = []
    for name, value in responses:
        (tmp_path / (name + "-original-response.json")).write_text(
            json.dumps(value, ensure_ascii=False)
        )
        delivery = value.get("result_delivery")
        if delivery:
            (tmp_path / (name + "-same-run-file.json.gz")).write_bytes(
                gzip.compress(Path(delivery["file_path"]).read_bytes(), mtime=0)
            )
        payload = delivered_payload(value)
        payloads.append(payload)
        selected.output_model.model_validate(payload)
    assert all(business(v) == business(payloads[0]) for v in payloads)
    values = []
    for path in fields:
        item = payloads[0]
        for part in path.split("."):
            item = item[part]
        values.append(item)
    receipt, composition, adjudication = values
    assert composition["comparison_basis"] == "exact_rational_same_assessment"
    assert set(adjudication.values()) == {"not_adjudicated"}
    if case["kind"] == "special":
        assert receipt["share_exact"] == case["share_exact"]
        assert receipt["requires_special_structure_review"] is False
    else:
        assert composition["body_seal_energy_relation"] == "equal"
        assert (
            composition["legacy_float_body_seal_energy_relation"]
            == case["legacy_relation"]
        )
        assert composition["body_within_support_exact"] == "1/2"
