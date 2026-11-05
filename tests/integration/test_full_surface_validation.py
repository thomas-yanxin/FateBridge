import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api_module
import fatebridge.mcp_server as mcp_module
from fatebridge.core.schema_cache import model_schema
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import (
    MCP_CASES,
    REST_GET_CASES,
    REST_POST_CASES,
)


def _build_client(monkeypatch) -> TestClient:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api_module.app)


def _assert_run_metadata(payload: dict) -> None:
    metadata = payload.get("run_metadata")
    assert isinstance(metadata, dict)
    assert metadata["tool_name"]
    assert metadata["engine"]
    assert metadata["run_id"]
    assert metadata["trace_id"]
    assert metadata["generated_at"]


def test_rest_case_map_covers_all_business_routes():
    actual_paths = {
        route.path
        for route in api_module.app.routes
        if getattr(route, "path", None)
        and not route.path.startswith("/openapi")
        and not route.path.startswith("/docs")
        and not route.path.startswith("/redoc")
    }
    # Result readers take opaque IDs from a prior calculation, so their live
    # success/auth/error cases are in test_result_delivery and
    # test_ziwei_twenty_third_iteration (verified reads), not static GETs.
    result_reader_paths = {
        "/api/results/{result_id}",
        "/api/results/{result_id}/pages",
        "/api/results/{result_id}/verified",
    }
    expected_paths = set(REST_GET_CASES) | set(REST_POST_CASES) | result_reader_paths

    assert expected_paths == actual_paths


def test_mcp_case_map_covers_all_registered_tools():
    actual_names = {
        tool.name
        for tool in asyncio.run(mcp_module.app.list_tools(run_middleware=False))
    }

    assert set(MCP_CASES) == actual_names


def test_rest_health_endpoints_return_expected_contract(monkeypatch):
    client = _build_client(monkeypatch)

    for path, assertion in REST_GET_CASES.items():
        response = client.get(path)
        assert response.status_code == 200
        if path == "/metrics":
            assert "fatebridge_http_requests_total" in response.text
            continue
        assertion(response.json())


@pytest.mark.parametrize("path", REST_POST_CASES)
def test_rest_post_endpoints_all_accept_representative_payloads(monkeypatch, path):
    client = _build_client(monkeypatch)
    response = client.post(path, json=REST_POST_CASES[path]())
    assert response.status_code == 200, path
    body = response.json()
    assert "error" not in body, path
    _assert_run_metadata(body)


@pytest.mark.parametrize("name", MCP_CASES)
def test_shared_execution_accepts_all_mcp_representative_payloads(name):
    from fatebridge.application.execution import execute_tool

    by_name = {spec.tool_name: spec for spec in CATALOG}
    spec = by_name[name]
    body = execute_tool(spec, spec.request_model.model_validate(MCP_CASES[name][1]()))
    assert "error" not in body, name
    _assert_run_metadata(body)


@pytest.mark.parametrize(
    "names", [tuple(MCP_CASES)[i::6] for i in range(6)], ids=lambda names: names[0]
)
def test_fastmcp_client_accepts_all_representative_payloads(names, mcp_output_models):
    """Exercise protocol validation and defaults, which direct .fn skips."""

    async def run():
        async with Client(mcp_module.app) as client:
            for name in names:
                result = await client.call_tool(name, MCP_CASES[name][1]())
                body = json.loads(result.content[0].text)
                assert "error" not in body, name
                _assert_run_metadata(body)
                assert result.structured_content == body
                Draft202012Validator(model_schema(mcp_output_models[name])).validate(
                    body
                )

    asyncio.run(run())


@pytest.fixture(scope="module")
def mcp_output_models():
    # Publication equality is checked once below. Response cases reuse those
    # canonical models instead of serializing every wire schema for each batch.
    return {
        spec.tool_name: spec.output_model
        for spec in CATALOG
        if spec.mcp_name and spec.output_model is not None
    }


@pytest.mark.asyncio
async def test_all_published_schemas_keep_valid_shared_references():
    from jsonschema.validators import validator_for

    async with Client(mcp_module.app) as client:
        tools = await client.list_tools()
    by_name = {s.tool_name: s for s in CATALOG if s.mcp_name}
    total_wire = 0
    total_original = 0
    checked_schemas = set()
    for tool in tools:
        published = tool.model_dump(by_alias=True)
        for schema in [
            published["inputSchema"],
            published["outputSchema"],
        ]:
            if schema is not None:
                signature = json.dumps(schema, sort_keys=True)
                if signature not in checked_schemas:
                    validator_for(schema).check_schema(schema)
                    checked_schemas.add(signature)
        if published["outputSchema"] is not None:
            original = model_schema(by_name[tool.name].output_model)
            assert published["outputSchema"] == original
            total_wire += len(json.dumps(published["outputSchema"]))
            total_original += len(json.dumps(original))
    assert total_wire == total_original
