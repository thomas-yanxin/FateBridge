"""Agent-friendliness contracts: stranger-agent MCP loop, 3-surface default delivery parity, and catalog hygiene."""

from __future__ import annotations

import ast
import asyncio
import importlib
import json
import shlex
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import validate

import fatebridge.api as api
from fatebridge import cli
from fatebridge.application.description import describe_spec, summarize_spec
from fatebridge.application.discovery import discover_specs
from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from tests.support.transports import cached_mcp_app

FORBIDDEN_SURFACE_KEYS = {
    "selected_sections",
    "snapshot_text",
    "snapshot_export",
    "result_delivery",
    "projection_warnings",
}


def _business(payload: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in payload.items() if k != "run_metadata"}


@pytest.mark.asyncio
async def test_stranger_agent_mcp_loop_and_error_recovery() -> None:
    """An agent starting cold can discover, search, call with default delivery, and recover from typos."""
    async with Client(cached_mcp_app()) as client:
        # 1. Surface exposes discover_tools + run_calculation + run_batch and 0 resources.
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {
            "discover_tools",
            "run_calculation",
            "run_batch",
        }
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        assert resources == []
        assert templates == []

        # 2. Step 1: discover_tools() returns family counts and summary tool records.
        overview = await client.call_tool("discover_tools", {})
        assert not overview.is_error
        body = overview.structured_content
        assert body["detail"] == "summary"
        assert sum(body["families"].values()) == len(CATALOG)
        assert len(body["families"]) == 12
        assert body["matched_count"] == len(CATALOG)
        sample_summary = body["tools"][0]
        assert "input_schema" not in sample_summary
        assert {"tool", "family", "summary"} <= set(sample_summary)

        # 3. Step 2: q= search narrows to relevant tools.
        searched = await client.call_tool("discover_tools", {"q": "法达"})
        assert not searched.is_error
        assert "firdaria" in {
            item["tool"] for item in searched.structured_content["tools"]
        }

        # 4. Step 3: discover_tools(tool=...) pulls the unwrapped single-tool contract.
        contract_res = await client.call_tool("discover_tools", {"tool": "firdaria"})
        assert not contract_res.is_error
        contract = contract_res.structured_content
        assert contract["tool"] == "firdaria"
        example = contract["example_input"]
        validate(example, contract["input_schema"])

        # 5. Step 4: run_calculation uses default delivery and succeeds inline.
        calc_res = await client.call_tool(
            "run_calculation",
            {
                "tool": "firdaria",
                "arguments": example,
                "as_of": "2026-10-12T12:00:00+08:00",
            },
        )
        assert not calc_res.is_error
        payload = calc_res.structured_content
        assert payload["run_metadata"]["tool_name"] == "firdaria"
        for forbidden in FORBIDDEN_SURFACE_KEYS:
            assert forbidden not in payload

        # 6. Error recovery on misspelled tool -> constraints.suggestions.
        bad_tool = await client.call_tool(
            "run_calculation",
            {"tool": "firdari", "arguments": example},
            raise_on_error=False,
        )
        assert bad_tool.is_error
        assert bad_tool.structured_content["error_code"] == "unknown_tool"
        assert (
            "firdaria"
            in bad_tool.structured_content["issues"][0]["constraints"]["suggestions"]
        )

        # 7. Error recovery on misspelled fields -> constraints.available.
        bad_fields = await client.call_tool(
            "run_calculation",
            {
                "tool": "firdaria",
                "arguments": example,
                "fields": ["nonexistent_field_xyz"],
            },
            raise_on_error=False,
        )
        assert bad_fields.is_error
        assert bad_fields.structured_content["error_code"] == "validation_error"
        issue = bad_fields.structured_content["issues"][0]
        assert issue["code"] == "unknown_projection_path"
        assert "firdaria" in issue["constraints"]["available"]


