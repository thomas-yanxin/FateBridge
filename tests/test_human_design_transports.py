"""Actual REST, native MCP and CLI parity with same-run evidence checks."""

import asyncio
import json

import pytest

from tests.ephemeris_case_runtime import native_ephemeris_files_module

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
)


@pytest.mark.parametrize("empty_files", [False, True])
def test_optional_cycle_contacts_and_compact_card_match_all_three_surfaces(
    rest, capsys, monkeypatch, tmp_path, empty_files
):
    from fatebridge.application.examples import evidence_views

    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    params = {
        **INPUT,
        "birth_year": 1980,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 0,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "cycle_reference_datetime": "2029-07-01T00:00:00Z",
    }
    response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            tools = {t.name: t for t in await client.list_tools()}
            schema = tools["human_design"].model_dump(by_alias=True)
            assert "cycle_reference_datetime" in schema["inputSchema"]["properties"]
            result = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not result.is_error
            Draft202012Validator(schema["outputSchema"]).validate(
                result.structured_content
            )
            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["cycles"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert not card.is_error
            if "result_delivery" in card.structured_content:
                assert card.structured_content["result_delivery"][
                    "deferred_fields"
                ] == ["run_metadata.runtime"]
            assert card.structured_content["cycle_summary"] == expected["cycle_summary"]
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        verified = verify_human_design_reading(result)
        assert verified["status"] == "verified_fixed_template_reading"
        assert verified["checked_cycle_evaluation_count"] > 30000
        assert (
            result["cycle_summary"]["phase_arithmetic_method"]
            == "exact_binary_longitude_increments_with_integer_winding_v1"
        )
        for body in result["cycle_context"]["bodies"]:
            assert all("exact_residual" in event for event in body["contacts"])
        assert [b["contact_count"] for b in result["cycle_summary"]["bodies"]] == (
            [1, 3, 0] if empty_files else [1, 3, 3]
        )
        result.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "year,node_mode", [(1800, "true"), (1800, "mean"), (2399, "true"), (2399, "mean")]
)
def test_cycle_range_edges_keep_original_natal_basis_on_actual_three_surfaces(
    rest, capsys, year, node_mode
):
    params = dict(
        birth_year=year,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        node_mode=node_mode,
        require_swiss_files=True,
        cycle_reference_datetime=f"{year+66}-01-01T00:00:00Z",
    )
    response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not result.is_error
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        assert result["cycle_context"]["status"] == "computed_finite_search"
        assert (
            verify_human_design_reading(result)["status"]
            == "verified_fixed_template_reading"
        )
        assert {
            f["de_number"] for f in result["cycle_context"]["source_evidence"]["files"]
        } == {441}
        for body in result["cycle_context"]["bodies"][:2]:
            natal = next(
                a
                for a in result["activations"]["personality"]
                if a["body"] == body["body"]
            )
            assert body["natal_longitude"] == natal["longitude"]
        result.pop("run_metadata")
    assert expected == native == cli


def test_published_first_view_retains_reading_and_source_discrepancy_inline(
    monkeypatch, tmp_path
):
    # Bound the ephemeris inventory, as in an unpacked installation. Operators
    # with many unrelated files retain the full provenance via result_delivery;
    # their inventory length must not change this first-view baseline test.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                {
                    **example_input(SPEC),
                    "fields": suggested_fields(SPEC),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            body = result.structured_content
            assert "result_delivery" not in body
            assert body["bodygraph"]["channels"]
            assert body["interpretation"]["authority_meaning"]
            assert body["interpretation"]["ephemeris_scope"]
            assert (
                body["ephemeris_backend_comparison"]["status"]
                == "same_backend_not_independent"
            )
            assert body["ephemeris_backend_comparison"]["changed_levels"] == []
            assert body["variables"]["status"] == "computed"
            assert body["variables"]["code"]
            assert body["source_consistency"]["discrepancies"]
            assert body["validation"]["prediction"] == "not_validated"

    asyncio.run(call())


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


@pytest.mark.parametrize("node_mode", ["true", "mean"])
@pytest.mark.parametrize("birth_year", [1800, 1900, 1960, 1965, 1990])
def test_full_business_results_identical_across_transports(
    rest, capsys, node_mode, birth_year
):
    params = {
        **INPUT,
        "birth_year": birth_year,
        "node_mode": node_mode,
        "birth_time_uncertainty_minutes": 5,
    }
    response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app()) as client:
            tools = {t.name: t for t in await client.list_tools()}
            tool = tools["human_design"].model_dump(by_alias=True)
            assert {"birth_hour", "birth_minute", "birth_timezone"} <= set(
                tool["inputSchema"]["required"]
            )
            result = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not result.is_error
            Draft202012Validator(tool["outputSchema"]).validate(
                result.structured_content
            )
            return result.structured_content

    via_mcp = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    via_cli = json.loads(capsys.readouterr().out)
    for value in (expected, via_mcp, via_cli):
        assert (
            verify_human_design_reading(value)["status"]
            == "verified_fixed_template_reading"
        )
        value.pop("run_metadata")
    assert expected == via_mcp == via_cli


