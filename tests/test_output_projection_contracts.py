"""Every object reachable by field projection must accept missing siblings."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import ValidationError

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.fengshui.output import Ruleset
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import PAYLOADS, payload

SPECS = {spec.key: spec for spec in CATALOG}
SNAPSHOTS = Path(__file__).parent / "golden" / "snapshots"
AS_OF = "2026-10-12T02:00:00Z"


def projectable_objects(root, node, path=(), refs=frozenset()):
    """Follow references/unions/map values, but never traverse array items.

    run_metadata is preserved whole by the projector, even when a child is
    requested. Required receipt facts therefore cannot cause this defect.
    """
    if path[:1] == ("run_metadata",):
        return
    if "$ref" in node:
        ref = node["$ref"]
        if ref in refs:
            return
        target = root
        assert ref.startswith("#/")
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        yield from projectable_objects(root, target, path, refs | {ref})
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


@pytest.mark.parametrize("key", list(SPECS))
def test_no_projectable_business_object_requires_sibling_fields(key):
    schema = SPECS[key].output_model.model_json_schema()
    for path, node in projectable_objects(schema, schema):
        assert not node.get("required"), (key, ".".join(path), node["required"])


def leaves(value, path=()):
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
def test_every_golden_leaf_projection_validates_without_rewriting_snapshots(key):
    spec = SPECS[key]
    slug = (
        spec.rest_path.strip("/").replace("/", "_") if spec.rest_path else "mcp_" + key
    )
    if key == "astro_relative_chart":
        slug = "api_astro_relative"
    original = (SNAPSHOTS / (slug + ".json")).read_text()
    # Golden canonicalization deliberately omits volatile receipt fields such
    # as run_id and generated_at. Those are not complete live RunMetadata.
    result = {k: v for k, v in json.loads(original).items() if k != "run_metadata"}
    validator = Draft202012Validator(spec.output_model.model_json_schema())
    for field, expected in leaves(result):
        projected = project_fields(result, [field], strict_fields=True)
        spec.output_model.model_validate(projected)
        validator.validate(projected)
        value = projected
        for part in field.split("."):
            value = value[part]
        assert value == expected
    assert result == {
        k: v for k, v in json.loads(original).items() if k != "run_metadata"
    }


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


def test_all_published_schemas_preserve_object_projection_compatibility(rest, capsys):
    manifest = {
        tool["tool"]: tool["output_schema"]
        for tool in rest.get("/api/tools").json()["tools"]
    }
    openapi = rest.get("/openapi.json").json()

    async def native_schemas():
        async with Client(mcp.app) as client:
            return {
                tool.name: tool.model_dump(by_alias=True)["outputSchema"]
                for tool in await client.list_tools()
            }

    published = asyncio.run(native_schemas())
    assert set(published) == {spec.tool_name for spec in CATALOG if spec.mcp_name}
    for spec in CATALOG:
        central = spec.output_model.model_json_schema()
        assert run(["describe", spec.tool_name]) == 0
        cli = json.loads(capsys.readouterr().out)["output_schema"]
        assert central == cli == manifest[spec.tool_name]
        roots = [(central, central)]
        if spec.mcp_name:
            roots.append((published[spec.tool_name], published[spec.tool_name]))
        if spec.rest_path:
            response = openapi["paths"][spec.rest_path]["post"]["responses"]["200"][
                "content"
            ]["application/json"]["schema"]
            roots.append((openapi, response))
        for root, node in roots:
            for path, obj in projectable_objects(root, node):
                assert not obj.get("required"), (
                    spec.tool_name,
                    ".".join(path),
                    obj["required"],
                )


@pytest.mark.parametrize("name", list(PAYLOADS))
@pytest.mark.parametrize("no_metadata", [False, True])
def test_each_ruleset_field_projects_on_native_mcp_rest_and_cli(
    name, no_metadata, rest, tmp_path, capsys
):
    spec = SPECS["fengshui_" + name]
    inputs = payload(name)
    # Assess exposes several independent rule layers, including the natal one.
    if name == "assess":
        natal = payload("xuankong_natal")
        inputs["house"] = natal.pop("house")
        inputs["xuankong"] = natal
        inputs["methods"] = ["bazhai", "jinsuo", "annual_stars", "xuankong_natal"]
    full = rest.post(spec.rest_path, json=inputs, params={"as_of": AS_OF})
    assert full.status_code == 200, full.text
    cases = []
    for layer, data in full.json()["layers"].items():
        for field in Ruleset.model_fields:
            value = data["ruleset"][field]
            cases.append(
                (
                    "layers." + layer + ".ruleset." + field,
                    {"layers": {layer: {"ruleset": {field: value}}}},
                )
            )

    async def native_calls():
        async with Client(mcp.app) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            schema = tools[spec.tool_name].model_dump(by_alias=True)["outputSchema"]
            results = []
            for field, _ in cases:
                # Leave native client schema validation enabled. A renderer-only
                # test would miss RuntimeError on a successful partial result.
                results.append(
                    await client.call_tool(
                        spec.tool_name,
                        {
                            **inputs,
                            "as_of": AS_OF,
                            "fields": [field],
                            "strict_fields": True,
                            "include_snapshot_text": False,
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
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
        code = run(
            [
                *(["--no-metadata"] if no_metadata else []),
                spec.tool_name,
                "--request-file",
                str(request_file),
                "--as-of",
                AS_OF,
                "--fields",
                field,
                "--strict-fields",
                "--no-include-snapshot-text",
            ]
        )
        cli = json.loads(capsys.readouterr().out)
        assert http.status_code == 200 and not protocol.is_error and code == 0
        assert json.loads(protocol.content[0].text) == protocol.structured_content
        for result in (http.json(), protocol.structured_content, cli):
            assert {k: v for k, v in result.items() if k != "run_metadata"} == expected
            spec.output_model.model_validate(result)
            Draft202012Validator(native_schema).validate(result)
        if no_metadata:
            assert "run_metadata" not in cli
        else:
            for result in (http.json(), protocol.structured_content, cli):
                assert result["run_metadata"]["tool_name"] == spec.tool_name


@pytest.mark.parametrize(
    "value", [{"version": 1}, {"source_ids": "S1"}, {"sources": [{"title": 1}]}]
)
def test_partial_ruleset_still_rejects_wrong_present_types(value):
    with pytest.raises(ValidationError):
        Ruleset.model_validate(value)
    with pytest.raises(SchemaError):
        Draft202012Validator(Ruleset.model_json_schema()).validate(value)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "field,issue",
    [
        ("layers.directions.ruleset.sources.0.title", "non_object_projection_path"),
        ("layers.directions.ruleset.versoin", "unknown_projection_path"),
    ],
)
def test_ruleset_invalid_paths_keep_same_diagnostics_on_all_surfaces(
    strict, field, issue, rest, tmp_path, capsys
):
    inputs = payload("directions")
    http = rest.post(
        "/api/fengshui/directions",
        json=inputs,
        params={"fields": field, "strict_fields": strict, "as_of": AS_OF},
    )

    async def native_call():
        async with Client(mcp.app) as client:
            return await client.call_tool(
                "fengshui_directions",
                {**inputs, "fields": [field], "strict_fields": strict, "as_of": AS_OF},
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
            "--strict-fields",
            str(strict).lower(),
            "--as-of",
            AS_OF,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == (422 if strict else 200)
    assert protocol.is_error == strict and code == (1 if strict else 0)
    diagnostic = "issues" if strict else "projection_warnings"
    for result in (http.json(), protocol.structured_content, cli):
        assert result[diagnostic] == [{"path": field, "code": issue}]
    assert json.loads(protocol.content[0].text) == protocol.structured_content
