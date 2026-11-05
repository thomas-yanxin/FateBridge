"""Current month references and partial projections retain strict semantics."""

import asyncio
import json

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError
from pydantic import ValidationError

import fatebridge.mcp_server as mcp
from fatebridge.cli import run as cli_run
from fatebridge.core.output_bazi_evidence import EvidenceStructureProfile
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture


@pytest.mark.parametrize(
    "dominant",
    [
        {"key": "default_support"},
        {"key": "default_support", "useful_elements": ["火"]},
        {"useful_elements": ["火"]},
        {"key": "selected_month_reference", "formation_status": "formed"},
        {"key": "selected_month_reference", "useful_elements": ["火"]},
    ],
)
def test_current_policy_cannot_accept_legacy_promotion_or_unadjudicated_preferences(
    dominant,
):
    payload = {
        "resolution_policy": "source_conditions_before_preference_v3",
        "dominant_structure": dominant,
    }
    with pytest.raises(ValidationError):
        EvidenceStructureProfile.model_validate(payload)
    with pytest.raises(SchemaError):
        Draft202012Validator(EvidenceStructureProfile.model_json_schema()).validate(
            payload
        )


@pytest.mark.parametrize("policy", [None, "layered_conflict_review_v1"])
@pytest.mark.parametrize(
    "dominant",
    [
        {"key": "selected_month_reference", "useful_elements": ["火"]},
        {"key": "selected_month_reference", "avoid_elements": ["水"]},
        {"key": "selected_month_reference", "useful_ten_gods": ["正印"]},
        {"key": "selected_month_reference", "formation_status": "formed"},
    ],
)
def test_current_key_alone_never_bypasses_month_reference_semantics(policy, dominant):
    payload = {"dominant_structure": dominant}
    if policy is not None:
        payload["resolution_policy"] = policy
    with pytest.raises(ValidationError):
        EvidenceStructureProfile.model_validate(payload)
    with pytest.raises(SchemaError):
        Draft202012Validator(EvidenceStructureProfile.model_json_schema()).validate(
            payload
        )


def test_current_profile_and_version_conditions_agree_on_three_surfaces(
    rest, tmp_path, capsys
):
    spec = SPECS["bazi_birth"]
    payload = inputs(spec)
    options = {
        "fields": ["bazi_birth.structure_profile"],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    protocol = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            "bazi_birth.structure_profile",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    http = rest.post(spec.rest_path, json=payload, params={"as_of": AS_OF, **options})
    assert not protocol.is_error and code == 0 and http.status_code == 200
    assert (
        business(protocol.structured_content) == business(cli) == business(http.json())
    )
    profile = cli["bazi_birth"]["structure_profile"]
    assert profile["resolution_policy"] == "source_conditions_before_preference_v3"
    assert profile["dominant_structure"]["key"] == "selected_month_reference"
    assert profile["dominant_structure"]["formation_status"] == "not_adjudicated"
    for key in ("useful_elements", "avoid_elements", "useful_ten_gods"):
        assert profile["dominant_structure"][key] == []

    async def native_schema():
        async with Client(mcp.app) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
        return tools[spec.tool_name].model_dump(by_alias=True)["outputSchema"]

    assert cli_run(["describe", spec.tool_name]) == 0
    cli_schema = json.loads(capsys.readouterr().out)["output_schema"]
    advertised = {
        tool["tool"]: tool["output_schema"]
        for tool in rest.get("/api/tools").json()["tools"]
    }
    schemas = [
        spec.output_model.model_json_schema(),
        cli_schema,
        advertised[spec.tool_name],
        asyncio.run(native_schema()),
    ]
    assert all(schema == schemas[0] for schema in schemas)
    historical = {
        "bazi_birth": {
            "structure_profile": {
                "resolution_policy": "layered_conflict_review_v1",
                "dominant_structure": {
                    "key": "default_support",
                    "useful_elements": ["火"],
                },
            }
        }
    }
    for schema in schemas:
        validator = Draft202012Validator(schema)
        validator.validate(business(cli))
        with pytest.raises(SchemaError):
            validator.validate(historical)
        historical["bazi_birth"]["structure_profile"][
            "resolution_policy"
        ] = "source_conditions_before_preference_v3"
        with pytest.raises(SchemaError):
            validator.validate(historical)
        historical["bazi_birth"]["structure_profile"][
            "resolution_policy"
        ] = "layered_conflict_review_v1"
