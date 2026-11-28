"""Every object reachable by field projection must accept missing siblings."""

import asyncio
import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import JsonValue, ValidationError

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.application.projection import project_fields
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.cli import run
from fatebridge.core.fengshui.models import Coverage
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import PAYLOADS, payload
from tests.support.current_outputs import current_business
from tests.support.transports import (
    cached_output_validator,
    call_calculation,
    capability_contracts,
)

SPECS = {spec.name: spec for spec in CATALOG}
AS_OF = "2026-10-12T02:00:00Z"


class CurrentBusiness(Protocol):
    def __call__(self, name: str, /) -> ServiceResult: ...


def test_tool_specific_nested_contracts_are_published_at_the_catalog_root() -> None:
    for spec in CATALOG:
        assert "run_metadata" in spec.output_model.model_fields, spec.name
        assert set(spec.required_output_fields) <= set(
            spec.output_model.model_fields
        ), spec.name


def projectable_objects(
    root: ServiceResult,
    node: ServiceResult,
    path: tuple[str, ...] = (),
    refs: set[tuple[str, bool]] | None = None,
) -> Iterator[tuple[tuple[str, ...], ServiceResult]]:
    """Follow references/unions/map values, but never traverse array items.

    run_metadata is preserved whole by the projector, even when a child is
    requested. Required receipt facts therefore cannot cause this defect.
    """
    if path[:1] == ("run_metadata",):
        return
    if refs is None:
        refs = set()
    if "$ref" in node:
        ref = node["$ref"]
        position = (ref, bool(path))
        if position in refs:
            return
        refs.add(position)
        target = root
        assert ref.startswith("#/")
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        yield from projectable_objects(root, target, path, refs)
        return
    if node.get("type") == "object" or "properties" in node:
        yield path, node
    for name, child in node.get("properties", {}).items():
        yield from projectable_objects(root, child, (*path, name), refs)
    values = node.get("additionalProperties")
    if isinstance(values, dict):
        yield from projectable_objects(root, values, (*path, "{}"), refs)
    for keyword in ("anyOf", "oneOf", "allOf"):
        for child in node.get(keyword, []):
            yield from projectable_objects(root, child, path, refs)


def leaves(
    value: JsonValue, path: tuple[str, ...] = ()
) -> Iterator[tuple[str, JsonValue]]:
    # The API traverses objects only; nulls, scalars and arrays are whole values.
    if isinstance(value, dict) and value:
        if any("." in key or key.strip() != key for key in value):
            yield ".".join(path), value
        else:
            for key, child in value.items():
                if path or key != "run_metadata":
                    yield from leaves(child, (*path, key))
    elif path:
        yield ".".join(path), value


@pytest.mark.parametrize("key", list(SPECS))
def test_every_current_leaf_projection_validates_without_rewriting_facts(
    key: str, current_business: CurrentBusiness
) -> None:
    spec = SPECS[key]
    result = copy.deepcopy(current_business(key))
    before = copy.deepcopy(result)
    spec.output_model.model_validate(result)
    validator = cached_output_validator(spec.output_model)
    for field, expected in leaves(result):
        projected = project_fields(result, [field])
        spec.output_model.model_validate(projected)
        validator.validate(projected)
        value = projected
        for part in field.split("."):
            value = value[part]
        assert value == expected
    assert result == before


