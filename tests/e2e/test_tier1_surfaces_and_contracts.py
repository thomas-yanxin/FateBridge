"""Tier 1 opaque-box E2E tests for Plan A R1 (surfaces & metadata) and R5 (contracts)."""

from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import sys
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e._surfaces import (
    REPO_ROOT,
    assert_isomorphic_subset,
    augmented_inputs_for,
    call_cli,
    call_cli_tool,
    call_mcp_tool,
    call_python_run,
    call_rest_get,
    call_rest_post,
    extract_error_issues,
    find_bloat_keys,
    has_dotted_path,
    rest_path_for,
    strip_run_metadata,
)

LEGACY_DETAIL_VALUES: tuple[str, ...] = ("compact", "audit")
DISCOVERY_DETAILS: tuple[Literal["brief", "summary", "full"], ...] = (
    "brief",
    "summary",
    "full",
)
BLOAT_PROSE_PATTERN = re.compile(
    r"\b(?:rule_trace|source_citations|source_catalog|conventions)\b"
)


# ---------------------------------------------------------------------------
# R1: Calculation `detail` removal & discovery `detail` preservation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_value", LEGACY_DETAIL_VALUES)
async def test_mcp_run_calculation_rejects_detail(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    detail_value: str,
) -> None:
    payload = augmented_inputs_for("gua_lookup", all_tool_specs)
    outcome = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": "gua_lookup",
            "arguments": payload,
            "as_of": e2e_as_of,
            "detail": detail_value,
        },
    )
    assert not outcome.ok
    assert outcome.status_code == 422
    assert outcome.payload.get("error_code") == "validation_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_value", LEGACY_DETAIL_VALUES)
async def test_mcp_run_batch_rejects_detail(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    detail_value: str,
) -> None:
    payload = augmented_inputs_for("gua_lookup", all_tool_specs)
    top_level_outcome = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [{"id": "c1", "tool": "gua_lookup", "arguments": payload}],
            "as_of": e2e_as_of,
            "detail": detail_value,
        },
    )
    assert not top_level_outcome.ok
    assert top_level_outcome.status_code == 422
    assert top_level_outcome.payload.get("error_code") == "validation_error"

    per_call_outcome = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": "gua_lookup",
                    "arguments": payload,
                    "detail": detail_value,
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert not per_call_outcome.ok
    assert per_call_outcome.status_code == 422
    assert per_call_outcome.payload.get("error_code") == "validation_error"


