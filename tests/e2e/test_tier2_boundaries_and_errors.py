"""Tier 2 opaque-box E2E tests for boundary conditions and error contracts.

Covers:
- `include` + `fields` mutual exclusion across all 5 surfaces (including empty lists)
- Invalid `include`, `fields`, and `evidence_views` diagnostics across surfaces
- `default_omit` & `omitted_fields` boundary cases (empty, heavy, wildcard, partial)
- R3 scope parameter boundaries (`end_year`, `scan_months`, `scan_days`,
  `search_window_hours`, `orb`, `max_age_years`)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e._surfaces import (
    assert_dotted_path_restored,
    assert_isomorphic_subset,
    augmented_inputs_for,
    call_cli_tool,
    call_mcp_tool,
    call_python_run,
    call_rest_post,
    extract_error_issues,
    has_dotted_path,
    rest_path_for,
    strip_run_metadata,
)

EMPTY_OMIT_TOOLS: tuple[str, ...] = (
    "gua_lookup",
    "place_lookup",
    "compare_bazi_sources",
    "combine_four_gua",
)

HEAVY_OMIT_TOOLS: tuple[str, ...] = (
    "bazi_birth_chart",
    "vedic_chart",
    "horary_chart",
    "astrology_chart",
    "human_design",
)

WILDCARD_OMIT_TOOLS: tuple[str, ...] = (
    "ziwei_timing",
    "hamburg_midpoint_chart",
)

VIEWLESS_TOOLS: tuple[str, ...] = (
    "gua_lookup",
    "bazi_compatibility",
    "solar_return",
)

INVALID_PROJECTION_PATHS: tuple[tuple[str, str, str | None], ...] = (
    ("misspelled_view", "rootz", "roots"),
    ("typo_top_level", "day_mastur", "day_master"),
    ("nonexistent_deep", "nonexistent.deep.path", None),
    ("empty_segment", "", None),
    ("double_dot", "a..b", None),
    ("unknown_list_index", "four_pillars.0", None),
    ("non_object_list_index", "favorable_elements.0", None),
    ("non_object_scalar_attr", "favorable_elements_status.0", None),
)

MUTUAL_EXCLUSION_LIST_CASES: tuple[tuple[str, list[str], list[str]], ...] = (
    ("both_non_empty", ["*"], ["run_metadata"]),
    ("both_empty", [], []),
    ("empty_include_non_empty_fields", [], ["run_metadata"]),
    ("non_empty_include_empty_fields", ["*"], []),
)


def _assert_python_parameter_error(
    tool_name: str,
    payload: dict[str, Any],
    *,
    as_of: str,
    include: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    with pytest.raises(ValueError) as exc_info:
        call_python_run(
            tool_name,
            payload,
            as_of=as_of,
            include=include,
            fields=fields,
        )
    exc = exc_info.value
    assert type(exc).__name__ == "ParameterError"
    assert getattr(exc, "status_code", None) == 422
    issues = getattr(exc, "issues", None)
    assert isinstance(issues, list) and len(issues) > 0
    return [dict(item) for item in issues if isinstance(item, dict)]


def _assert_surface_422_issues(
    issues: list[dict[str, Any]],
    *,
    expected_code: str | None = None,
    require_available: bool = False,
    expected_suggestion: str | None = None,
) -> None:
    assert issues, "Expected structured error issues in 422 response"
    if expected_code is not None:
        assert any(
            issue.get("code") == expected_code for issue in issues
        ), f"Expected issue code {expected_code!r} in {issues!r}"
    if require_available:
        assert any(
            isinstance(issue.get("constraints", {}).get("available"), list)
            and len(issue["constraints"]["available"]) > 0
            for issue in issues
        ), f"Expected non-empty constraints.available in {issues!r}"
    if expected_suggestion is not None:
        assert any(
            expected_suggestion
            in (issue.get("constraints", {}).get("suggestions") or [])
            for issue in issues
        ), f"Expected suggestion {expected_suggestion!r} in {issues!r}"


# ---------------------------------------------------------------------------
# `include` + `fields` Mutual Exclusion (all 5 surfaces)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_include_and_fields_mutual_exclusion_across_all_5_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    py_issues = _assert_python_parameter_error(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["*"],
        fields=["run_metadata"],
    )
    _assert_surface_422_issues(py_issues, expected_code="conflicting_delivery_controls")

    mcp_calc = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["*"],
            "fields": ["run_metadata"],
        },
    )
    assert not mcp_calc.ok
    assert mcp_calc.status_code == 422
    assert mcp_calc.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(mcp_calc.payload),
        expected_code="conflicting_delivery_controls",
    )

    mcp_batch_call = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": ["*"],
                    "fields": ["run_metadata"],
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert not mcp_batch_call.ok
    assert mcp_batch_call.status_code == 422
    assert mcp_batch_call.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(mcp_batch_call.payload),
        expected_code="conflicting_delivery_controls",
    )

    rest_single = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[
            ("as_of", e2e_as_of),
            ("include", "*"),
            ("fields", "run_metadata"),
        ],
    )
    assert not rest_single.ok
    assert rest_single.status_code == 422
    assert rest_single.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(rest_single.payload),
        expected_code="conflicting_delivery_controls",
    )

    rest_batch = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": ["*"],
                    "fields": ["run_metadata"],
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert not rest_batch.ok
    assert rest_batch.status_code == 422
    assert rest_batch.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(rest_batch.payload),
        expected_code="conflicting_delivery_controls",
    )

    cli_out = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["*"],
        fields=["run_metadata"],
    )
    assert not cli_out.ok
    assert cli_out.exit_code == 1
    assert cli_out.status_code == 422
    assert cli_out.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(cli_out.payload),
        expected_code="conflicting_delivery_controls",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "inc_val", "fields_val"),
    MUTUAL_EXCLUSION_LIST_CASES,
    ids=[case[0] for case in MUTUAL_EXCLUSION_LIST_CASES],
)
async def test_include_and_fields_empty_list_combinations_reject_422(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    case_id: str,
    inc_val: list[str],
    fields_val: list[str],
) -> None:
    tool_name = "gua_lookup"
    payload = augmented_inputs_for(tool_name, all_tool_specs)

    py_issues = _assert_python_parameter_error(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=inc_val,
        fields=fields_val,
    )
    _assert_surface_422_issues(py_issues, expected_code="conflicting_delivery_controls")

    mcp_calc = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": inc_val,
            "fields": fields_val,
        },
    )
    assert not mcp_calc.ok, f"{case_id} unexpectedly succeeded on MCP"
    assert mcp_calc.status_code == 422
    _assert_surface_422_issues(
        extract_error_issues(mcp_calc.payload),
        expected_code="conflicting_delivery_controls",
    )

    mcp_batch = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": inc_val,
                    "fields": fields_val,
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert not mcp_batch.ok
    assert mcp_batch.status_code == 422
    _assert_surface_422_issues(
        extract_error_issues(mcp_batch.payload),
        expected_code="conflicting_delivery_controls",
    )

    rest_batch = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": inc_val,
                    "fields": fields_val,
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert not rest_batch.ok
    assert rest_batch.status_code == 422
    _assert_surface_422_issues(
        extract_error_issues(rest_batch.payload),
        expected_code="conflicting_delivery_controls",
    )


def test_cli_empty_string_include_and_fields_combinations_reject_422(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "gua_lookup"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    for inc_arg, fields_arg, expected_code in (
        ([""], [""], "conflicting_delivery_controls"),
        ([""], ["run_metadata"], "conflicting_delivery_controls"),
        (["*"], [""], "conflicting_delivery_controls"),
        ([""], None, "invalid_projection_path"),
        (None, [""], "invalid_projection_path"),
    ):
        cli_out = call_cli_tool(
            tool_name,
            payload,
            as_of=e2e_as_of,
            include=inc_arg,
            fields=fields_arg,
        )
        assert not cli_out.ok
        assert cli_out.exit_code == 1
        assert cli_out.status_code == 422
        assert cli_out.payload.get("error_code") == "validation_error"
        _assert_surface_422_issues(
            extract_error_issues(cli_out.payload),
            expected_code=expected_code,
        )


def test_rest_empty_and_whitespace_delivery_query_params_and_batch_detail_422(
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    for query_string, expected_code in (
        ("?include=&fields=", "conflicting_delivery_controls"),
        ("?include=", "invalid_projection_path"),
        ("?fields=", "invalid_projection_path"),
        ("?include=%20", "invalid_projection_path"),
        ("?fields=%20", "invalid_projection_path"),
        ("?detail=", "extra_forbidden"),
    ):
        resp = rest_client.post(f"{rest_path}{query_string}", json=payload)
        assert resp.status_code == 422, (query_string, resp.text)
        body = resp.json()
        assert body.get("error_code") == "validation_error"
        _assert_surface_422_issues(
            extract_error_issues(body),
            expected_code=expected_code,
        )

    gua_payload = augmented_inputs_for("gua_lookup", all_tool_specs)
    batch_resp = rest_client.post(
        "/api/batch?detail=compact",
        json={
            "calls": [
                {"id": "c1", "tool": "gua_lookup", "arguments": gua_payload},
            ]
        },
    )
    assert batch_resp.status_code == 422, batch_resp.text
    batch_body = batch_resp.json()
    assert batch_body.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(batch_body),
        expected_code="extra_forbidden",
    )


# ---------------------------------------------------------------------------
# Invalid `include`, `fields`, & `evidence_views` Diagnostics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_misspelled_evidence_view_returns_suggestions_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    assert "roots" in all_tool_specs[tool_name].get("evidence_views", {})
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    py_issues = _assert_python_parameter_error(
        tool_name, payload, as_of=e2e_as_of, include=["rootz"]
    )
    _assert_surface_422_issues(
        py_issues,
        expected_code="unknown_projection_path",
        require_available=True,
        expected_suggestion="roots",
    )

    mcp_out = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["rootz"],
        },
    )
    assert not mcp_out.ok
    assert mcp_out.status_code == 422
    assert mcp_out.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(mcp_out.payload),
        expected_code="unknown_projection_path",
        require_available=True,
        expected_suggestion="roots",
    )

    rest_out = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("include", "rootz")],
    )
    assert not rest_out.ok
    assert rest_out.status_code == 422
    assert rest_out.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(rest_out.payload),
        expected_code="unknown_projection_path",
        require_available=True,
        expected_suggestion="roots",
    )

    cli_out = call_cli_tool(tool_name, payload, as_of=e2e_as_of, include=["rootz"])
    assert not cli_out.ok
    assert cli_out.exit_code == 1
    assert cli_out.status_code == 422
    assert cli_out.payload.get("error_code") == "validation_error"
    _assert_surface_422_issues(
        extract_error_issues(cli_out.payload),
        expected_code="unknown_projection_path",
        require_available=True,
        expected_suggestion="roots",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", VIEWLESS_TOOLS)
async def test_unknown_view_on_viewless_tools_rejects_with_available(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    assert not all_tool_specs[tool_name].get("evidence_views")
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    py_issues = _assert_python_parameter_error(
        tool_name, payload, as_of=e2e_as_of, include=["nonexistent_view"]
    )
    _assert_surface_422_issues(
        py_issues, expected_code="unknown_projection_path", require_available=True
    )

    mcp_out = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["nonexistent_view"],
        },
    )
    assert not mcp_out.ok
    assert mcp_out.status_code == 422
    _assert_surface_422_issues(
        extract_error_issues(mcp_out.payload),
        expected_code="unknown_projection_path",
        require_available=True,
    )

    rest_out = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("include", "nonexistent_view")],
    )
    assert not rest_out.ok
    assert rest_out.status_code == 422
    _assert_surface_422_issues(
        extract_error_issues(rest_out.payload),
        expected_code="unknown_projection_path",
        require_available=True,
    )

    mcp_batch = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": ["nonexistent_view"],
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert mcp_batch.ok
    assert mcp_batch.payload.get("status") == "error"
    assert mcp_batch.payload.get("failed") == 1
    mcp_item = mcp_batch.payload["results"][0]
    assert mcp_item["ok"] is False
    assert mcp_item["error"]["status_code"] == 422
    _assert_surface_422_issues(
        extract_error_issues(mcp_item["error"]),
        expected_code="unknown_projection_path",
        require_available=True,
    )

    rest_batch = call_rest_post(
        rest_client,
        "/api/batch",
        json_body={
            "calls": [
                {
                    "id": "c1",
                    "tool": tool_name,
                    "arguments": payload,
                    "include": ["nonexistent_view"],
                }
            ],
            "as_of": e2e_as_of,
        },
    )
    assert rest_batch.ok
    assert rest_batch.payload.get("status") == "error"
    assert rest_batch.payload.get("failed") == 1
    rest_item = rest_batch.payload["results"][0]
    assert rest_item["ok"] is False
    assert rest_item["error"]["status_code"] == 422
    _assert_surface_422_issues(
        extract_error_issues(rest_item["error"]),
        expected_code="unknown_projection_path",
        require_available=True,
    )

    cli_out = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["nonexistent_view"],
    )
    assert not cli_out.ok
    assert cli_out.exit_code == 1
    assert cli_out.status_code == 422
    _assert_surface_422_issues(
        extract_error_issues(cli_out.payload),
        expected_code="unknown_projection_path",
        require_available=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "bad_path", "expected_suggestion"),
    INVALID_PROJECTION_PATHS,
    ids=[case[0] for case in INVALID_PROJECTION_PATHS],
)
async def test_invalid_include_and_fields_dotted_paths_reject_422(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    case_id: str,
    bad_path: str,
    expected_suggestion: str | None,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    if bad_path in ("", "a..b"):
        expected_code = "invalid_projection_path"
    elif case_id.startswith("non_object_"):
        expected_code = "non_object_projection_path"
    else:
        expected_code = "unknown_projection_path"
    require_available = expected_code == "unknown_projection_path"

    for control_name in ("include", "fields"):
        inc_arg = [bad_path] if control_name == "include" else None
        fields_arg = [bad_path] if control_name == "fields" else None
        suggestion_for_call = (
            expected_suggestion
            if not (control_name == "fields" and bad_path == "rootz")
            else None
        )
        py_issues = _assert_python_parameter_error(
            tool_name,
            payload,
            as_of=e2e_as_of,
            include=inc_arg,
            fields=fields_arg,
        )
        _assert_surface_422_issues(
            py_issues,
            expected_code=expected_code,
            require_available=require_available,
            expected_suggestion=suggestion_for_call,
        )

        mcp_out = await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {
                "tool": tool_name,
                "arguments": payload,
                "as_of": e2e_as_of,
                control_name: [bad_path],
            },
        )
        assert not mcp_out.ok, f"{case_id} ({control_name}) passed unexpectedly"
        assert mcp_out.status_code == 422
        _assert_surface_422_issues(
            extract_error_issues(mcp_out.payload),
            expected_code=expected_code,
            require_available=require_available,
            expected_suggestion=suggestion_for_call,
        )

        rest_out = call_rest_post(
            rest_client,
            rest_path,
            json_body=payload,
            params=[("as_of", e2e_as_of), (control_name, bad_path)],
        )
        assert not rest_out.ok
        assert rest_out.status_code == 422
        _assert_surface_422_issues(
            extract_error_issues(rest_out.payload),
            expected_code=expected_code,
            require_available=require_available,
            expected_suggestion=suggestion_for_call,
        )

        cli_out = call_cli_tool(
            tool_name,
            payload,
            as_of=e2e_as_of,
            include=inc_arg,
            fields=fields_arg,
        )
        assert not cli_out.ok
        assert cli_out.exit_code == 1
        assert cli_out.status_code == 422
        _assert_surface_422_issues(
            extract_error_issues(cli_out.payload),
            expected_code=expected_code,
            require_available=require_available,
            expected_suggestion=suggestion_for_call,
        )


# ---------------------------------------------------------------------------
# `default_omit` & `omitted_fields` Boundary Cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tool_name", EMPTY_OMIT_TOOLS)
def test_empty_default_omit_tools_match_full_output_and_omit_metadata(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_out.ok and full_out.ok

    assert not default_out.payload["run_metadata"].get("omitted_fields")
    assert not full_out.payload["run_metadata"].get("omitted_fields")
    assert strip_run_metadata(default_out.payload) == strip_run_metadata(
        full_out.payload
    )


@pytest.mark.parametrize("tool_name", HEAVY_OMIT_TOOLS)
def test_heavy_tools_emit_non_empty_omitted_fields_and_restore_on_star(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_out.ok and full_out.ok

    omitted = default_out.payload["run_metadata"].get("omitted_fields")
    assert (
        isinstance(omitted, list) and len(omitted) > 0
    ), f"Expected heavy tool {tool_name!r} to report non-empty omitted_fields"
    default_biz = strip_run_metadata(default_out.payload)
    full_biz = strip_run_metadata(full_out.payload)
    assert_isomorphic_subset(default_biz, full_biz)
    for omitted_path in omitted:
        assert not has_dotted_path(default_biz, omitted_path)
        assert has_dotted_path(full_biz, omitted_path)
    assert not full_out.payload["run_metadata"].get("omitted_fields")


@pytest.mark.parametrize("tool_name", WILDCARD_OMIT_TOOLS)
def test_nested_and_wildcard_default_omit_subtrees_restore_cleanly(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    full_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=["*"])
    assert default_out.ok and full_out.ok

    omitted = default_out.payload["run_metadata"].get("omitted_fields")
    assert isinstance(omitted, list) and len(omitted) > 0
    assert any(
        "." in path or "*" in path for path in omitted
    ), f"Expected nested/wildcard omitted paths on {tool_name!r}, got {omitted!r}"

    default_biz = strip_run_metadata(default_out.payload)
    full_biz = strip_run_metadata(full_out.payload)
    for omitted_path in omitted:
        assert not has_dotted_path(default_biz, omitted_path)
        assert has_dotted_path(full_biz, omitted_path)

    nested_target = next(
        (path for path in omitted if "*" in path),
        next(path for path in omitted if "." in path),
    )
    targeted_out = call_python_run(
        tool_name, payload, as_of=e2e_as_of, include=[nested_target]
    )
    assert targeted_out.ok, targeted_out.payload
    targeted_biz = strip_run_metadata(targeted_out.payload)
    assert_dotted_path_restored(default_biz, targeted_biz, full_biz, nested_target)
    assert_isomorphic_subset(default_biz, targeted_biz)
    assert_isomorphic_subset(targeted_biz, full_biz)
    remaining = targeted_out.payload["run_metadata"].get("omitted_fields") or []
    assert nested_target not in remaining


@pytest.mark.parametrize(
    ("tool_name", "view_name"),
    (("bazi_birth_chart", "calendar_basis"), ("vedic_chart", "strength")),
)
def test_partial_include_overlap_updates_omitted_fields_preserving_others(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
    view_name: str,
) -> None:
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    assert default_out.ok
    default_omitted = list(
        default_out.payload["run_metadata"].get("omitted_fields") or []
    )
    assert len(default_omitted) >= 2

    target_path = default_omitted[0]
    path_out = call_python_run(
        tool_name, payload, as_of=e2e_as_of, include=[target_path]
    )
    assert path_out.ok, path_out.payload
    assert has_dotted_path(strip_run_metadata(path_out.payload), target_path)
    path_remaining = list(path_out.payload["run_metadata"].get("omitted_fields") or [])
    assert target_path not in path_remaining
    for untouched in default_omitted[1:]:
        assert untouched in path_remaining

    view_fields = all_tool_specs[tool_name]["evidence_views"][view_name]["fields"]
    view_out = call_python_run(tool_name, payload, as_of=e2e_as_of, include=[view_name])
    assert view_out.ok, view_out.payload
    view_biz = strip_run_metadata(view_out.payload)
    for field_path in view_fields:
        assert has_dotted_path(view_biz, field_path)
    view_remaining = list(view_out.payload["run_metadata"].get("omitted_fields") or [])
    assert len(view_remaining) < len(default_omitted)
    for field_path in view_fields:
        assert field_path not in view_remaining


def test_including_already_present_top_level_key_keeps_omitted_fields_intact(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    default_out = call_python_run(tool_name, payload, as_of=e2e_as_of)
    present_out = call_python_run(
        tool_name, payload, as_of=e2e_as_of, include=["day_master"]
    )
    assert default_out.ok and present_out.ok

    default_omitted = default_out.payload["run_metadata"].get("omitted_fields") or []
    assert default_omitted, "Expected bazi_overview default to omit secondary fields"
    assert "day_master" not in default_omitted
    assert has_dotted_path(strip_run_metadata(default_out.payload), "day_master")
    assert present_out.payload["run_metadata"].get("omitted_fields") == default_omitted
    assert strip_run_metadata(present_out.payload) == strip_run_metadata(
        default_out.payload
    )


# ---------------------------------------------------------------------------
# R3 Scope Parameter Boundary Cases
# ---------------------------------------------------------------------------


def test_r3_bazi_yearly_timing_end_year_span_boundary(
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_yearly_timing"
    base = augmented_inputs_for(tool_name, all_tool_specs)
    analysis_year = int(base["analysis_year"])
    rest_path = rest_path_for(tool_name, all_tool_specs)

    valid_span20 = {**base, "end_year": analysis_year + 19}
    py_ok = call_python_run(tool_name, valid_span20, as_of=e2e_as_of)
    rest_ok = call_rest_post(
        rest_client,
        rest_path,
        json_body=valid_span20,
        params=[("as_of", e2e_as_of)],
    )
    assert py_ok.ok and rest_ok.ok

    invalid_span21 = {**base, "end_year": analysis_year + 20}
    py_err = call_python_run(tool_name, invalid_span21, as_of=e2e_as_of)
    rest_err = call_rest_post(
        rest_client,
        rest_path,
        json_body=invalid_span21,
        params=[("as_of", e2e_as_of)],
    )
    for err in (py_err, rest_err):
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"


def test_r3_bazi_monthly_timing_scan_months_boundaries(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_monthly_timing"
    base = augmented_inputs_for(tool_name, all_tool_specs)

    out_1 = call_python_run(tool_name, {**base, "scan_months": 1}, as_of=e2e_as_of)
    out_24 = call_python_run(tool_name, {**base, "scan_months": 24}, as_of=e2e_as_of)
    assert out_1.ok, out_1.payload
    assert out_24.ok, out_24.payload
    months_1 = out_1.payload["monthly_timeline"]
    months_24 = out_24.payload["monthly_timeline"]
    assert len(months_1) == 1
    assert len(months_24) == 24
    assert len(months_1) < len(months_24)

    for invalid_months in (0, 25):
        err = call_python_run(
            tool_name, {**base, "scan_months": invalid_months}, as_of=e2e_as_of
        )
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"


def test_r3_bazi_daily_timing_scan_days_boundaries(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_daily_timing"
    base = augmented_inputs_for(tool_name, all_tool_specs)

    out_1 = call_python_run(tool_name, {**base, "scan_days": 1}, as_of=e2e_as_of)
    out_31 = call_python_run(tool_name, {**base, "scan_days": 31}, as_of=e2e_as_of)
    assert out_1.ok, out_1.payload
    assert out_31.ok, out_31.payload
    days_1 = out_1.payload["daily_timeline"]
    days_31 = out_31.payload["daily_timeline"]
    assert len(days_1) == 1
    assert len(days_31) == 31
    assert len(days_1) < len(days_31)

    for invalid_days in (0, 32):
        err = call_python_run(
            tool_name, {**base, "scan_days": invalid_days}, as_of=e2e_as_of
        )
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"


def test_r3_transit_chart_scan_days_boundaries(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "transit_chart"
    base = augmented_inputs_for(tool_name, all_tool_specs)

    out_1 = call_python_run(
        tool_name, {**base, "scan_days": 1}, as_of=e2e_as_of, include=["*"]
    )
    out_90 = call_python_run(
        tool_name, {**base, "scan_days": 90}, as_of=e2e_as_of, include=["*"]
    )
    assert out_1.ok, out_1.payload
    assert out_90.ok, out_90.payload
    tl_1 = out_1.payload["transit_chart"]["transit_timeline"]
    tl_90 = out_90.payload["transit_chart"]["transit_timeline"]
    assert len(tl_1) == 1
    assert len(tl_90) == 90
    assert len(tl_1) < len(tl_90)

    for invalid_days in (0, 91):
        err = call_python_run(
            tool_name, {**base, "scan_days": invalid_days}, as_of=e2e_as_of
        )
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"


def test_r3_evaluate_election_time_search_window_hours_boundaries(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "evaluate_election_time"
    base = augmented_inputs_for(tool_name, all_tool_specs)

    out_0 = call_python_run(
        tool_name, {**base, "search_window_hours": 0}, as_of=e2e_as_of, include=["*"]
    )
    out_24 = call_python_run(
        tool_name, {**base, "search_window_hours": 24}, as_of=e2e_as_of, include=["*"]
    )
    assert out_0.ok, out_0.payload
    assert out_24.ok, out_24.payload
    assert strip_run_metadata(out_0.payload) != strip_run_metadata(out_24.payload)
    el_0 = out_0.payload["election"]
    el_24 = out_24.payload["election"]
    assert not el_0.get("candidate_windows")
    windows_24 = el_24.get("candidate_windows") or []
    assert len(windows_24) == 5
    total_24 = el_24.get("candidate_windows_total_count")
    assert isinstance(total_24, int)
    assert total_24 == 25 > len(windows_24)

    for invalid_hours in (-1, 169):
        err = call_python_run(
            tool_name,
            {**base, "search_window_hours": invalid_hours},
            as_of=e2e_as_of,
        )
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"


@pytest.mark.parametrize(
    ("tool_name", "key_field"),
    (
        ("planetary_arc_directions", "planetary_arc"),
        ("sidereal_progressions", "sidereal_progressions"),
    ),
)
def test_r3_western_lifespan_orb_boundaries_and_monotonic_hits(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
    key_field: str,
) -> None:
    base = augmented_inputs_for(tool_name, all_tool_specs)

    hit_counts: list[int] = []
    for valid_orb in (0.0, 1.0, 15.0):
        out = call_python_run(
            tool_name, {**base, "orb": valid_orb}, as_of=e2e_as_of, include=["*"]
        )
        assert out.ok, out.payload
        hit_counts.append(len(out.payload[key_field]["hits"]))

    assert hit_counts[0] <= hit_counts[1] <= hit_counts[2]
    assert hit_counts[0] < hit_counts[-1]

    for invalid_orb in (-0.1, 15.1):
        err = call_python_run(tool_name, {**base, "orb": invalid_orb}, as_of=e2e_as_of)
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"


def test_r3_persian_directions_max_age_years_boundaries_and_monotonic_hits(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "persian_directions"
    base = augmented_inputs_for(tool_name, all_tool_specs)

    hit_counts: list[int] = []
    for valid_age in (1.0, 90.0, 200.0):
        out = call_python_run(
            tool_name,
            {**base, "max_age_years": valid_age},
            as_of=e2e_as_of,
            include=["*"],
        )
        assert out.ok, out.payload
        hit_counts.append(len(out.payload["persian_directions"]["hits"]))

    assert hit_counts[0] <= hit_counts[1] <= hit_counts[2]
    assert hit_counts[0] < hit_counts[-1]

    for invalid_age in (0.0, 200.1):
        err = call_python_run(
            tool_name, {**base, "max_age_years": invalid_age}, as_of=e2e_as_of
        )
        assert not err.ok
        assert err.status_code == 422
        assert err.payload.get("error_code") == "validation_error"