def test_projected_contract_and_tampered_claim_rejection(rest):
    fields = [
        "bodygraph.type",
        "bodygraph.authority",
        "bodygraph.definition.components",
        "validation.prediction",
        "rule_trace",
        "rulesets",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=INPUT,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    projected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(projected)
    assert "subtype" not in projected["bodygraph"]
    assert projected["validation"] == {"prediction": "not_validated"}
    complete = rest.post(SPEC.rest_path, json=INPUT).json()
    receipt = complete["run_metadata"]
    claim = CalculationClaim(
        path="bodygraph.authority",
        value=complete["bodygraph"]["authority"],
        run_id=receipt["run_id"],
        business_output_sha256=receipt["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(complete, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(
            complete, [claim.model_copy(update={"value": "sacral"})]
        )["status"]
        == "rejected"
    )
    assert verify_calculation_claims(projected, [claim])["status"] == "rejected"


def test_circuitry_card_projects_actual_mechanics_and_its_source_level(rest):
    from fatebridge.application.examples import evidence_views

    fields = evidence_views(SPEC)["circuitry"]["fields"]
    response = rest.post(
        SPEC.rest_path,
        json=INPUT,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(body)
    summary = body["bodygraph"]["circuitry"]
    assert summary["defined_channel_count"] == sum(
        row["channel_count"] for row in summary["circuits"]
    )
    assert body["interpretation"]["circuitry_meaning"]
    source = body["source_consistency"]["channel_classifications"]
    assert source["direct_classifications_checked"] == 6
    assert source["endpoint_inferences_checked"] == 30


def test_integration_group_card_and_conservation_match_all_three_surfaces(
    rest, capsys, monkeypatch, tmp_path
):
    from pathlib import Path

    from fatebridge.application.examples import evidence_views

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    cases = [
        case
        for name in (
            "human-design-official-charts.json",
            "human-design-official-authority-charts.json",
        )
        for case in json.loads((Path(__file__).parent / "fixtures" / name).read_text())[
            "cases"
        ]
    ]
    case = next(
        c
        for c in cases
        if any(
            pair <= {int(x.split(".")[0]) for col in c["columns"].values() for x in col}
            for pair in [{10, 20}, {10, 57}, {20, 34}, {34, 57}]
        )
    )
    fields = evidence_views(SPEC)["circuitry"]["fields"]
    response = rest.post(
        SPEC.rest_path,
        json=case["birth_input"],
        params={"fields": fields, "strict_fields": True},
    )
    assert response.status_code == 200
    expected = response.json()
    summary = expected["bodygraph"]["circuitry"]
    assert summary["integration"]["completed_channel_ids"]
    assert (
        sum(summary["group_channel_counts"].values())
        == summary["defined_channel_count"]
    )
    assert summary["group_membership"]["integration_group"] == "individual"
    assert (
        expected["source_consistency"]["circuit_group_memberships"]["status"]
        == "bounded_public_group_membership_match"
    )

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                {
                    **case["birth_input"],
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert (
                not result.is_error
                and "result_delivery" not in result.structured_content
            )
            return result.structured_content

    actual = asyncio.run(call())
    flags = ["human_design"]
    for key, value in case["birth_input"].items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    command = json.loads(capsys.readouterr().out)
    for value in (expected, actual, command):
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        value.pop("run_metadata", None)
    assert expected == actual == command


def test_joint_transition_case_and_compact_summary_survive_all_three_surfaces(
    rest, capsys, monkeypatch, tmp_path
):
    from datetime import datetime
    from pathlib import Path

    from fatebridge.application.examples import evidence_views

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    case = json.loads(
        (
            Path(__file__).parent / "fixtures/human-design-transition-case.json"
        ).read_text()
    )
    moment = datetime.fromisoformat(case["nominal_birth_utc"])
    params = dict(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_timezone="UTC",
        birth_time_uncertainty_minutes=1,
    )
    expected = rest.post(SPEC.rest_path, json=params).json()
    assert len(expected["time_sensitivity"]["classification_variants"]) == 3
    summary = expected["time_sensitivity"]["joint_transition_refinement_summary"]
    assert (
        summary["additional_evaluation_count"] == 1
        and summary["continuous_interval_certified"] is False
    )

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            full = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not full.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["uncertainty"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert (
                not card.is_error and "result_delivery" not in card.structured_content
            )
            assert (
                card.structured_content["time_sensitivity"][
                    "joint_transition_refinement_summary"
                ]
                == summary
            )
            assert (
                "joint_transition_refinement"
                not in card.structured_content["time_sensitivity"]
            )
            return full.structured_content

    actual = asyncio.run(call())
    flags = ["human_design"]
    for k, v in params.items():
        flags.extend(["--" + k.replace("_", "-"), str(v)])
    assert run(flags) == 0
    command = json.loads(capsys.readouterr().out)
    for value in (expected, actual, command):
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        assert (
            verify_human_design_reading(value)["status"]
            == "verified_fixed_template_reading"
        )
        value.pop("run_metadata")
    assert expected == actual == command


def test_variables_card_returns_typed_paired_evidence_without_certification(rest):
    from fatebridge.application.examples import evidence_views

    response = rest.post(
        SPEC.rest_path,
        json=INPUT,
        params={
            "fields": evidence_views(SPEC)["variables"]["fields"],
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200, response.text
    value = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
    assert value["variables"]["code"] in value["interpretation"]["variables_meaning"]
    assert value["variables"]["subdivision_accuracy_certified"] is False
    assert len(value["variables"]["arrows"]) == 4
    assert all(len(a["basis"]) == 2 for a in value["variables"]["arrows"])
    assert value["validation"]["all_three_axes_full_marks"] is False


@pytest.mark.parametrize(
    "year,month,day,authority,expected_channels",
    [
        (1988, 3, 22, "ego_manifested", ["25-51", "10-20"]),
        (1980, 11, 13, "self_projected", ["13-33"]),
        (1980, 9, 9, "environment_no_inner_authority", []),
        (1980, 11, 18, "lunar_no_inner_authority", []),
    ],
)
def test_actual_three_surfaces_preserve_authority_paths_and_projected_card(
    rest, capsys, year, month, day, authority, expected_channels
):
    from fatebridge.application.examples import evidence_views

    params = {
        "birth_year": year,
        "birth_month": month,
        "birth_day": day,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "Europe/London",
    }
    complete = rest.post(SPEC.rest_path, json=params).json()
    assert (
        verify_human_design_reading(complete)["status"]
        == "verified_fixed_template_reading"
    )
    fields = evidence_views(SPEC)["authority"]["fields"]
    response = rest.post(
        SPEC.rest_path,
        json=params,
        params={"fields": fields, "strict_fields": True, "response_char_limit": 0},
    )
    assert response.status_code == 200, response.text
    via_rest = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            return result.structured_content

    via_mcp = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    flags.extend(["--fields", *fields, "--strict-fields", "--response-char-limit", "0"])
    assert run(flags) == 0
    via_cli = json.loads(capsys.readouterr().out)
    for value in (via_rest, via_mcp, via_cli):
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        value.pop("run_metadata")
        assert value["bodygraph"]["authority"] == authority
        evidence = value["bodygraph"]["classification_evidence"]
        paths = evidence["authority_paths"]
        assert (paths[0]["channel_ids"] if paths else []) == expected_channels
        assert type(evidence["no_inner_authority"]) is bool
        assert value["interpretation"]["authority_structure"]
    assert via_rest == via_mcp == via_cli


@pytest.mark.parametrize(
    "year,month,day,minimum,count",
    [
        (1980, 1, 2, 3, 23),
        (1980, 1, 14, 2, 2),
        (1988, 3, 22, None, 0),
        (1980, 11, 18, None, 0),
    ],
)
def test_definition_bridge_card_is_inline_and_identical_across_actual_surfaces(
    rest, capsys, year, month, day, minimum, count
):
    from fatebridge.application.examples import evidence_views

    params = dict(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Europe/London",
    )
    complete = rest.post(SPEC.rest_path, json=params).json()
    assert (
        verify_human_design_reading(complete)["status"]
        == "verified_fixed_template_reading"
    )
    full_report = complete["definition_bridging"]
    assert full_report["minimum_added_gate_count"] == minimum
    assert len(full_report["minimum_solutions"]) == count
    fields = evidence_views(SPEC)["definition"]["fields"]
    response = rest.post(
        SPEC.rest_path, json=params, params={"fields": fields, "strict_fields": True}
    )
    assert response.status_code == 200, response.text
    via_rest = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            assert "result_delivery" not in result.structured_content
            return result.structured_content

    via_mcp = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    flags.extend(["--fields", *fields, "--strict-fields"])
    assert run(flags) == 0
    via_cli = json.loads(capsys.readouterr().out)
    for value in (via_rest, via_mcp, via_cli):
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        report = value["definition_bridging"]
        assert report["minimum_added_gate_count"] == minimum
        assert report["minimum_solution_count"] == count
        assert report["minimum_solutions_preview"] == [
            {
                k: row[k]
                for k in (
                    "added_gates",
                    "newly_completed_channel_ids",
                    "connects_all_original_components",
                )
            }
            for row in full_report["minimum_solutions"][:3]
        ]
        assert report["preview_is_truncated"] is (count > 3)
        assert "minimum_solutions" not in report
        assert "假设" in report["scope"]
        assert value["interpretation"]["definition_structure"]
        value.pop("run_metadata")
    assert via_rest == via_mcp == via_cli


@pytest.mark.parametrize("node_mode", ["true", "mean"])
def test_precision_card_keeps_backend_differences_distinct_from_node_convention(
    rest, node_mode
):
    from fatebridge.application.examples import evidence_views

    fields = evidence_views(SPEC)["precision"]["fields"]
    response = rest.post(
        SPEC.rest_path,
        json={**INPUT, "node_mode": node_mode},
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(body)
    assert body["node_convention_comparison"]["selected"] == node_mode
    backend = body["node_backend_comparison"]
    assert backend["node_mode"] == node_mode
    assert backend["subdivision_accuracy_certified"] is False
    if node_mode == "mean":
        assert backend["status"] == "analytic_mean_node_not_cross_validated"
        assert backend["rows"] == []
    else:
        assert len(backend["rows"]) == 4
        assert {row["body"] for row in backend["rows"]} == {"NorthNode", "SouthNode"}


@pytest.mark.parametrize(
    "changes",
    [
        {"birth_hour": None},
        {"birth_minute": None},
        {"birth_timezone": "bad-zone"},
        {"birth_month": 2, "birth_day": 30},
        {"use_true_solar_time": True},
        {"node_mode": "auto"},
    ],
)
def test_invalid_input_rejected_on_real_protocols(rest, changes):
    params = {**INPUT, **changes}
    assert rest.post(SPEC.rest_path, json=params).status_code == 422

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "human_design", params, raise_on_error=False
            )
            assert result.is_error

    asyncio.run(call())


@pytest.mark.parametrize("node_mode", ["true", "mean"])
@pytest.mark.parametrize("uncertainty", [0, 10])
def test_joint_uncertainty_card_and_full_witnesses_survive_actual_surfaces(
    rest, capsys, monkeypatch, tmp_path, node_mode, uncertainty
):
    from fatebridge.application.examples import evidence_views

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    params = {
        "birth_year": 1980,
        "birth_month": 2,
        "birth_day": 4,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "node_mode": node_mode,
        "birth_time_uncertainty_minutes": uncertainty,
    }
    full = rest.post(SPEC.rest_path, json=params).json()
    check = verify_human_design_reading(full)
    assert check["status"] == "verified_fixed_template_reading", check
    assert check["checked_joint_snapshot_count"] >= 2
    fields = evidence_views(SPEC)["uncertainty"]["fields"]
    via_rest = rest.post(
        SPEC.rest_path, json=params, params={"fields": fields, "strict_fields": True}
    ).json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            assert "result_delivery" not in result.structured_content
            return result.structured_content

    via_mcp = asyncio.run(call())
    flags = ["human_design"]
    for k, v in params.items():
        flags.extend(["--" + k.replace("_", "-"), str(v)])
    flags.extend(["--fields", *fields, "--strict-fields"])
    assert run(flags) == 0
    via_cli = json.loads(capsys.readouterr().out)
    for value in (via_rest, via_mcp, via_cli):
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        value.pop("run_metadata")
        if uncertainty:
            assert (
                value["time_sensitivity"]["sampling"]["continuous_interval_certified"]
                is False
            )
            if node_mode == "true":
                summary = value["time_sensitivity"]["joint_evidence_summary"]
                assert summary["bridge_families_changed"] is True
                assert summary["bridge_minimum_gate_count_changed"] is False
                assert summary["first_bridge_change"]["added_gate_set_count"] > 0
        else:
            assert value["time_sensitivity"]["status"] == "not_assessed"
            assert value["time_sensitivity"]["joint_evidence_summary"] is None
        if node_mode == "mean":
            assert value["node_backend_comparison"]["joint_evidence_summary"] is None
    assert via_rest == via_mcp == via_cli


@pytest.mark.parametrize("node_mode", ["true", "mean"])
def test_full_backend_ephemeris_card_survives_actual_three_surfaces(
    rest, capsys, monkeypatch, tmp_path, node_mode
):
    from fatebridge.application.examples import evidence_views

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    fields = evidence_views(SPEC)["ephemeris"]["fields"]
    params = {
        **INPUT,
        "node_mode": node_mode,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
    }
    expected = rest.post(
        SPEC.rest_path,
        json={**INPUT, "node_mode": node_mode},
        params={"fields": fields, "strict_fields": True},
    ).json()
    assert (
        expected["ephemeris_backend_comparison"]["status"]
        == "same_backend_not_independent"
    )
    assert expected["ephemeris_backend_comparison"]["joint_evidence_summary"] is None

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool("human_design", params)
            assert (
                not result.is_error
                and "result_delivery" not in result.structured_content
            )
            return result.structured_content

    actual = asyncio.run(call())
    arguments = ["human_design"]
    for key, value in {**INPUT, "node_mode": node_mode}.items():
        arguments += ["--" + key.replace("_", "-"), str(value)]
    assert run([*arguments, "--fields", *fields, "--strict-fields"]) == 0
    command = json.loads(capsys.readouterr().out)
    for value in [expected, actual, command]:
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        assert value["calculation_policy"]["position_frame"] == (
            "geocentric_apparent_tropical_ecliptic_of_date"
        )
        assert value["calculation_policy"]["position_frame_scope"] == "physical_bodies"
        assert value["calculation_policy"]["lunar_node_frame"] == (
            "geocentric_tropical_ecliptic_of_date_mathematical_point"
        )
        assert value["ephemeris_backend_comparison"]["selected_model_scope"] == (
            "all_factor_computation_models"
        )
        value.pop("run_metadata", None)
    assert expected == actual == command


@pytest.mark.parametrize("bad", ["certificate", "status", "provenance"])
def test_fresh_hash_cannot_hide_forged_full_backend_report(monkeypatch, tmp_path, bad):
    from fatebridge.application.execution import execute_tool
    from fatebridge.services.replay_metadata import digest

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    value = execute_tool(SPEC, SPEC.request_model(**INPUT))
    assert (
        verify_human_design_reading(value)["status"]
        == "verified_fixed_template_reading"
    )
    report = value["ephemeris_backend_comparison"]
    if bad == "certificate":
        report["independent_astronomy_certified"] = True
    elif bad == "status":
        report["status"] = "full_backend_compared"
    else:
        report["selected_provenance"]["tt_epochs"]["design"] += 1
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"


@pytest.mark.parametrize("profile", ["4/6", "4/1", "6/3"])
def test_profile_role_card_and_line_basis_survive_all_three_surfaces(
    rest, capsys, monkeypatch, tmp_path, profile
):
    from pathlib import Path

    from fatebridge.application.examples import evidence_views

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    fixtures = Path(__file__).resolve().parent / "fixtures"
    cases = [
        case
        for name in [
            "human-design-official-charts.json",
            "human-design-official-authority-charts.json",
        ]
        for case in json.loads((fixtures / name).read_text())["cases"]
    ]
    case = next(c for c in cases if c["properties"]["Profile"] == profile)
    fields = evidence_views(SPEC)["profile"]["fields"]
    expected = rest.post(
        SPEC.rest_path,
        json=case["birth_input"],
        params={"fields": fields, "strict_fields": True},
    ).json()
    assert expected["profile_evidence"]["status"] == "computed"
    assert expected["profile_evidence"]["profile"] == profile
    assert expected["profile_evidence"]["ruleset"]["version"] == "1.39.0"
    phases = expected["profile_evidence"]["sixth_line_process"]
    assert phases["applicable"] is ("6" in profile)
    assert phases["current_phase"] is None and phases["computed_return_dates"] is None
    if profile == "4/6":
        assert expected["profile_evidence"]["geometry"]["angle"] == "right"
    if profile == "4/1":
        assert expected["profile_evidence"]["geometry"]["angle"] == "juxtaposition"

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design",
                {
                    **case["birth_input"],
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert (
                not result.is_error
                and "result_delivery" not in result.structured_content
            )
            return result.structured_content

    actual = asyncio.run(call())
    flags = ["human_design"]
    for key, value in case["birth_input"].items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    command = json.loads(capsys.readouterr().out)
    for value in [expected, actual, command]:
        Draft202012Validator(SPEC.output_model.model_json_schema()).validate(value)
        value.pop("run_metadata", None)
    assert expected == actual == command