@pytest.mark.parametrize("detail_value", LEGACY_DETAIL_VALUES)
def test_rest_calculation_and_batch_reject_detail(
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    detail_value: str,
) -> None:
    payload = augmented_inputs_for("gua_lookup", all_tool_specs)
    path = rest_path_for("gua_lookup", all_tool_specs)

    calc_outcome = call_rest_post(
        rest_client,
        path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("detail", detail_value)],
    )
    assert not calc_outcome.ok
    assert calc_outcome.status_code == 422
    assert calc_outcome.payload.get("error_code") == "validation_error"

    batch_top = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [{"id": "c1", "tool": "gua_lookup", "arguments": payload}],
            "as_of": e2e_as_of,
            "detail": detail_value,
        },
    )
    assert not batch_top.ok
    assert batch_top.status_code == 422
    assert batch_top.payload.get("error_code") == "validation_error"
    assert any(
        issue.get("code") == "extra_forbidden"
        for issue in extract_error_issues(batch_top.payload)
    )

    batch_call = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [
                {
                    "id": "c1",
                    "tool": "gua_lookup",
                    "arguments": payload,
                    "detail": detail_value,
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert not batch_call.ok
    assert batch_call.status_code == 422
    assert batch_call.payload.get("error_code") == "validation_error"
    assert any(
        issue.get("code") == "extra_forbidden"
        for issue in extract_error_issues(batch_call.payload)
    )


@pytest.mark.parametrize("detail_value", LEGACY_DETAIL_VALUES)
def test_cli_tool_rejects_detail_flag(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    detail_value: str,
) -> None:
    payload = augmented_inputs_for("gua_lookup", all_tool_specs)
    outcome = call_cli_tool(
        "gua_lookup",
        payload,
        as_of=e2e_as_of,
        extra_flags=["--detail", detail_value],
    )
    assert not outcome.ok
    assert outcome.exit_code == 2
    assert outcome.payload.get("error_code") == "usage_error"


@pytest.mark.parametrize("detail_value", LEGACY_DETAIL_VALUES)
def test_python_run_rejects_detail(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    detail_value: str,
) -> None:
    import fatebridge

    sig = inspect.signature(fatebridge.run)
    assert "detail" not in sig.parameters
    assert "include" in sig.parameters
    assert "fields" in sig.parameters

    payload = augmented_inputs_for("gua_lookup", all_tool_specs)
    try:
        outcome = call_python_run(
            "gua_lookup",
            payload,
            as_of=e2e_as_of,
            detail=detail_value,
        )
    except (TypeError, ValueError) as exc:
        msg = str(exc).lower()
        assert (
            "detail" in msg or "extra_forbidden" in msg or "unexpected keyword" in msg
        ), f"Unexpected {type(exc).__name__} when passing detail={detail_value!r}: {exc}"
        return
    assert not outcome.ok
    assert outcome.payload.get("error_code") == "validation_error"
    assert any(
        issue.get("code") == "extra_forbidden" and issue.get("path") == "detail"
        for issue in extract_error_issues(outcome.payload)
    ), f"Expected extra_forbidden issue for 'detail', got: {outcome.payload}"


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_level", DISCOVERY_DETAILS)
async def test_discovery_preserves_detail_across_all_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    detail_level: Literal["brief", "summary", "full"],
) -> None:
    import fatebridge

    py_manifest = fatebridge.discover(tool="bazi_overview", detail=detail_level)
    assert py_manifest["tool"] == "bazi_overview"
    assert py_manifest["detail"] == detail_level

    mcp_outcome = await call_mcp_tool(
        mcp_client,
        "discover_tools",
        {"tool": "bazi_overview", "detail": detail_level},
    )
    assert mcp_outcome.ok
    assert mcp_outcome.payload["tool"] == "bazi_overview"
    assert mcp_outcome.payload["detail"] == detail_level

    rest_outcome = call_rest_get(
        rest_client,
        "/api/tools",
        params={"tool": "bazi_overview", "detail": detail_level},
    )
    assert rest_outcome.ok
    assert rest_outcome.payload["tool"] == "bazi_overview"
    assert rest_outcome.payload["detail"] == detail_level

    cli_outcome = call_cli(
        ["discover", "bazi_overview", "--detail", detail_level],
    )
    assert cli_outcome.ok
    assert cli_outcome.payload["tool"] == "bazi_overview"
    assert cli_outcome.payload["detail"] == detail_level


@pytest.mark.asyncio
async def test_mcp_and_rest_schemas_remove_detail_and_expose_include_fields(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    mcp_tools = {tool.name: tool for tool in await mcp_client.list_tools()}
    assert set(mcp_tools) == {"discover_tools", "run_calculation", "run_batch"}

    calc_props = mcp_tools["run_calculation"].input_schema.get("properties", {})
    assert "detail" not in calc_props
    assert "include" in calc_props
    assert "fields" in calc_props

    batch_schema = mcp_tools["run_batch"].input_schema
    batch_props = batch_schema.get("properties", {})
    assert "detail" not in batch_props
    assert "include" not in batch_props
    assert "fields" not in batch_props
    assert "calls" in batch_props
    batch_call_def = batch_schema.get("$defs", {}).get("BatchCall", {})
    batch_call_props = batch_call_def.get("properties", {})
    assert "detail" not in batch_call_props
    assert "include" in batch_call_props
    assert "fields" in batch_call_props

    discover_props = mcp_tools["discover_tools"].input_schema.get("properties", {})
    assert "detail" in discover_props

    openapi_outcome = call_rest_get(rest_client, "/openapi.json")
    assert openapi_outcome.ok
    openapi = openapi_outcome.payload

    bazi_path = rest_path_for("bazi_overview", all_tool_specs)
    post_op = openapi["paths"][bazi_path]["post"]
    query_param_names = {
        param["name"]
        for param in post_op.get("parameters", [])
        if param.get("in") == "query"
    }
    assert "detail" not in query_param_names
    assert {"include", "fields", "as_of"}.issubset(query_param_names)

    tools_get_op = openapi["paths"]["/api/tools"]["get"]
    tools_query_names = {
        param["name"]
        for param in tools_get_op.get("parameters", [])
        if param.get("in") == "query"
    }
    assert "detail" in tools_query_names

    components_schemas = openapi.get("components", {}).get("schemas", {})
    batch_req_props = components_schemas.get("BatchRequest", {}).get("properties", {})
    assert "detail" not in batch_req_props
    assert "include" not in batch_req_props
    assert "fields" not in batch_req_props
    assert "calls" in batch_req_props
    batch_call_rest_props = components_schemas.get("BatchCall", {}).get(
        "properties", {}
    )
    assert "detail" not in batch_call_rest_props
    assert "include" in batch_call_rest_props
    assert "fields" in batch_call_rest_props


# ---------------------------------------------------------------------------
# R1: `include` and `fields` across all 5 calculation surfaces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_include_star_returns_lossless_output_on_all_5_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    py_default = call_python_run(tool_name, payload, as_of=e2e_as_of)
    py_full = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    mcp_full = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["*"],
        },
    )
    rest_full = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("include", "*")],
    )
    cli_full = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["*"],
    )
    batch_full = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": ["*"],
                }
            ],
            "as_of": e2e_as_of,
        },
    )

    for outcome in (py_default, py_full, mcp_full, rest_full, cli_full, batch_full):
        assert outcome.ok, outcome.payload

    batch_item = batch_full.payload["results"][0]
    assert batch_item["ok"] is True
    batch_result = batch_item["result"]

    canonical_business = strip_run_metadata(py_full.payload)
    for surface_payload in (
        mcp_full.payload,
        rest_full.payload,
        cli_full.payload,
        batch_result,
    ):
        assert strip_run_metadata(surface_payload) == canonical_business
        assert not surface_payload["run_metadata"].get("omitted_fields")

    assert not py_full.payload["run_metadata"].get("omitted_fields")
    assert_isomorphic_subset(py_default.payload, py_full.payload)


