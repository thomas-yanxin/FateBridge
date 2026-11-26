import asyncio
import json
import re
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for
from pydantic import BaseModel, JsonValue

import fatebridge.api as api_module
import fatebridge.mcp_server as mcp_module
from fatebridge.application.execution import execute_with_receipt
from fatebridge.cli import run
from fatebridge.core.schema_cache import model_schema
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.transports.rest import register_rest
from tests.fixtures.surface_payloads import (
    MCP_CASES,
    REST_GET_CASES,
    REST_POST_CASES,
)
from tests.support.output_facts import canonical_json
from tests.support.transports import (
    AS_OF,
    SPECS,
    cached_mcp_app,
    cached_output_validator,
    call_calculation,
    describe_capability,
    discover_capabilities,
    surface_calls,
)


def assert_public_run_metadata(payload: dict[str, JsonValue]) -> None:
    pending: list[JsonValue] = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            assert not any(
                re.search(
                    r"(?:^|_)(?:sha\d*|hash|hashes|digest|fingerprint)(?:_|$)",
                    field_name,
                    re.I,
                )
                for field_name in value
            )
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            assert not re.fullmatch(r"[0-9a-f]{64}", value)
        else:
            pass
    metadata = payload.get("run_metadata")
    assert isinstance(metadata, dict)
    assert metadata["tool_name"]
    assert metadata["engine"]
    assert metadata["run_id"]
    assert metadata["generated_at"]


def test_rest_case_map_covers_all_business_routes() -> None:
    actual_paths = {
        route.path
        for route in api_module.app.routes
        if getattr(route, "path", None)
        and getattr(route, "include_in_schema", False)
        and not route.path.startswith("/openapi")
        and not route.path.startswith("/docs")
        and not route.path.startswith("/redoc")
    }
    expected_paths = set(REST_GET_CASES) | set(REST_POST_CASES)

    assert expected_paths == actual_paths


@pytest.mark.asyncio
async def test_mcp_case_map_covers_all_discovered_capabilities() -> None:
    async with Client(cached_mcp_app()) as client:
        assert set(await discover_capabilities(client)) == set(MCP_CASES)


