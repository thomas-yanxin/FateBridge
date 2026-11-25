import asyncio
import json
import re

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
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls


def _build_client(monkeypatch) -> TestClient:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    return TestClient(api_module.app)


def _assert_run_metadata(payload: dict) -> None:
    pending = [payload]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            assert not any(
                re.search(
                    r"(?:^|_)(?:sha\d*|hash|hashes|digest|fingerprint)(?:_|$)",
                    key,
                    re.I,
                )
                for key in item
            )
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, str):
            assert not re.fullmatch(r"[0-9a-f]{64}", item)
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
            for definition in original.get("$defs", {}).values():
                assert not any(
                    re.search(r"sha\d+|fingerprint|(?:^|_)hash(?:_|$)", key, re.I)
                    for key in definition.get("properties", {})
                )
            total_wire += len(json.dumps(published["outputSchema"]))
            total_original += len(json.dumps(original))
    assert total_wire == total_original


def test_rest_reserved_field_guard_rejects_clashing_model():
    """A request model that declares a reserved transport field must fail loud."""
    from pydantic import BaseModel

    from fatebridge.application.bindings import person_invoke
    from fatebridge.application.tool_spec import ToolSpec
    from fatebridge.transports.rest import register_rest

    class _Clashing(BaseModel):
        fields: str = ""  # collides with the REST projection query param

    bad = ToolSpec(
        key="_clash",
        bind=person_invoke(lambda *_a, **_k: {}),
        request_model=_Clashing,
        summary="x",
        operation_label_zh="x",
        family="x",
        rest_path="/api/_clash",
    )

    class _DummyApp:
        def add_api_route(self, *a, **k):  # pragma: no cover - never reached
            raise AssertionError("route mounted despite reserved-field clash")

    with pytest.raises(ValueError, match="reserved"):
        register_rest(_DummyApp(), [bad], execute_service=lambda *a, **k: None)


@pytest.mark.parametrize(
    ("tool_name", "arguments", "fields"),
    [
        ("export_registry", {"technique": "generic"}, ["selected_technique.key"]),
        ("knowledge_registry", {"domain": "qimen"}, ["domains"]),
        (
            "knowledge_read",
            {"domain": "qimen", "key": "休门"},
            ["domain", "category", "key", "rendered_text"],
        ),
    ],
)
def test_reference_helpers_match_strict_projection_and_clock(
    tool_name, arguments, fields, surface_calls
):
    response, protocol, code, local = surface_calls(
        SPECS[tool_name],
        arguments,
        projection={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
        rest_as_of=AS_OF,
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    assert code == 0, local
    outputs = [response.json(), protocol.structured_content, local]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        _assert_run_metadata(output)
        assert output["run_metadata"]["tool_name"] == tool_name
        assert output["run_metadata"]["effective_time"]["as_of"] == AS_OF
        assert set(output) == {field.split(".")[0] for field in fields} | {
            "run_metadata"
        }
    if tool_name == "knowledge_read":
        assert local["category"] == "door"
        assert local["key"] == "休门"
        assert "休养" in local["rendered_text"]
    elif tool_name == "knowledge_registry":
        assert local["domains"][0]["domain"] == "qimen"
        assert any(
            category["name"] == "door" and "休门" in category["keys"]
            for category in local["domains"][0]["categories"]
        )
    else:
        assert local["selected_technique"] == {"key": "generic"}


@pytest.mark.parametrize(
    ("content", "selection", "expected_titles", "expected_blocks", "expected_missing"),
    [
        ("", [], [], [], ["起盘信息"]),
        (
            "[公开]\n中文 ☊ 😀 é\n\n【空段】\n\n[公开]\n第二段\n\n[空段]",
            ["公开", "空段", "公开"],
            ["公开", "空段"],
            ["[公开]\n中文 ☊ 😀 é", "【空段】", "[公开]\n第二段", "[空段]"],
            [],
        ),
    ],
)
def test_export_parse_roundtrip_preserves_unicode_empty_and_repeated_sections(
    content,
    selection,
    expected_titles,
    expected_blocks,
    expected_missing,
    surface_calls,
):
    request = {
        "technique": "generic",
        "content": content,
        "selected_sections": selection,
    }
    fields = [
        "export_text",
        "sections",
        "section_titles_detected",
        "selected_sections",
        "missing_selected_sections",
    ]
    first = None
    for _ in range(2):
        response, protocol, code, local = surface_calls(
            SPECS["export_parse"],
            request,
            projection={
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
            rest_as_of=AS_OF,
        )
        assert response.status_code == 200, response.text
        assert not protocol.is_error, protocol.content
        assert json.loads(protocol.content[0].text) == protocol.structured_content
        assert code == 0, local
        outputs = [response.json(), protocol.structured_content, local]
        assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
        for output in outputs:
            assert output["run_metadata"]["effective_time"]["as_of"] == AS_OF
        parsed = business(local)
        assert parsed["section_titles_detected"] == expected_titles
        assert parsed["missing_selected_sections"] == expected_missing
        assert [section["content"] for section in parsed["sections"]] == expected_blocks
        assert all(section["included"] for section in parsed["sections"])
        assert parsed["export_text"] == "\n\n".join(expected_blocks)
        if first is None:
            first = parsed
        else:
            assert parsed == first
        request["content"] = parsed["export_text"]