@pytest.mark.asyncio
async def test_include_evidence_view_expands_omitted_fields_on_all_5_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    views = all_tool_specs[tool_name].get("evidence_views", {})
    assert "calendar_basis" in views
    view_fields = views["calendar_basis"]["fields"]
    assert view_fields

    default_res = call_python_run(tool_name, payload, as_of=e2e_as_of)
    assert default_res.ok
    default_omitted = default_res.payload["run_metadata"].get("omitted_fields") or []
    assert default_omitted

    py_view = call_python_run(
        tool_name, payload, as_of=e2e_as_of, include=["calendar_basis"]
    )
    mcp_view = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["calendar_basis"],
        },
    )
    rest_view = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("include", "calendar_basis")],
    )
    cli_view = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["calendar_basis"],
    )
    batch_view = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": ["calendar_basis"],
                }
            ],
            "as_of": e2e_as_of,
        },
    )

    for outcome in (py_view, mcp_view, rest_view, cli_view, batch_view):
        assert outcome.ok, outcome.payload

    batch_result = batch_view.payload["results"][0]["result"]
    expected_business = strip_run_metadata(py_view.payload)

    for surface_payload in (
        py_view.payload,
        mcp_view.payload,
        rest_view.payload,
        cli_view.payload,
        batch_result,
    ):
        assert strip_run_metadata(surface_payload) == expected_business
        for field_path in view_fields:
            assert has_dotted_path(
                surface_payload, field_path
            ), f"Expected {field_path!r} from view 'calendar_basis' to be present"
            remaining_omitted = surface_payload["run_metadata"].get("omitted_fields")
            assert not remaining_omitted or field_path not in remaining_omitted


