"""Tier 3 opaque-box E2E tests for cross-feature pairwise combinations and surface parity."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e._surfaces import (
    assert_isomorphic_subset,
    augmented_inputs_for,
    call_cli,
    call_cli_tool,
    call_mcp_tool,
    call_python_run,
    call_rest_post,
    extract_error_issues,
    find_bloat_keys,
    has_dotted_path,
    rest_path_for,
    strip_run_metadata,
)

SHARED_SUBJECT: dict[str, Any] = {
    "name": "测试甲",
    "gender": "male",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_place": "北京",
    "birth_longitude": 116.4074,
    "birth_latitude": 39.9042,
    "timezone": "Asia/Shanghai",
}

SHARED_CONTEXT: dict[str, Any] = {
    "year": 2026,
    "month": 10,
    "day": 12,
    "hour": 4,
    "minute": 0,
    "place": "北京",
    "longitude": 116.4074,
    "latitude": 39.9042,
    "timezone": "Asia/Shanghai",
}


def _call_cli_batch(batch_payload: dict[str, Any]) -> Any:
    return call_cli(
        ["batch", "--request-file", "-"],
        stdin_text=json.dumps(batch_payload, ensure_ascii=False),
    )


def _assert_unified_run_metadata(
    meta: dict[str, Any],
    *,
    tool_name: str,
    as_of: str,
) -> None:
    assert meta.get("tool_name") == tool_name
    assert isinstance(meta.get("duration_ms"), (int, float))
    assert meta["duration_ms"] >= 0
    replay = meta.get("replay")
    assert isinstance(replay, dict)
    assert replay.get("as_of") == as_of
    assert isinstance(replay.get("overrides"), dict)
    assert isinstance(replay.get("requires_original_input"), bool)
    effective_time = meta.get("effective_time")
    assert isinstance(effective_time, dict)
    assert effective_time.get("as_of") == as_of


# ---------------------------------------------------------------------------
# Pairwise 1: `run_batch` shared subject + context + defaults + mixed modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_batch_same_tool_shared_subject_context_consistency_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    views = all_tool_specs[tool_name].get("evidence_views", {})
    assert "calendar_basis" in views
    view_fields = list(views["calendar_basis"]["fields"])
    assert view_fields
    projected_fields = ["bazi_birth.day_master", "bazi_birth.four_pillars"]

    batch_payload: dict[str, Any] = {
        "subjects": {"native": SHARED_SUBJECT},
        "context": SHARED_CONTEXT,
        "defaults": {"zi_hour_policy": "day_rollover_at_23"},
        "as_of": e2e_as_of,
        "calls": [
            {"id": "default_call", "tool": tool_name, "subject": "native"},
            {
                "id": "view_call",
                "tool": tool_name,
                "subject": "native",
                "include": ["calendar_basis"],
            },
            {
                "id": "full_call",
                "tool": tool_name,
                "subject": "native",
                "include": ["*"],
            },
            {
                "id": "fields_call",
                "tool": tool_name,
                "subject": "native",
                "fields": projected_fields,
            },
        ],
    }

    mcp_outcome = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_outcome = call_rest_post(rest_client, "/api/batch", json_body=batch_payload)
    cli_outcome = _call_cli_batch(batch_payload)

    for outcome in (mcp_outcome, rest_outcome, cli_outcome):
        assert outcome.ok, outcome.payload
        assert outcome.status_code == 200
        assert outcome.payload["status"] == "ok"
        assert outcome.payload["succeeded"] == 4
        assert outcome.payload["failed"] == 0
        assert outcome.payload["as_of"] == e2e_as_of
        assert len(outcome.payload["results"]) == 4

    mcp_by_id = {item["id"]: item["result"] for item in mcp_outcome.payload["results"]}
    rest_by_id = {
        item["id"]: item["result"] for item in rest_outcome.payload["results"]
    }
    cli_by_id = {item["id"]: item["result"] for item in cli_outcome.payload["results"]}

    for call_id in ("default_call", "view_call", "full_call", "fields_call"):
        assert strip_run_metadata(mcp_by_id[call_id]) == strip_run_metadata(
            rest_by_id[call_id]
        )
        assert strip_run_metadata(mcp_by_id[call_id]) == strip_run_metadata(
            cli_by_id[call_id]
        )

    for by_id in (mcp_by_id, rest_by_id, cli_by_id):
        default_res = by_id["default_call"]
        view_res = by_id["view_call"]
        full_res = by_id["full_call"]
        fields_res = by_id["fields_call"]

        for res in (default_res, view_res, full_res, fields_res):
            assert find_bloat_keys(res) == []
            _assert_unified_run_metadata(
                res["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
            )

        default_omitted = default_res["run_metadata"].get("omitted_fields") or []
        view_omitted = view_res["run_metadata"].get("omitted_fields") or []
        assert default_omitted, "Expected default bazi_birth_chart to omit heavy blocks"
        assert not full_res["run_metadata"].get("omitted_fields")
        assert not fields_res["run_metadata"].get("omitted_fields")

        for field_path in view_fields:
            assert has_dotted_path(view_res, field_path)
            assert field_path not in view_omitted
        assert len(view_omitted) < len(default_omitted)

        assert_isomorphic_subset(default_res, view_res)
        assert_isomorphic_subset(view_res, full_res)
        assert_isomorphic_subset(fields_res, full_res)
        assert set(strip_run_metadata(fields_res)) == {"bazi_birth"}
        assert set(fields_res["bazi_birth"]) == {"day_master", "four_pillars"}


# ---------------------------------------------------------------------------
# Pairwise 2: `run_batch` partial_error, conflicting controls & stop_on_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_batch_partial_error_with_invalid_include_and_fields_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    batch_payload: dict[str, Any] = {
        "subjects": {"native": SHARED_SUBJECT},
        "context": SHARED_CONTEXT,
        "as_of": e2e_as_of,
        "calls": [
            {"id": "ok_default", "tool": tool_name, "subject": "native"},
            {
                "id": "ok_include",
                "tool": tool_name,
                "subject": "native",
                "include": ["calendar_basis"],
            },
            {
                "id": "ok_fields",
                "tool": tool_name,
                "subject": "native",
                "fields": ["bazi_birth.day_master"],
            },
            {
                "id": "bad_include",
                "tool": tool_name,
                "subject": "native",
                "include": ["calendar_basi"],
            },
            {
                "id": "bad_fields",
                "tool": tool_name,
                "subject": "native",
                "fields": ["bazi_birth.day_mastr"],
            },
        ],
    }

    mcp_outcome = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_outcome = call_rest_post(rest_client, "/api/batch", json_body=batch_payload)
    cli_outcome = _call_cli_batch(batch_payload)

    for outcome in (mcp_outcome, rest_outcome, cli_outcome):
        assert outcome.ok, outcome.payload
        assert outcome.status_code == 200
        assert outcome.payload["status"] == "partial_error"
        assert outcome.payload["succeeded"] == 3
        assert outcome.payload["failed"] == 2
        results = outcome.payload["results"]
        assert [item["id"] for item in results] == [
            "ok_default",
            "ok_include",
            "ok_fields",
            "bad_include",
            "bad_fields",
        ]
        assert all(item["ok"] is True for item in results[:3])

        bad_include_err = results[3]["error"]
        assert results[3]["ok"] is False
        assert bad_include_err["error_code"] == "validation_error"
        inc_issues = extract_error_issues(bad_include_err)
        assert inc_issues and inc_issues[0]["code"] == "unknown_projection_path"
        inc_constraints = inc_issues[0].get("constraints", {})
        assert inc_constraints.get("available")
        assert "calendar_basis" in (inc_constraints.get("suggestions") or [])

        bad_fields_err = results[4]["error"]
        assert results[4]["ok"] is False
        assert bad_fields_err["error_code"] == "validation_error"
        fld_issues = extract_error_issues(bad_fields_err)
        assert fld_issues and fld_issues[0]["code"] == "unknown_projection_path"
        fld_constraints = fld_issues[0].get("constraints", {})
        assert fld_constraints.get("available")
        assert "day_master" in (fld_constraints.get("suggestions") or [])

    assert cli_outcome.exit_code == 0


@pytest.mark.asyncio
async def test_run_batch_rejects_conflicting_include_and_fields_on_call(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    batch_payload: dict[str, Any] = {
        "subjects": {"native": SHARED_SUBJECT},
        "as_of": e2e_as_of,
        "calls": [
            {
                "id": "conflict_call",
                "tool": "bazi_birth_chart",
                "subject": "native",
                "include": ["calendar_basis"],
                "fields": ["bazi_birth.day_master"],
            }
        ],
    }

    mcp_outcome = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_outcome = call_rest_post(rest_client, "/api/batch", json_body=batch_payload)
    cli_outcome = _call_cli_batch(batch_payload)

    assert not mcp_outcome.ok
    assert mcp_outcome.status_code == 422
    assert not rest_outcome.ok
    assert rest_outcome.status_code == 422
    assert not cli_outcome.ok
    assert cli_outcome.exit_code == 1

    for outcome in (mcp_outcome, rest_outcome, cli_outcome):
        assert outcome.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(outcome.payload)
        assert issues
        assert any(
            issue.get("code") == "conflicting_delivery_controls" for issue in issues
        )


@pytest.mark.asyncio
async def test_run_batch_stop_on_error_halts_after_invalid_include(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    batch_payload: dict[str, Any] = {
        "subjects": {"native": SHARED_SUBJECT},
        "context": SHARED_CONTEXT,
        "as_of": e2e_as_of,
        "stop_on_error": True,
        "calls": [
            {
                "id": "first_include",
                "tool": "bazi_birth_chart",
                "subject": "native",
                "include": ["calendar_basis"],
            },
            {
                "id": "second_fields",
                "tool": "bazi_overview",
                "subject": "native",
                "fields": ["day_master"],
            },
            {
                "id": "failing_include",
                "tool": "bazi_birth_chart",
                "subject": "native",
                "include": ["nonexistent_view_xyz"],
            },
            {
                "id": "skipped_call",
                "tool": "fengshui_minggua",
                "subject": "native",
            },
        ],
    }

    mcp_outcome = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_outcome = call_rest_post(rest_client, "/api/batch", json_body=batch_payload)
    cli_outcome = _call_cli_batch(batch_payload)

    for outcome in (mcp_outcome, rest_outcome, cli_outcome):
        assert outcome.ok, outcome.payload
        assert outcome.payload["status"] == "partial_error"
        assert outcome.payload["succeeded"] == 2
        assert outcome.payload["failed"] == 1
        results = outcome.payload["results"]
        assert [item["id"] for item in results] == [
            "first_include",
            "second_fields",
            "failing_include",
        ]
        assert results[0]["ok"] is True
        assert has_dotted_path(results[0]["result"], "bazi_birth.calendar_context")
        assert results[1]["ok"] is True
        assert set(strip_run_metadata(results[1]["result"])) == {"day_master"}
        assert results[2]["ok"] is False
        assert results[2]["error"]["error_code"] == "validation_error"
        issues = extract_error_issues(results[2]["error"])
        assert issues and issues[0]["constraints"].get("available")


@pytest.mark.asyncio
async def test_run_batch_rejects_detail_and_unknown_subject_upfront_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    gua_input = augmented_inputs_for("gua_lookup", all_tool_specs)
    top_detail_payload = {
        "calls": [{"id": "c1", "tool": "gua_lookup", "arguments": gua_input}],
        "as_of": e2e_as_of,
        "detail": "compact",
    }
    call_detail_payload = {
        "calls": [
            {
                "id": "c1",
                "tool": "gua_lookup",
                "arguments": gua_input,
                "detail": "audit",
            }
        ],
        "as_of": e2e_as_of,
    }
    unknown_subject_payload = {
        "subjects": {"alice": SHARED_SUBJECT},
        "as_of": e2e_as_of,
        "calls": [{"id": "c1", "tool": "bazi_birth_chart", "subject": "missing"}],
    }

    for payload in (top_detail_payload, call_detail_payload):
        mcp_err = await call_mcp_tool(mcp_client, "run_batch", payload)
        rest_err = call_rest_post(rest_client, "/api/batch", json_body=payload)
        cli_err = _call_cli_batch(payload)

        assert not mcp_err.ok and mcp_err.status_code == 422
        assert not rest_err.ok and rest_err.status_code == 422
        assert not cli_err.ok and cli_err.exit_code == 1
        for outcome in (mcp_err, rest_err, cli_err):
            assert outcome.payload.get("error_code") == "validation_error"

    mcp_subj = await call_mcp_tool(mcp_client, "run_batch", unknown_subject_payload)
    rest_subj = call_rest_post(
        rest_client, "/api/batch", json_body=unknown_subject_payload
    )
    cli_subj = _call_cli_batch(unknown_subject_payload)

    assert not mcp_subj.ok and mcp_subj.status_code == 422
    assert not rest_subj.ok and rest_subj.status_code == 422
    assert not cli_subj.ok and cli_subj.exit_code == 1
    for outcome in (mcp_subj, rest_subj, cli_subj):
        assert outcome.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(outcome.payload)
        assert issues and issues[0]["code"] == "unknown_subject"
        assert issues[0].get("constraints") == {"available": ["alice"]}


# ---------------------------------------------------------------------------
# Pairwise 3: CLI flag combinations
# ---------------------------------------------------------------------------


def test_cli_pairwise_include_and_fields_with_as_of(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    view_fields = list(
        all_tool_specs[tool_name]["evidence_views"]["calendar_basis"]["fields"]
    )

    inc_outcome = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["calendar_basis"],
    )
    assert inc_outcome.ok, inc_outcome.raw_stdout or inc_outcome.raw_stderr
    assert inc_outcome.exit_code == 0
    _assert_unified_run_metadata(
        inc_outcome.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
    )
    for field_path in view_fields:
        assert has_dotted_path(inc_outcome.payload, field_path)
    remaining_omitted = inc_outcome.payload["run_metadata"].get("omitted_fields") or []
    for field_path in view_fields:
        assert field_path not in remaining_omitted

    fields_outcome = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        fields=["bazi_birth.day_master", "bazi_birth.four_pillars"],
    )
    assert fields_outcome.ok, fields_outcome.raw_stdout or fields_outcome.raw_stderr
    assert fields_outcome.exit_code == 0
    _assert_unified_run_metadata(
        fields_outcome.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
    )
    assert not fields_outcome.payload["run_metadata"].get("omitted_fields")
    assert set(strip_run_metadata(fields_outcome.payload)) == {"bazi_birth"}
    assert set(fields_outcome.payload["bazi_birth"]) == {
        "day_master",
        "four_pillars",
    }


def test_cli_pairwise_conflicting_and_legacy_detail_flags(
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)

    conflict_outcome = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["*"],
        fields=["bazi_birth.day_master"],
    )
    assert not conflict_outcome.ok
    assert conflict_outcome.exit_code == 1
    assert conflict_outcome.payload.get("error_code") == "validation_error"
    issues = extract_error_issues(conflict_outcome.payload)
    assert issues and issues[0]["code"] == "conflicting_delivery_controls"

    legacy_include_outcome = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["*"],
        extra_flags=["--detail", "compact"],
    )
    assert not legacy_include_outcome.ok
    assert legacy_include_outcome.exit_code == 2
    assert legacy_include_outcome.payload.get("error_code") == "usage_error"

    legacy_fields_outcome = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        fields=["bazi_birth.day_master"],
        extra_flags=["--detail", "audit"],
    )
    assert not legacy_fields_outcome.ok
    assert legacy_fields_outcome.exit_code == 2
    assert legacy_fields_outcome.payload.get("error_code") == "usage_error"


# ---------------------------------------------------------------------------
# Pairwise 4: 4-Surface & 3-Surface Parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_four_surface_parity_default_and_targeted_include(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    for tool_name, view_name in (
        ("bazi_birth_chart", "calendar_basis"),
        ("vedic_chart", "strength"),
    ):
        payload = augmented_inputs_for(tool_name, all_tool_specs)
        rest_path = rest_path_for(tool_name, all_tool_specs)

        py_def = call_python_run(tool_name, payload, as_of=e2e_as_of)
        mcp_def = await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": tool_name, "arguments": payload, "as_of": e2e_as_of},
        )
        rest_def = call_rest_post(
            rest_client,
            rest_path,
            json_body=payload,
            params=[("as_of", e2e_as_of)],
        )
        cli_def = call_cli_tool(tool_name, payload, as_of=e2e_as_of)

        def_outcomes = (py_def, mcp_def, rest_def, cli_def)
        for outcome in def_outcomes:
            assert outcome.ok, outcome.payload
            assert find_bloat_keys(outcome.payload) == []
            _assert_unified_run_metadata(
                outcome.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
            )

        expected_def_business = strip_run_metadata(py_def.payload)
        expected_def_omitted = py_def.payload["run_metadata"].get("omitted_fields")
        assert expected_def_omitted
        for outcome in def_outcomes[1:]:
            assert strip_run_metadata(outcome.payload) == expected_def_business
            assert (
                outcome.payload["run_metadata"].get("omitted_fields")
                == expected_def_omitted
            )

        py_inc = call_python_run(
            tool_name, payload, as_of=e2e_as_of, include=[view_name]
        )
        mcp_inc = await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {
                "tool": tool_name,
                "arguments": payload,
                "as_of": e2e_as_of,
                "include": [view_name],
            },
        )
        rest_inc = call_rest_post(
            rest_client,
            rest_path,
            json_body=payload,
            params=[("as_of", e2e_as_of), ("include", view_name)],
        )
        cli_inc = call_cli_tool(
            tool_name, payload, as_of=e2e_as_of, include=[view_name]
        )

        inc_outcomes = (py_inc, mcp_inc, rest_inc, cli_inc)
        for outcome in inc_outcomes:
            assert outcome.ok, outcome.payload
            assert find_bloat_keys(outcome.payload) == []
            _assert_unified_run_metadata(
                outcome.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
            )
            assert_isomorphic_subset(py_def.payload, outcome.payload)

        expected_inc_business = strip_run_metadata(py_inc.payload)
        expected_inc_omitted = py_inc.payload["run_metadata"].get("omitted_fields")
        for outcome in inc_outcomes[1:]:
            assert strip_run_metadata(outcome.payload) == expected_inc_business
            assert (
                outcome.payload["run_metadata"].get("omitted_fields")
                == expected_inc_omitted
            )


@pytest.mark.asyncio
async def test_four_surface_parity_lossless_include_star_and_strict_fields(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    selected_fields = ["four_pillars", "day_master.strength"]

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
    cli_full = call_cli_tool(tool_name, payload, as_of=e2e_as_of, include=["*"])

    full_outcomes = (py_full, mcp_full, rest_full, cli_full)
    expected_full_business = strip_run_metadata(py_full.payload)
    for outcome in full_outcomes:
        assert outcome.ok, outcome.payload
        assert find_bloat_keys(outcome.payload) == []
        assert not outcome.payload["run_metadata"].get("omitted_fields")
        _assert_unified_run_metadata(
            outcome.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
        )
        assert strip_run_metadata(outcome.payload) == expected_full_business

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
        tool_name, payload, as_of=e2e_as_of, fields=selected_fields
    )

    proj_outcomes = (py_proj, mcp_proj, rest_proj, cli_proj)
    expected_proj_business = strip_run_metadata(py_proj.payload)
    for outcome in proj_outcomes:
        assert outcome.ok, outcome.payload
        assert not outcome.payload["run_metadata"].get("omitted_fields")
        _assert_unified_run_metadata(
            outcome.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
        )
        assert strip_run_metadata(outcome.payload) == expected_proj_business
        assert set(strip_run_metadata(outcome.payload)) == {
            "four_pillars",
            "day_master",
        }
        assert set(outcome.payload["day_master"]) == {"strength"}
        assert_isomorphic_subset(outcome.payload, py_full.payload)


@pytest.mark.asyncio
async def test_three_surface_error_diagnostics_parity_invalid_include_and_conflict(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)

    mcp_inv = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["calendar_basi"],
        },
    )
    rest_inv = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), ("include", "calendar_basi")],
    )
    cli_inv = call_cli_tool(
        tool_name, payload, as_of=e2e_as_of, include=["calendar_basi"]
    )

    assert not mcp_inv.ok and mcp_inv.status_code == 422
    assert not rest_inv.ok and rest_inv.status_code == 422
    assert not cli_inv.ok and cli_inv.exit_code == 1

    inv_issues_list = [
        extract_error_issues(outcome.payload)
        for outcome in (mcp_inv, rest_inv, cli_inv)
    ]
    for outcome, issues in zip(
        (mcp_inv, rest_inv, cli_inv), inv_issues_list, strict=True
    ):
        assert outcome.payload.get("error_code") == "validation_error"
        assert issues and issues[0]["code"] == "unknown_projection_path"
        constraints = issues[0].get("constraints", {})
        assert constraints.get("available")
        assert "calendar_basis" in (constraints.get("suggestions") or [])

    assert inv_issues_list[0][0]["constraints"] == inv_issues_list[1][0]["constraints"]
    assert inv_issues_list[0][0]["constraints"] == inv_issues_list[2][0]["constraints"]

    mcp_conf = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            "include": ["calendar_basis"],
            "fields": ["bazi_birth.day_master"],
        },
    )
    rest_conf = call_rest_post(
        rest_client,
        rest_path,
        json_body=payload,
        params=[
            ("as_of", e2e_as_of),
            ("include", "calendar_basis"),
            ("fields", "bazi_birth.day_master"),
        ],
    )
    cli_conf = call_cli_tool(
        tool_name,
        payload,
        as_of=e2e_as_of,
        include=["calendar_basis"],
        fields=["bazi_birth.day_master"],
    )

    assert not mcp_conf.ok and mcp_conf.status_code == 422
    assert not rest_conf.ok and rest_conf.status_code == 422
    assert not cli_conf.ok and cli_conf.exit_code == 1

    conf_issues_list = [
        extract_error_issues(outcome.payload)
        for outcome in (mcp_conf, rest_conf, cli_conf)
    ]
    for outcome, issues in zip(
        (mcp_conf, rest_conf, cli_conf), conf_issues_list, strict=True
    ):
        assert outcome.payload.get("error_code") == "validation_error"
        assert issues and issues[0]["code"] == "conflicting_delivery_controls"
        assert issues[0].get("constraints", {}).get("available") == [
            "include",
            "fields",
        ]


# ---------------------------------------------------------------------------
# Pairwise 5: REST API Key Auth + `include` query param
# ---------------------------------------------------------------------------


def test_rest_api_key_auth_with_include_query_param(
    monkeypatch: pytest.MonkeyPatch,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    import fatebridge.api as api

    tool_name = "bazi_birth_chart"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    view_fields = list(
        all_tool_specs[tool_name]["evidence_views"]["calendar_basis"]["fields"]
    )

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(
            header_name="X-API-Key",
            api_keys={"e2e-client": "secret-e2e-key"},
        ),
    )

    try:
        with TestClient(api.app) as client:
            unauth = call_rest_post(
                client,
                rest_path,
                json_body=payload,
                params=[("as_of", e2e_as_of), ("include", "calendar_basis")],
            )
            assert not unauth.ok
            assert unauth.status_code == 401
            assert unauth.payload.get("error_code") == "authentication_required"

            wrong_key = call_rest_post(
                client,
                rest_path,
                json_body=payload,
                params=[("as_of", e2e_as_of), ("include", "calendar_basis")],
                headers={"X-API-Key": "invalid-key"},
            )
            assert not wrong_key.ok
            assert wrong_key.status_code == 401
            assert wrong_key.payload.get("error_code") == "authentication_required"

            authed = call_rest_post(
                client,
                rest_path,
                json_body=payload,
                params=[("as_of", e2e_as_of), ("include", "calendar_basis")],
                headers={"X-API-Key": "secret-e2e-key"},
            )
            assert authed.ok, authed.payload
            assert authed.status_code == 200
            for field_path in view_fields:
                assert has_dotted_path(authed.payload, field_path)
            omitted = authed.payload["run_metadata"].get("omitted_fields") or []
            for field_path in view_fields:
                assert field_path not in omitted
            _assert_unified_run_metadata(
                authed.payload["run_metadata"], tool_name=tool_name, as_of=e2e_as_of
            )
    finally:
        api._reset_runtime_state_for_tests()


@pytest.mark.asyncio
async def test_run_batch_random_coin_seed_isolation_and_mixed_delivery_isolation(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    """Unseeded coin-cast liuyao calls in one batch never share cached seeds; mixed delivery modes stay isolated."""
    liuyao_example = dict(all_tool_specs["liuyao"]["example_input"])
    unseeded_coin_args = {
        k: v
        for k, v in liuyao_example.items()
        if k not in ("seed", "coins", "lines", "gua_code")
    }
    unseeded_coin_args["method"] = "coin"

    batch_payload: dict[str, Any] = {
        "subjects": {"native": SHARED_SUBJECT},
        "context": SHARED_CONTEXT,
        "as_of": e2e_as_of,
        "calls": [
            {"id": "coin_1", "tool": "liuyao", "arguments": unseeded_coin_args},
            {"id": "coin_2", "tool": "liuyao", "arguments": unseeded_coin_args},
            {"id": "bazi_default", "tool": "bazi_birth_chart", "subject": "native"},
            {
                "id": "bazi_full",
                "tool": "bazi_birth_chart",
                "subject": "native",
                "include": ["*"],
            },
            {
                "id": "bazi_fields",
                "tool": "bazi_birth_chart",
                "subject": "native",
                "fields": ["bazi_birth.day_master"],
            },
            {
                "id": "bazi_bad",
                "tool": "bazi_birth_chart",
                "subject": "native",
                "include": ["nonexistent_view_isolation"],
            },
        ],
    }

    mcp_outcome = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_outcome = call_rest_post(rest_client, "/api/batch", json_body=batch_payload)

    for outcome in (mcp_outcome, rest_outcome):
        assert outcome.ok, outcome.payload
        assert outcome.payload["status"] == "partial_error"
        assert outcome.payload["succeeded"] == 5
        assert outcome.payload["failed"] == 1
        by_id = {item["id"]: item for item in outcome.payload["results"]}

        seed_1 = by_id["coin_1"]["result"]["run_metadata"]["replay"]["overrides"][
            "seed"
        ]
        seed_2 = by_id["coin_2"]["result"]["run_metadata"]["replay"]["overrides"][
            "seed"
        ]
        assert isinstance(seed_1, int) and isinstance(seed_2, int)
        assert seed_1 != seed_2

        default_res = by_id["bazi_default"]["result"]
        full_res = by_id["bazi_full"]["result"]
        fields_res = by_id["bazi_fields"]["result"]
        bad_item = by_id["bazi_bad"]

        assert default_res["run_metadata"].get("omitted_fields")
        assert not full_res["run_metadata"].get("omitted_fields")
        assert not fields_res["run_metadata"].get("omitted_fields")
        assert_isomorphic_subset(default_res, full_res)
        assert set(strip_run_metadata(fields_res)) == {"bazi_birth"}
        assert set(fields_res["bazi_birth"]) == {"day_master"}
        assert bad_item["ok"] is False
        assert bad_item["error"]["error_code"] == "validation_error"
