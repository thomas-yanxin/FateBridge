"""Consumer arithmetic and same-result explanations; no force or efficacy labels."""

import asyncio
import copy
import gzip
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.classical_force import build_force_components
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import StrengthContext
from fatebridge.core.output_classical_force import EngineeringForceComposition
from fatebridge.core.output_strength_thresholds import StrengthThresholdArithmetic
from tests.bazi.test_bazi_strength_thresholds import delivered_payload, evaluate
from tests.support import bazi_strength_reference_v3 as current_reference
from tests.support.transports import SPECS, business, call_cli, native
from tests.support.transports import rest as _rest_fixture

rest = _rest_fixture
DATA = Path(__file__).parents[1] / "data/bazi"
BODY = json.loads((DATA / "consumer-inputs.json").read_text())
SPECIAL = json.loads((DATA / "consumer-special.json").read_text())
CLIMATE = json.loads((DATA / "climate-source-first.json").read_text())
PUBLIC = json.loads((DATA / "public-inputs-first.json").read_text())


def assess(values):
    pillars = dict(zip(("year", "month", "day", "hour"), map(tuple, values)))
    return pillars, ElementAnalysis.analyze_day_master_strength(pillars)

    # These three receipts contain hashes, not complete old result objects.
    # Pin their envelope and provenance; do not forge v11 metadata into an old


@pytest.mark.parametrize("row", BODY, ids=lambda r: str(r["index"]))
def test_current_v11_all_187_budgets_match_independent_literal_season_arithmetic(row):
    pillars, strength = assess(row["pillars"])
    assessment = strength["assessment"]
    assert assessment["method_id"] == "season_root_revelation_relations_v12"
    assert assessment["seasonal_phases"] == current_reference.seasonal_phases(
        row["pillars"][1][1]
    )
    # The relation decisions are premises; this independently verifies their
    # budget arithmetic, not whether those traditional relations should apply.
    expected = current_reference.reconstruct(row["pillars"], assessment["relations"])
    receipt = assessment["threshold_arithmetic"]
    assert receipt["energies_exact"] == {
        element: str(value) for element, value in expected["energies"].items()
    }
    assert receipt["support_exact"] == str(expected["support"])
    assert receipt["weaken_exact"] == str(expected["weaken"])
    assert receipt["share_exact"] == str(expected["share"])
    assert receipt["numerical_label"] == expected["numerical_grade"]
    assert (
        assessment["structural_decision"]["numerical_label"]
        == expected["numerical_grade"]
    )
    assert (
        receipt["requires_special_structure_review"]
        is expected["requires_special_structure_review"]
    )
    assert (
        assessment["requires_special_structure_review"]
        is expected["requires_special_structure_review"]
    )
    force = build_natal_evidence(pillars, strength)["force_components"]
    composition = force["engineering_composition"]
    assert composition["body_energy_exact"] == str(expected["body"])
    assert composition["seal_energy_exact"] == str(expected["seal"])
    assert composition["body_within_support_exact"] == str(
        expected["body_within_support"]
    )
    assert composition["body_seal_energy_relation"] == expected["body_seal_relation"]
    assert set(force["classical_adjudication"].values()) == {"not_adjudicated"}
    EngineeringForceComposition.model_validate(composition)
    StrengthThresholdArithmetic.model_validate(receipt)


@pytest.mark.parametrize("row", SPECIAL, ids=lambda r: str(r["index"]))
def test_current_v11_special_flags_match_independent_exact_inequalities(row):
    _, strength = assess(row["pillars"])
    assessment = strength["assessment"]
    expected = current_reference.reconstruct(row["pillars"], assessment["relations"])
    assert assessment["threshold_arithmetic"]["share_exact"] == str(expected["share"])
    assert (
        assessment["requires_special_structure_review"]
        is expected["requires_special_structure_review"]
    )
    favorable = ElementAnalysis.get_favorable_elements(strength)
    if expected["requires_special_structure_review"]:
        assert favorable == []
    else:
        assert favorable


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
    receipt = evaluate(
        SPECIAL[0]["pillars"],
    )["threshold_arithmetic"]
    patch = dict(patch)
    if "requires_special_structure_review" in patch:
        patch["requires_special_structure_review"] = not receipt[
            "requires_special_structure_review"
        ]
    with pytest.raises(ValidationError):
        StrengthThresholdArithmetic.model_validate({**receipt, **patch})
    assert StrengthThresholdArithmetic.model_validate(
        {"energies_exact": {"水": "1/2"}}
    ).energies_exact == {"水": "1/2"}
    with pytest.raises(ValidationError):
        StrengthContext.model_validate(
            {
                "threshold_arithmetic": receipt,
                "requires_special_structure_review": not receipt[
                    "requires_special_structure_review"
                ],
            }
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
    pillars = dict(zip(current_reference.ORDER, map(tuple, BODY[0]["pillars"])))
    composition = build_force_components(
        pillars,
        evaluate(
            BODY[0]["pillars"],
        ),
        {},
    )["engineering_composition"]
    patch = dict(patch)
    if "body_seal_energy_relation" in patch:
        patch["body_seal_energy_relation"] = (
            "body_greater"
            if composition["body_seal_energy_relation"] != "body_greater"
            else "seal_greater"
        )
    if (
        patch.get("body_within_support_exact")
        == composition["body_within_support_exact"]
    ):
        patch["body_within_support_exact"] = "1/3"
    with pytest.raises(ValidationError):
        EngineeringForceComposition.model_validate({**composition, **patch})
    EngineeringForceComposition.model_validate({"body_energy_exact": "1/3"})


@pytest.mark.parametrize("case", PUBLIC, ids=lambda r: r["id"])
def test_five_fictional_identities_use_v11_reference_on_eleven_tools_and_transports(
    case, rest, tmp_path, capsys
):
    original = next(row for row in [*BODY, *SPECIAL] if row["index"] == case["index"])
    arguments = case["arguments"]
    birth_pillars = BaZiCalendar.get_four_pillars(
        datetime(
            arguments["birth_year"],
            arguments["birth_month"],
            arguments["birth_day"],
            arguments["birth_hour"],
        ),
        timezone_name=arguments["birth_timezone"],
    )
    values = ["".join(birth_pillars[name]) for name in current_reference.ORDER]
    assert values == original["pillars"]
    _, strength = assess(values)
    assessment = strength["assessment"]
    assert assessment["method_id"] == "season_root_revelation_relations_v12"
    expected = current_reference.reconstruct(values, assessment["relations"])
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
    assert receipt["energies_exact"] == {
        element: str(value) for element, value in expected["energies"].items()
    }
    assert receipt["support_exact"] == str(expected["support"])
    assert receipt["weaken_exact"] == str(expected["weaken"])
    assert receipt["share_exact"] == str(expected["share"])
    assert receipt["numerical_label"] == expected["numerical_grade"]
    assert (
        receipt["requires_special_structure_review"]
        is expected["requires_special_structure_review"]
    )
    assert composition["body_energy_exact"] == str(expected["body"])
    assert composition["seal_energy_exact"] == str(expected["seal"])
    assert composition["body_within_support_exact"] == str(
        expected["body_within_support"]
    )
    assert composition["body_seal_energy_relation"] == expected["body_seal_relation"]