@pytest.mark.asyncio
async def test_include_dotted_path_unomits_specific_paths_on_all_5_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    default_res = call_python_run(tool_name, payload, as_of=e2e_as_of)
    assert default_res.ok
    omitted_list = default_res.payload["run_metadata"].get("omitted_fields") or []
    assert omitted_list, "Expected bazi_overview default response to omit heavy blocks"
    target_path = omitted_list[0]
    assert not has_dotted_path(default_res.payload, target_path)

    py_inc = call_python_run(tool_name, payload, as_of=e2e_as_of, include=[target_path])
    mcp_inc = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": [target_path],
        },
    )
    rest_inc = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("include", target_path)],
    )
    cli_inc = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=[target_path],
    )
    batch_inc = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": [target_path],
                }
            ],
            "as_of": e2e_as_of,
        },
    )

    for outcome in (py_inc, mcp_inc, rest_inc, cli_inc, batch_inc):
        assert outcome.ok, outcome.payload

    batch_result = batch_inc.payload["results"][0]["result"]
    expected_business = strip_run_metadata(py_inc.payload)
    for surface_payload in (
        py_inc.payload,
        mcp_inc.payload,
        rest_inc.payload,
        cli_inc.payload,
        batch_result,
    ):
        assert strip_run_metadata(surface_payload) == expected_business
        assert has_dotted_path(surface_payload, target_path)
        remaining = surface_payload["run_metadata"].get("omitted_fields") or []
        assert target_path not in remaining


@pytest.mark.asyncio
async def test_fields_projection_preserves_run_metadata_on_all_5_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    selected_fields = list(
        all_tool_specs[tool_name]["evidence_views"]["root_effects"]["fields"]
    )
    assert selected_fields

    py_proj = call_python_run(
        tool_name, payload, as_of=e2e_as_of, fields=selected_fields
    )
    mcp_proj = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "fields": selected_fields,
        },
    )
    rest_proj = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of)] + [("fields", f) for f in selected_fields],
    )
    cli_proj = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        fields=selected_fields,
    )
    batch_proj = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "fields": selected_fields,
                }
            ],
            "as_of": e2e_as_of,
        },
    )

    for outcome in (py_proj, mcp_proj, rest_proj, cli_proj, batch_proj):
        assert outcome.ok, outcome.payload

    batch_result = batch_proj.payload["results"][0]["result"]
    expected_business = strip_run_metadata(py_proj.payload)
    expected_top_keys = {field.split(".")[0] for field in selected_fields}

    for surface_payload in (
        py_proj.payload,
        mcp_proj.payload,
        rest_proj.payload,
        cli_proj.payload,
        batch_result,
    ):
        assert strip_run_metadata(surface_payload) == expected_business
        assert set(strip_run_metadata(surface_payload)) == expected_top_keys
        for field_path in selected_fields:
            assert has_dotted_path(surface_payload, field_path)
        assert isinstance(surface_payload.get("run_metadata"), dict)
        assert surface_payload["run_metadata"]["tool_name"] == tool_name


