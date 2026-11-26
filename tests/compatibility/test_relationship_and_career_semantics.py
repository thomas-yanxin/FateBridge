"""Relationship selection and natal evidence through the public transports."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import JsonValue, ValidationError

from fatebridge.application.examples import example_input
from fatebridge.cli import run
from fatebridge.core.requests.compatibility import TwoPersonCompatibilityRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation, rest

SPECS = {
    spec.name: spec
    for spec in CATALOG
    if spec.name in {"bazi_compatibility", "bazi_career"}
}


async def mcp_call(tool: str, inputs: dict[str, JsonValue]) -> CallToolResult:
    async with Client(create_mcp_app(families=SPECS[tool].family)) as client:
        return await call_calculation(
            client,
            SPECS[tool].name,
            inputs,
            raise_on_error=False,
        )


def cli_call(
    tool: str, inputs: dict[str, JsonValue], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, JsonValue]]:
    """Exercise the published flags for flat birth and pair requests."""
    args = [SPECS[tool].name, "--detail", "audit"]
    for field, value in inputs.items():
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        args.extend(["--" + field.replace("_", "-"), rendered])
    code = run(args)
    return code, json.loads(capsys.readouterr().out)


def test_relationship_schema_lists_exactly_the_supported_rules() -> None:
    schema = TwoPersonCompatibilityRequest.model_json_schema()
    field = schema["properties"]["relationship_type"]
    assert set(field["enum"]) == {
        "general",
        "marriage",
        "friendship",
        "business",
        "family",
    }
    assert field["default"] == "general"
    inputs = example_input(SPECS["bazi_compatibility"])
    inputs.pop("relationship_type")
    assert TwoPersonCompatibilityRequest(**inputs).relationship_type == "general"


@pytest.mark.parametrize("invalid", ["business_partner", "Marriage", "", None, 7])
def test_invalid_relationship_matches_all_transports(
    rest: TestClient, capsys: pytest.CaptureFixture[str], invalid: str | int | None
) -> None:
    tool = "bazi_compatibility"
    inputs = {**example_input(SPECS[tool]), "relationship_type": invalid}
    with pytest.raises(ValidationError):
        TwoPersonCompatibilityRequest(**inputs)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(
            TwoPersonCompatibilityRequest.model_json_schema()
        ).validate(inputs)
    response = rest.post(SPECS[tool].rest_path, json=inputs, params={"detail": "audit"})
    protocol = asyncio.run(mcp_call(tool, inputs))
    code, cli = cli_call(tool, inputs, capsys)
    assert response.status_code == 422 and protocol.is_error and code == 1
    bodies = [response.json(), protocol.structured_content, cli]
    for body in bodies:
        assert body["error_code"] == "validation_error"
        assert body["issues"][0]["path"] == "relationship_type"
        assert body["issues"][0]["code"] == "literal_error"
        assert not body["retryable"]
    assert bodies[0]["issues"] == bodies[1]["issues"] == bodies[2]["issues"]


@pytest.mark.parametrize(
    "kind",
    [None, "general", "marriage", "friendship", "business", "family"],
)
def test_relationship_facts_match_across_transports(
    rest: TestClient, capsys: pytest.CaptureFixture[str], kind: str | None
) -> None:
    tool = "bazi_compatibility"
    inputs = example_input(SPECS[tool])
    if kind is None:
        inputs.pop("relationship_type")
    else:
        inputs["relationship_type"] = kind
    response = rest.post(SPECS[tool].rest_path, json=inputs, params={"detail": "audit"})
    protocol = asyncio.run(mcp_call(tool, inputs))
    code, cli = cli_call(tool, inputs, capsys)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    bodies = [response.json(), protocol.structured_content, cli]
    for body in bodies:
        assert body["relationship_type"] == (kind or "general")
        assert set(body["natal_contexts"]) == {"person1", "person2"}
        assert body["cross_chart_relations"]["pairs"]
        assert body["directional_ten_gods"]["person1_to_person2"]["target"] == "person2"
    for key in ("natal_contexts", "cross_chart_relations", "directional_ten_gods"):
        assert bodies[0][key] == bodies[1][key] == bodies[2][key]


def test_career_semantics_match_rest_mcp_cli(
    rest: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    tool = "bazi_career"
    inputs = {
        **example_input(SPECS[tool]),
        "dayun_pillar": "甲申",
        "liunian_pillar": "丙午",
    }
    response = rest.post(SPECS[tool].rest_path, json=inputs, params={"detail": "audit"})
    protocol = asyncio.run(mcp_call(tool, inputs))
    code, cli = cli_call(tool, inputs, capsys)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    career = [
        body["career_analysis"]
        for body in [response.json(), protocol.structured_content, cli]
    ]
    assert career[0] == career[1] == career[2]
    assert career[0]["timing_context"]["dayun_pillar"] == "甲申"
    assert career[0]["timing_context"]["liunian_pillar"] == "丙午"
    assert career[0]["evidence_chain"]["topic"]["stars"]["正官"]