@pytest.fixture
def rest(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


def test_all_published_schemas_preserve_object_projection_compatibility(
    rest: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = {
        spec.name: rest.get(
            "/api/tools",
            params={
                "tool": spec.name,
                "detail": "full",
                "include_output_schema": True,
            },
        ).json()["output_schema"]
        for spec in CATALOG
    }
    openapi = rest.get("/openapi.json").json()

    async def native_schemas() -> dict[str, ServiceResult]:
        async with Client(mcp.app) as default_client:
            default_tools = await default_client.list_tools()
            assert all(
                tool.model_dump(by_alias=True)["outputSchema"] is None
                for tool in default_tools
            )
        async with Client(mcp.create_mcp_app()) as client:
            return {
                name: contract["output_schema"]
                for name, contract in (
                    await capability_contracts(
                        client, detail="full", include_output_schema=True
                    )
                ).items()
            }

    published = asyncio.run(native_schemas())
    assert set(published) == {spec.name for spec in CATALOG if spec.expose_mcp}
    for spec in CATALOG:
        central = spec.output_model.model_json_schema()
        assert (
            run(
                [
                    "discover",
                    "--tool",
                    spec.name,
                    "--detail",
                    "full",
                    "--include-output-schema",
                ]
            )
            == 0
        )
        cli = json.loads(capsys.readouterr().out)["output_schema"]
        assert central == cli == manifest[spec.name]
        roots = [(central, central)]
        if spec.expose_mcp:
            roots.append((published[spec.name], published[spec.name]))
        if spec.rest_path:
            response = openapi["paths"][spec.rest_path]["post"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"]
            roots.append((openapi, response))
        for root, node in roots:
            for path, obj in projectable_objects(root, node):
                assert not obj.get("required"), (
                    spec.name,
                    ".".join(path),
                    obj["required"],
                )


@pytest.mark.parametrize("name", list(PAYLOADS))
def test_each_coverage_and_layer_field_projects_on_native_mcp_rest_and_cli(
    name: str,
    rest: TestClient,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec_key = (
        "fengshui_xuankong_house_chart"
        if name == "xuankong_natal"
        else f"fengshui_{name}"
    )
    spec = SPECS[spec_key]
    inputs = payload(name)
    # Assess exposes several independent rule layers, including the natal one.
    if name == "assess":
        natal = payload("xuankong_natal")
        inputs["house"] = natal.pop("house")
        inputs["xuankong"] = natal
        inputs["methods"] = ["bazhai", "jinsuo", "annual_stars", "xuankong_natal"]
    full = rest.post(
        spec.rest_path, json=inputs, params={"as_of": AS_OF, "include": "*"}
    )
    assert full.status_code == 200, full.text
    cases = []
    body = full.json()
    for layer, data in body["layers"].items():
        if isinstance(data, dict) and "status" in data:
            cases.append(
                (
                    f"layers.{layer}.status",
                    {"layers": {layer: {"status": data["status"]}}},
                )
            )
    cases.append(
        (
            "coverage.implemented_layers",
            {
                "coverage": {
                    "implemented_layers": body["coverage"]["implemented_layers"]
                }
            },
        )
    )

    async def native_calls() -> tuple[dict, list[CallToolResult]]:
        async with Client(mcp.app) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert all(tool.output_schema is None for tool in tools.values())
            schema = spec.output_model.model_json_schema()
            results = []
            for field, _ in cases:
                results.append(
                    await call_calculation(
                        client,
                        spec.name,
                        {
                            **inputs,
                            "as_of": AS_OF,
                            "fields": [field],
                        },
                        raise_on_error=False,
                    )
                )
            return schema, results

    native_schema, native_results = asyncio.run(native_calls())
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(inputs))
    for (field, expected), protocol in zip(cases, native_results):
        http = rest.post(
            spec.rest_path,
            json=inputs,
            params={
                "as_of": AS_OF,
                "fields": field,
            },
        )
        code = run(
            [
                spec.name,
                "--request-file",
                str(request_file),
                "--as-of",
                AS_OF,
                "--fields",
                field,
            ]
        )
        cli = json.loads(capsys.readouterr().out)
        assert http.status_code == 200 and not protocol.is_error and code == 0
        for result in (http.json(), protocol.structured_content, cli):
            assert {k: v for k, v in result.items() if k != "run_metadata"} == expected
            spec.output_model.model_validate(result)
            Draft202012Validator(native_schema).validate(result)
            assert result["run_metadata"]["tool_name"] == spec.name


@pytest.mark.parametrize(
    "value", [{"implemented_layers": "bazhai"}, {"missing_inputs": [123]}]
)
def test_partial_coverage_still_rejects_wrong_present_types(value: JsonValue) -> None:
    with pytest.raises(ValidationError):
        Coverage.model_validate(value)
    with pytest.raises(SchemaError):
        Draft202012Validator(Coverage.model_json_schema()).validate(value)


@pytest.mark.parametrize(
    "field,issue",
    [
        ("coverage.implemented_layers.0", "non_object_projection_path"),
        ("layers.directions.statuz", "unknown_projection_path"),
    ],
)
def test_fengshui_invalid_paths_keep_same_diagnostics_on_all_surfaces(
    field: str,
    issue: str,
    rest: TestClient,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = payload("directions")
    http = rest.post(
        "/api/fengshui/directions",
        json=inputs,
        params={"fields": field, "as_of": AS_OF},
    )

    async def native_call() -> CallToolResult:
        async with Client(mcp.app) as client:
            return await call_calculation(
                client,
                "fengshui_directions",
                {**inputs, "fields": [field], "as_of": AS_OF},
                raise_on_error=False,
            )

    protocol = asyncio.run(native_call())
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(inputs))
    code = run(
        [
            "fengshui_directions",
            "--request-file",
            str(request_file),
            "--fields",
            field,
            "--as-of",
            AS_OF,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 422 and protocol.is_error and code == 1
    for result in (http.json(), protocol.structured_content, cli):
        assert len(result["issues"]) == 1
        recorded = result["issues"][0]
        assert recorded["path"] == field
        assert recorded["code"] == issue
        if issue == "unknown_projection_path":
            assert "status" in recorded["constraints"]["available"]


def test_project_fields_whole_parent_overrides_dotted_regardless_of_order() -> None:
    from fatebridge.application.projection import project_fields

    payload = {
        "bazi_birth": {
            "day_master": {"stem": "壬", "strength": "弱"},
            "favorable_elements": ["金", "水"],
        },
        "summary": "summary-text",
        "run_metadata": {"run_id": "r"},
    }
    first = project_fields(payload, ["bazi_birth", "bazi_birth.day_master"])
    second = project_fields(payload, ["bazi_birth.day_master", "bazi_birth"])
    assert first["bazi_birth"] == payload["bazi_birth"]
    assert second["bazi_birth"] == payload["bazi_birth"]


def test_mcp_arguments_are_separate_from_delivery_controls() -> None:
    from fastmcp import FastMCP
    from pydantic import BaseModel

    from fatebridge.application.bindings import bind_kwargs
    from fatebridge.application.tool_spec import ToolSpec
    from fatebridge.mcp_server import _register_mcp_tools

    class Request(BaseModel):
        fields: list[str]

    spec = ToolSpec(
        name="field_calculation",
        bind=bind_kwargs(lambda fields: {"selection": fields, "other": 2}),
        request_model=Request,
        summary="",
        operation_label_zh="",
        family="",
    )
    server = FastMCP("test")
    _register_mcp_tools(server, [spec])

    async def call() -> CallToolResult:
        async with Client(server) as client:
            return await client.call_tool(
                "run_calculation",
                {
                    "tool": spec.name,
                    "arguments": {"fields": ["domain"]},
                    "fields": ["selection"],
                },
                raise_on_error=False,
            )

    result = asyncio.run(call())
    assert not result.is_error
    assert result.structured_content["selection"] == ["domain"]
    assert "other" not in result.structured_content