@pytest.mark.asyncio
async def test_include_evidence_view_works_for_vedic_and_ziwei_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    for tool_name, view_name in (
        ("vedic_chart", "strength"),
        ("ziwei_birth_chart", "palace_sihua"),
    ):
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        rest_path = rest_path_for(tool_name, all_tool_specs)
        views = all_tool_specs[tool_name]["evidence_views"]
        assert view_name in views
        view_fields = views[view_name]["fields"]

        mcp_res = await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {
                "tool": tool_name,
                "arguments": payload,
                "as_of": e2e_as_of,
                "include": [view_name],
            },
        )
        rest_res = call_rest_post(
            rest_client,
            rest_path,
            json_body=payload,
            params=[("as_of", e2e_as_of), ("include", view_name)],
        )
        cli_res = call_cli_tool(
            tool_name,
            payload,
            as_of=e2e_as_of,
            include=[view_name],
        )
        full_res = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])

        for outcome in (mcp_res, rest_res, cli_res, full_res):
            assert outcome.ok, outcome.payload

        assert strip_run_metadata(mcp_res.payload) == strip_run_metadata(
            rest_res.payload
        )
        assert strip_run_metadata(mcp_res.payload) == strip_run_metadata(
            cli_res.payload
        )
        assert_isomorphic_subset(mcp_res.payload, full_res.payload)
        for field_path in view_fields:
            assert has_dotted_path(mcp_res.payload, field_path)


@pytest.mark.asyncio
async def test_batch_supports_per_call_include_and_fields(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    payload = augmented_inputs_for("bazi_overview", all_tool_specs)
    selected_fields = ["four_pillars", "day_master.strength"]

    mixed_batch = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {"id": "default_call", "tool": "bazi_overview", "arguments": payload},
                {
                    "id": "full_call",
                    "tool": "bazi_overview",
                    "arguments": payload,
                    "include": ["*"],
                },
                {
                    "id": "proj_call",
                    "tool": "bazi_overview",
                    "arguments": payload,
                    "fields": selected_fields,
                },
            ],
            "as_of": e2e_as_of,
        },
    )
    assert mixed_batch.ok, mixed_batch.payload
    results = mixed_batch.payload["results"]
    assert len(results) == 3
    default_res, full_res, proj_res = (item["result"] for item in results)

    assert default_res["run_metadata"].get("omitted_fields")
    assert not full_res["run_metadata"].get("omitted_fields")
    assert not proj_res["run_metadata"].get("omitted_fields")
    assert_isomorphic_subset(default_res, full_res)
    assert_isomorphic_subset(proj_res, full_res)
    assert set(strip_run_metadata(proj_res)) == {"four_pillars", "day_master"}

    rest_per_call_batch = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [
                {
                    "id": "c1",
                    "tool": "bazi_overview",
                    "arguments": payload,
                    "include": ["*"],
                },
                {
                    "id": "c2",
                    "tool": "bazi_overview",
                    "arguments": payload,
                    "fields": selected_fields,
                },
            ],
            "as_of": e2e_as_of,
        },
    )
    assert rest_per_call_batch.ok, rest_per_call_batch.payload
    rest_full_res = rest_per_call_batch.payload["results"][0]["result"]
    rest_proj_res = rest_per_call_batch.payload["results"][1]["result"]
    assert strip_run_metadata(rest_full_res) == strip_run_metadata(full_res)
    assert not rest_full_res["run_metadata"].get("omitted_fields")
    assert strip_run_metadata(rest_proj_res) == strip_run_metadata(proj_res)
    assert not rest_proj_res["run_metadata"].get("omitted_fields")

    rest_top_include_rejected = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [{"id": "c1", "tool": "bazi_overview", "arguments": payload}],
            "include": ["*"],
            "as_of": e2e_as_of,
        },
    )
    assert not rest_top_include_rejected.ok
    assert rest_top_include_rejected.status_code == 422
    assert rest_top_include_rejected.payload.get("error_code") == "validation_error"
    assert any(
        issue.get("code") == "extra_forbidden"
        for issue in extract_error_issues(rest_top_include_rejected.payload)
    )

    mcp_top_include_rejected = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [{"id": "c1", "tool": "bazi_overview", "arguments": payload}],
            "include": ["*"],
            "as_of": e2e_as_of,
        },
    )
    assert not mcp_top_include_rejected.ok
    assert mcp_top_include_rejected.status_code == 422
    assert mcp_top_include_rejected.payload.get("error_code") == "validation_error"