@pytest.mark.parametrize(
    "tool_name", ["firdaria", "bazi_birth_chart", "fengshui_directions"]
)
def test_three_surface_parity_on_default_delivery(
    tool_name: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Default delivery produces identical business payload across REST, MCP, CLI."""
    spec = next(s for s in CATALOG if s.name == tool_name)
    example = example_input(spec)
    assert example is not None
    as_of = "2026-10-12T12:00:00+08:00"

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest_res = TestClient(api.app).post(
        spec.rest_path, json=example, params={"as_of": as_of}
    )
    assert rest_res.status_code == 200, rest_res.text

    async def mcp_call():
        async with Client(cached_mcp_app()) as client:
            return await client.call_tool(
                "run_calculation",
                {"tool": spec.name, "arguments": example, "as_of": as_of},
            )

    mcp_res = asyncio.run(mcp_call())
    assert not mcp_res.is_error

    cmd = [*shlex.split(cli._cli_example(spec, example))[1:], "--as-of", as_of]
    capsys.readouterr()
    code = cli.run(cmd)
    cli_body = json.loads(capsys.readouterr().out)
    assert code == 0

    assert (
        _business(rest_res.json())
        == _business(mcp_res.structured_content)
        == _business(cli_body)
    )


FORBIDDEN_LEGACY_PARAMS = frozenset(
    {"gps_lat", "gps_lon", "lat", "lon", "zone", "hsys", "zodiacal"}
)
ALLOWED_SURFACES_KEYS = frozenset({"cli", "rest", "mcp"})


def _resolve_schema_property(schema: dict[str, object], name: str) -> dict[str, object]:
    prop = schema["properties"][name]
    if "$ref" in prop:
        ref_name = prop["$ref"].rsplit("/", 1)[-1]
        return schema["$defs"][ref_name]
    for branch in prop.get("anyOf", []):
        if isinstance(branch, dict) and "$ref" in branch:
            ref_name = branch["$ref"].rsplit("/", 1)[-1]
            return schema["$defs"][ref_name]
    return prop


def test_catalog_hygiene_across_all_tools() -> None:
    """Single canonical identity, valid examples, lean labels, and no cross-technique leakage."""
    assert len(CATALOG) == 91
    assert len({spec.family for spec in CATALOG}) == 12
    assert set(ExecutionOptions.model_fields) == {"as_of"}

    for removed in ("key", "mcp_name", "tool_name"):
        assert not hasattr(ToolSpec, removed)
        assert removed not in ToolSpec.__dataclass_fields__

    names: set[str] = set()
    specs = {spec.name: spec for spec in CATALOG}
    assert "gua_meanings" not in specs
    assert "gua_lookup" in specs

    for spec in CATALOG:
        assert spec.name not in names
        names.add(spec.name)
        assert len(spec.operation_label_zh) <= 24, (spec.name, spec.operation_label_zh)

        ex = example_input(spec)
        assert ex is not None, f"{spec.name} missing example_input"
        spec.request_model.model_validate(ex)

        model_fields = set(spec.request_model.model_fields)
        assert FORBIDDEN_LEGACY_PARAMS.isdisjoint(model_fields), (
            spec.name,
            model_fields & FORBIDDEN_LEGACY_PARAMS,
        )

        req_props = set(spec.request_model.model_json_schema().get("properties", {}))
        out_fields = set(spec.output_model.model_fields)
        desc = describe_spec(spec)
        summary_desc = summarize_spec(spec)
        assert set(desc["surfaces"]) == ALLOWED_SURFACES_KEYS, (
            spec.name,
            desc["surfaces"],
        )
        assert set(summary_desc["surfaces"]) == ALLOWED_SURFACES_KEYS, (
            spec.name,
            summary_desc["surfaces"],
        )
        assert FORBIDDEN_SURFACE_KEYS.isdisjoint(req_props), (spec.name, req_props)
        assert FORBIDDEN_SURFACE_KEYS.isdisjoint(out_fields), (spec.name, out_fields)
        assert FORBIDDEN_SURFACE_KEYS.isdisjoint(set(desc)), spec.name

    # No cross-technique parameter leakage on split models.
    solar_props = set(specs["solar_return"].request_model.model_fields)
    assert not any(f.startswith(("firdaria_", "pd_")) for f in solar_props), solar_props

    natal_props = set(specs["astrology_chart"].request_model.model_fields)
    assert "saptavargaja_profile" not in natal_props
    assert not any(f.startswith("guolao_") for f in natal_props), natal_props

    # Nested option schemas expose concrete typed properties rather than free-form dicts.
    qimen_schema = specs["qimen"].request_model.model_json_schema()
    assert _resolve_schema_property(qimen_schema, "qimen_options").get("properties")
    sanshi_schema = specs["sanshi_combined_chart"].request_model.model_json_schema()
    for field_name in ("qimen_options", "taiyi_options"):
        assert _resolve_schema_property(sanshi_schema, field_name).get("properties")

    # Confirm default MCP app exposes 3 meta tools and 0 resources.
    app_mcp = create_mcp_app()
    assert app_mcp is not None


def test_discovery_summary_budget_and_full_detail_filter_guard() -> None:
    """Default discovery stays <= 32 KiB and unfiltered detail=full is rejected."""
    summary_payload = discover_specs(CATALOG, detail="summary")
    summary_bytes = len(json.dumps(summary_payload, ensure_ascii=False).encode("utf-8"))
    assert summary_bytes <= 32768, f"summary discovery exceeded 32 KiB: {summary_bytes}"

    with pytest.raises(ParameterError) as exc_info:
        discover_specs(CATALOG, detail="full")
    assert exc_info.value.issues[0]["code"] == "filter_required_for_full_detail"


def test_every_tool_delivers_default_within_budget() -> None:
    """Every tool delivers a compact isomorphic default payload <= 10 KiB."""
    options = ExecutionOptions(as_of="2026-10-12T12:00:00+08:00")
    for spec in CATALOG:
        request = spec.request_model.model_validate(example_input(spec))
        raw = execute_with_receipt(spec, request, options=options)
        delivered = deliver_response(raw, spec=spec)
        size = len(json.dumps(delivered, ensure_ascii=False).encode("utf-8"))
        assert size <= 10240, f"{spec.name} default output too large: {size} bytes"


def test_package_imports_are_absolute_and_export_presets_is_deleted() -> None:
    """src/fatebridge uses absolute imports only and fatebridge.core.export_presets stays deleted."""
    src_root = Path(__file__).resolve().parents[2] / "src" / "fatebridge"
    relative_imports: list[tuple[str, int]] = []
    for path in sorted(src_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                relative_imports.append((str(path.relative_to(src_root)), node.level))
    assert not relative_imports, relative_imports

    with pytest.raises(ImportError):
        importlib.import_module("fatebridge.core.export_presets")