def test_renamed_tool_accepts_only_the_public_name_on_all_surfaces(
    rest: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    new_path = "/api/divination/gua"
    old_path = "/api/divination/gua/meanings"
    new_name = "gua_lookup"
    old_name = "gua_meanings"
    routes_by_path = {
        r.path: r
        for r in api_module.app.routes
        if getattr(r, "path", None) and getattr(r, "include_in_schema", False)
    }
    assert routes_by_path[new_path].operation_id == new_name
    assert old_path not in routes_by_path
    args = {"queries": ["111111"]}
    http = rest.post(new_path, json=args)
    assert http.status_code == 200
    assert rest.post(old_path, json=args).status_code == 404
    assert rest.get("/api/tools", params={"tool": old_name}).status_code == 404

    async def call_mcp() -> list[dict[str, JsonValue]]:
        results: list[dict[str, JsonValue]] = []
        for family in (None, "divination"):
            async with Client(cached_mcp_app(family)) as native:
                names = await discover_capabilities(native)
                assert new_name in names and old_name not in names
                for endpoint, params in (
                    ("discover_tools", {"tool": old_name}),
                    ("run_calculation", {"tool": old_name, "arguments": args}),
                ):
                    rejected = await native.call_tool(
                        endpoint, params, raise_on_error=False
                    )
                    assert rejected.is_error
                    assert (
                        rejected.structured_content["issues"][0]["code"]
                        == "unknown_tool"
                    )
                result = await call_calculation(native, new_name, args)
                assert result.structured_content is not None
                results.append(result.structured_content)
        return results

    assert run([old_name, "--queries", "111111"]) == 2
    assert json.loads(capsys.readouterr().out)["error_code"] == "usage_error"
    assert run(["discover", old_name]) == 2
    err = json.loads(capsys.readouterr().out)
    assert err["error_code"] == "validation_error"
    assert err["issues"][0]["code"] == "unknown_tool"
    assert run([new_name, "--queries", "111111", "--detail", "audit"]) == 0
    results = [
        http.json(),
        json.loads(capsys.readouterr().out),
        *asyncio.run(call_mcp()),
    ]
    assert all(result["run_metadata"]["tool_name"] == new_name for result in results)
    assert all(result["results"] == results[0]["results"] for result in results[1:])


def test_rest_rejects_retired_nested_relationship_payload(rest: TestClient) -> None:
    path = "/api/astrology/relationship-chart"
    current = REST_POST_CASES[path]()
    old = {
        side: {
            key.removeprefix(side + "_"): value
            for key, value in current.items()
            if key.startswith(side + "_")
        }
        for side in ("inner", "outer")
    }
    response = rest.post(path, json=old)
    assert response.status_code == 422
    assert {
        issue["path"]
        for issue in response.json()["issues"]
        if issue["code"] == "extra_forbidden"
    } == {"inner", "outer"}


def test_rest_health_endpoints_return_expected_contract(rest: TestClient) -> None:
    for path, assertion in REST_GET_CASES.items():
        response = rest.get(
            path, params={"detail": "summary"} if path == "/api/tools" else None
        )
        assert response.status_code == 200
        if path == "/metrics":
            assert "fatebridge_http_requests_total" in response.text
            continue
        else:
            pass
        assertion(response.json())


@pytest.mark.parametrize("path", REST_POST_CASES)
def test_rest_post_endpoints_all_accept_representative_payloads(
    rest: TestClient, path: str
) -> None:
    response = rest.post(path, json=REST_POST_CASES[path]())
    assert response.status_code == 200, path
    body = response.json()
    assert "error" not in body, path
    assert_public_run_metadata(body)


def mcp_tool_batches() -> list[tuple[str, ...]]:
    heavy = (
        "horary_chart",
        "evaluate_election_time",
        "canping",
        "bazi_compatibility",
        "bazi_timing",
    )
    heavy_set = {name for name in heavy if name in MCP_CASES}
    rest_names = [name for name in MCP_CASES if name not in heavy_set]
    return [(name,) for name in heavy if name in heavy_set] + [
        tuple(rest_names[i::6]) for i in range(6) if rest_names[i::6]
    ]


@pytest.mark.parametrize("names", mcp_tool_batches(), ids=lambda names: names[0])
@pytest.mark.asyncio
async def test_fastmcp_client_accepts_all_representative_payloads(
    names: tuple[str, ...], mcp_output_models: dict[str, type[BaseModel]]
) -> None:
    """Check successful envelopes and schema validation through an MCP client."""
    async with Client(mcp_module.app) as client:
        for tool_name in names:
            result = await call_calculation(
                client, tool_name, MCP_CASES[tool_name][1](), raise_on_error=False
            )
            assert not result.is_error, (tool_name, result.structured_content)
            body = result.structured_content
            assert body is not None, tool_name
            assert "error" not in body, tool_name
            assert_public_run_metadata(body)
            cached_output_validator(mcp_output_models[tool_name]).validate(body)


@pytest.fixture(scope="module")
def mcp_output_models() -> dict[str, type[BaseModel]]:
    # note (contracts): The schema publication test checks the same canonical models once.
    return {
        spec.name: spec.output_model
        for spec in CATALOG
        if spec.expose_mcp and spec.output_model is not None
    }


def assert_local_schema_defs(schema: dict[str, JsonValue]) -> None:
    definitions = schema.get("$defs", {})
    assert isinstance(definitions, dict)
    pending: list[JsonValue] = [schema]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/$defs/"):
                target = reference.removeprefix("#/$defs/").split("/", 1)[0]
                assert target in definitions, reference
            else:
                pass
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        else:
            pass


@pytest.mark.asyncio
async def test_all_published_schemas_keep_valid_shared_references() -> None:
    validated_definitions: set[tuple[type[Draft202012Validator], str]] = set()
    meta_validators: dict[type[Draft202012Validator], Draft202012Validator] = {}
    async with Client(mcp_module.app) as client:
        default_tools = await client.list_tools()
    for tool in default_tools:
        published = tool.model_dump(by_alias=True)
        assert published["outputSchema"] is None
        schema = published["inputSchema"]
        assert_local_schema_defs(schema)
        validator_type = validator_for(schema)
        if validator_type not in meta_validators:
            meta_validators[validator_type] = validator_type(validator_type.META_SCHEMA)
        else:
            pass
        meta_validator = meta_validators[validator_type]
        definitions = schema.get("$defs")
        if isinstance(definitions, dict):
            # note (contracts): Shared definitions use the same meta-schema across most tools.
            for definition in definitions.values():
                definition_identity = (
                    validator_type,
                    json.dumps(definition, sort_keys=True),
                )
                if definition_identity not in validated_definitions:
                    meta_validator.validate(definition)
                    validated_definitions.add(definition_identity)
                else:
                    pass
            meta_validator.validate(
                {name: value for name, value in schema.items() if name != "$defs"}
            )
        else:
            meta_validator.validate(schema)

    by_name = {s.name: s for s in CATALOG if s.expose_mcp}
    representatives = (
        "bazi_birth_chart",
        "astrology_chart",
        "gua_lookup",
        "fengshui_xuankong_house_chart",
        "ziwei_birth_chart",
    )
    async with Client(cached_mcp_app()) as client:
        discovered = set(await discover_capabilities(client))
        assert discovered == set(by_name)
        for name in representatives:
            published = await describe_capability(
                client, name, detail="full", include_output_schema=True
            )
            assert_local_schema_defs(published["input_schema"])
            published_output_schema = published["output_schema"]
            assert isinstance(published_output_schema, dict), name
            assert_local_schema_defs(published_output_schema)
            output_model = by_name[name].output_model
            assert output_model is not None, name
            assert published_output_schema == model_schema(output_model)

    for spec in by_name.values():
        if spec.request_model is not None:
            assert_local_schema_defs(model_schema(spec.request_model))
        else:
            pass
        if spec.output_model is not None:
            original = model_schema(spec.output_model)
            assert_local_schema_defs(original)
            for definition in original.get("$defs", {}).values():
                assert not any(
                    re.search(r"sha\d+|fingerprint|(?:^|_)hash(?:_|$)", key, re.I)
                    for key in definition.get("properties", {})
                )
        else:
            pass


def test_rest_reserved_field_guard_rejects_clashing_model() -> None:
    """Reject a request field named after the REST projection query parameter."""

    class ConflictingRequest(BaseModel):
        fields: str = ""

    catalog_spec = next(spec for spec in CATALOG if spec.name == "gua_lookup")
    spec = replace(catalog_spec, request_model=ConflictingRequest)

    app = FastAPI()
    existing_routes = list(app.routes)
    with pytest.raises(ValueError, match="reserved"):
        register_rest(app, [spec], execute_service=execute_with_receipt)
    assert app.routes == existing_routes


@pytest.mark.parametrize(
    ("spec_key", "arguments", "field", "expected"),
    [
        ("knowledge_read", {"domain": "qimen", "key": "休门"}, "category", "door"),
    ],
)
def test_reference_helpers_share_strict_projection_and_clock(
    spec_key: str,
    arguments: dict[str, JsonValue],
    field: str,
    expected: JsonValue,
    surface_calls,
) -> None:
    spec = SPECS[spec_key]
    response, protocol, code, cli = surface_calls(
        spec,
        arguments,
        projection={
            "detail": "audit",
            "fields": [field],
        },
        rest_as_of=AS_OF,
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    assert protocol.content == []
    root = field.partition(".")[0]
    assert canonical_json({root: expected}) == canonical_json(cli)
    for result in (response.json(), protocol.structured_content, cli):
        assert canonical_json(result) == canonical_json(cli)
        assert_public_run_metadata(result)
        assert result["run_metadata"]["tool_name"] == spec.name
        assert result["run_metadata"]["effective_time"]["as_of"] == AS_OF