def test_default_view_and_fields_preserve_strict_isomorphism(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    for tool_name, view_name in (
        ("bazi_birth_chart", "calendar_basis"),
        ("vedic_chart", "divisions"),
        ("ziwei_birth_chart", "named_patterns"),
    ):
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        default_res = call_python_run(tool_name, payload, as_of=e2e_as_of)
        view_res = call_python_run(
            tool_name, payload, as_of=e2e_as_of, include=[view_name]
        )
        full_res = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
        view_fields = all_tool_specs[tool_name]["evidence_views"][view_name]["fields"]
        proj_res = call_python_run(
            tool_name, payload, as_of=e2e_as_of, fields=view_fields
        )

        for outcome in (default_res, view_res, full_res, proj_res):
            assert outcome.ok, outcome.payload

        assert_isomorphic_subset(default_res.payload, view_res.payload)
        assert_isomorphic_subset(view_res.payload, full_res.payload)
        assert_isomorphic_subset(proj_res.payload, full_res.payload)


# ---------------------------------------------------------------------------
# R1: `RunMetadata.omitted_fields` & unified `replay_metadata`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_name", ("bazi_birth_chart", "bazi_overview", "vedic_chart")
)
def test_default_heavy_tool_populates_omitted_fields_and_actually_omits_them(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_res = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_res = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_res.ok and full_res.ok

    omitted = default_res.payload["run_metadata"].get("omitted_fields")
    assert isinstance(omitted, list) and len(omitted) > 0
    for omitted_path in omitted:
        assert isinstance(omitted_path, str) and omitted_path
        assert not has_dotted_path(
            default_res.payload, omitted_path
        ), f"{tool_name}: omitted path {omitted_path!r} still present in default output"
        assert has_dotted_path(
            full_res.payload, omitted_path
        ), f"{tool_name}: omitted path {omitted_path!r} missing from include=['*']"


def test_include_star_clears_omitted_fields_and_preserves_duration_and_replay(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    for tool_name in ("bazi_birth_chart", "vedic_chart"):
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        full_res = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
        assert full_res.ok
        meta = full_res.payload["run_metadata"]
        assert not meta.get("omitted_fields")
        assert isinstance(meta.get("duration_ms"), (int, float))
        assert meta["duration_ms"] >= 0
        replay = meta.get("replay")
        assert isinstance(replay, dict)
        assert replay.get("as_of") == e2e_as_of
        assert isinstance(replay.get("overrides"), dict)
        assert isinstance(replay.get("requires_original_input"), bool)


@pytest.mark.asyncio
async def test_default_call_always_emits_duration_ms_and_replay_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    outcomes = [
        call_python_run(tool_name, payload, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": tool_name, "arguments": payload, "as_of": e2e_as_of},
        ),
        call_rest_post(
            rest_client,
            rest_path,
            json_body=payload,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool(tool_name, payload, as_of=e2e_as_of),
    ]

    for outcome in outcomes:
        assert outcome.ok, outcome.payload
        meta = outcome.payload["run_metadata"]
        assert isinstance(meta.get("duration_ms"), (int, float))
        assert meta["duration_ms"] >= 0
        replay = meta.get("replay")
        assert isinstance(replay, dict)
        assert replay.get("as_of") == e2e_as_of
        assert isinstance(replay.get("overrides"), dict)
        assert isinstance(replay.get("requires_original_input"), bool)
        assert meta.get("effective_time", {}).get("as_of") == e2e_as_of


@pytest.mark.parametrize("tool_name", ("gua_lookup", "place_lookup"))
def test_small_tools_with_no_omissions_omit_omitted_fields(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_res = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_res = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_res.ok and full_res.ok

    assert not default_res.payload["run_metadata"].get("omitted_fields")
    assert strip_run_metadata(default_res.payload) == strip_run_metadata(
        full_res.payload
    )


def test_fields_projection_does_not_emit_omitted_fields(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    payload = augmented_inputs_for("bazi_birth_chart", all_tool_specs)
    proj_res = call_python_run(
        "bazi_birth_chart",
        payload,
        as_of=e2e_as_of,
        fields=["bazi_birth.four_pillars"],
    )
    assert proj_res.ok
    meta = proj_res.payload["run_metadata"]
    assert not meta.get("omitted_fields")
    assert isinstance(meta.get("duration_ms"), (int, float))
    assert meta["duration_ms"] >= 0
    assert isinstance(meta.get("replay"), dict)


# ---------------------------------------------------------------------------
# R5: Contract generation, hygiene, and stdio MCP process startup
# ---------------------------------------------------------------------------


def test_build_codex_call_contracts_check_zero_drift() -> None:
    script = REPO_ROOT / "scripts" / "build_codex_call_contracts.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        timeout=60.0,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_generated_contracts_readme_removes_legacy_detail_flags() -> None:
    readme_text = (REPO_ROOT / "docs" / "contracts" / "README.md").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        'detail="compact"',
        'detail="audit"',
        "--detail compact",
        "--detail audit",
        "detail=compact",
        "detail=audit",
    ):
        assert (
            forbidden not in readme_text
        ), f"Legacy calculation detail reference {forbidden!r} remains in README.md"
    assert "include" in readme_text
    assert "fields" in readme_text


def test_generated_contract_json_files_contain_no_bloat_or_compact_fields() -> None:
    contract_paths = sorted((REPO_ROOT / "docs" / "contracts").glob("*.json"))
    assert contract_paths, "Expected generated JSON contracts in docs/contracts/"

    for path in contract_paths:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        assert find_bloat_keys(data) == [], f"Bloat keys in {path.name}"
        assert "compact_fields" not in data, f"compact_fields in {path.name}"
        match = BLOAT_PROSE_PATTERN.search(raw_text)
        assert (
            match is None
        ), f"Forbidden audit bloat term {match.group(0)!r} found in {path.name}"


@pytest.mark.asyncio
async def test_generated_contract_json_files_match_live_discover_tools(
    mcp_client: Client,
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    contract_paths = sorted((REPO_ROOT / "docs" / "contracts").glob("*.json"))
    assert contract_paths, "Expected generated JSON contracts in docs/contracts/"

    for path in contract_paths:
        tool_name = path.stem
        contract_data = json.loads(path.read_text(encoding="utf-8"))
        assert contract_data.get("tool") == tool_name
        assert tool_name in all_tool_specs

        live_outcome = await call_mcp_tool(
            mcp_client,
            "discover_tools",
            {"tool": tool_name, "detail": "full"},
        )
        assert live_outcome.ok, live_outcome.payload
        live_spec = live_outcome.payload

        assert contract_data.get("input") == live_spec.get("input_schema")
        assert any(
            key in contract_data
            for key in ("first_view", "default_view", "default_omit")
        ), f"{path.name} missing Plan A view/default metadata"

        live_views = live_spec.get("evidence_views")
        if live_views:
            assert contract_data.get("evidence_views") == live_views
        else:
            assert not contract_data.get("evidence_views")


def test_cli_doctor_mcp_process_startup_succeeds() -> None:
    outcome = call_cli(["doctor", "--mcp"], timeout=60.0)
    assert outcome.ok, outcome.raw_stdout or outcome.raw_stderr
    assert outcome.exit_code == 0
    assert outcome.payload.get("ok") is True
    assert outcome.payload.get("mcp", {}).get("ok") is True
    assert outcome.payload.get("mcp_tool_count") == 3
    assert outcome.payload.get("mcp_capability_count") == 91
