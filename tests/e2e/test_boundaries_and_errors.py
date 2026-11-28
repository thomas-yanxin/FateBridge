"""Opaque-box E2E tests for M4 (3-Pillar), M5 (Safety Boundaries), and M8 (ErrorEnvelope)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e.conftest import (
    augmented_inputs_for,
    call_cli,
    call_cli_tool,
    call_mcp_tool,
    call_python_run,
    call_rest,
    extract_error_issues,
    rest_path_for,
    strip_run_metadata,
)

DEFAULT_PAYLOAD_BUDGET_BYTES = 10_240


def _assert_python_parameter_error(
    tool_name: str,
    payload: dict[str, Any],
    *,
    as_of: str,
    include: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    with pytest.raises(ValueError) as exc_info:
        call_python_run(tool_name, payload, as_of=as_of, include=include, fields=fields)
    exc = exc_info.value
    assert type(exc).__name__ == "ParameterError"
    assert getattr(exc, "status_code", None) == 422
    issues = getattr(exc, "issues", None)
    assert isinstance(issues, list) and len(issues) > 0
    return [dict(item) for item in issues if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# M4: Three-Pillar Mode (`birth_time_unknown=True`)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    ("bazi_overview", "bazi_birth_chart", "bazi_timing", "liuren_yearly_timing"),
)
async def test_three_pillar_mode_all_4_tools_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    tool_name: str,
) -> None:
    base_birth: dict[str, Any] = {
        "name": "案例对象",
        "gender": "male",
        "birth_year": 2003,
        "birth_month": 2,
        "birth_day": 6,
        "birth_time_unknown": True,
        "birth_place": "杭州西湖区",
    }
    if tool_name == "bazi_timing":
        args = {
            **base_birth,
            "analysis_year": 2026,
            "analysis_month": 4,
            "analysis_day": 6,
            "analysis_hour": 9,
            "analysis_minute": 30,
        }
    elif tool_name == "liuren_yearly_timing":
        args = {
            **base_birth,
            "analysis_year": 2026,
            "analysis_month": 4,
            "analysis_day": 6,
            "analysis_hour": 9,
            "analysis_minute": 30,
            "analysis_place": "杭州西湖区",
        }
    else:
        args = dict(base_birth)

    rest_path = rest_path_for(tool_name, all_tool_specs)
    py_out = call_python_run(tool_name, args, as_of=e2e_as_of)
    mcp_out = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {"tool": tool_name, "arguments": args, "as_of": e2e_as_of},
    )
    rest_out = call_rest(
        rest_client, "POST", rest_path, json_body=args, params=[("as_of", e2e_as_of)]
    )
    cli_out = call_cli_tool(tool_name, args, as_of=e2e_as_of)
    batch_out = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "subjects": {
                "client": {
                    "name": "案例对象",
                    "gender": "male",
                    "birth_date": "2003-02-06",
                    "birth_time_unknown": True,
                    "birth_place": "杭州西湖区",
                }
            },
            "context": {
                "analysis_datetime": "2026-04-06T09:30:00+08:00",
                "place": "杭州西湖区",
            },
            "calls": [{"id": "c1", "tool": tool_name, "subject": "client"}],
            "as_of": e2e_as_of,
        },
    )

    for out in (py_out, mcp_out, rest_out, cli_out, batch_out):
        assert out.ok, f"{tool_name} failed: {out.payload}"

    batch_res = batch_out.payload["results"][0]["result"]
    expected_biz = strip_run_metadata(py_out.payload)
    for payload in (mcp_out.payload, rest_out.payload, cli_out.payload):
        assert strip_run_metadata(payload) == expected_biz

    if tool_name in {"bazi_overview", "bazi_timing"}:
        assert strip_run_metadata(batch_res) == expected_biz
    elif tool_name == "bazi_birth_chart":
        # Context analysis_datetime overrides as_of analysis_date; natal four_pillars match
        assert (
            batch_res["bazi_birth"]["four_pillars"]
            == expected_biz["bazi_birth"]["four_pillars"]
        )
    else:
        # Context analysis_datetime carries explicit +08:00 offset vs direct Asia/Shanghai
        assert batch_res["analysis_context"]["timezone"] == "+08:00"
        assert expected_biz["analysis_context"]["timezone"] == "Asia/Shanghai"
        assert batch_res["runyear"] == expected_biz["runyear"]
        assert (
            batch_res["liuren"]["four_lessons"]
            == expected_biz["liuren"]["four_lessons"]
        )
        assert (
            batch_res["liuren"]["three_transmissions"]
            == expected_biz["liuren"]["three_transmissions"]
        )

    for payload in (py_out.payload, batch_res):
        assert (
            len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            <= DEFAULT_PAYLOAD_BUDGET_BYTES
        )
        if tool_name == "bazi_birth_chart":
            assert payload["bazi_birth"]["four_pillars"]["hour"] is None
            assert payload["coverage"]["mode"] == "three_pillars_hour_unknown"
        elif tool_name in {"bazi_overview", "bazi_timing"}:
            assert payload["four_pillars"]["hour"] is None
            assert payload["coverage"]["mode"] == "three_pillars_hour_unknown"
        else:
            assert payload["coverage"]["mode"] == "date_only_hour_unknown"


def test_three_pillar_lichun_boundary_warning(e2e_as_of: str) -> None:
    out = call_python_run(
        "bazi_overview",
        {
            "gender": "male",
            "birth_year": 2003,
            "birth_month": 2,
            "birth_day": 4,
            "birth_time_unknown": True,
            "birth_place": "杭州西湖区",
        },
        as_of=e2e_as_of,
    )
    assert out.ok, out.payload
    warnings = out.payload["coverage"]["boundary_warnings"]
    assert any("立春" in w for w in warnings), warnings


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "tool_name", "bad_args", "expected_code"),
    (
        (
            "missing_birth_hour",
            "bazi_overview",
            {"birth_year": 2003, "birth_month": 2, "birth_day": 6, "gender": "male"},
            "missing_birth_hour",
        ),
        (
            "conflict_hour",
            "bazi_birth_chart",
            {
                "birth_year": 2003,
                "birth_month": 2,
                "birth_day": 6,
                "birth_hour": 10,
                "birth_time_unknown": True,
                "gender": "male",
            },
            "conflicting_unknown_birth_time",
        ),
        (
            "conflict_minute",
            "bazi_timing",
            {
                "birth_year": 2003,
                "birth_month": 2,
                "birth_day": 6,
                "birth_minute": 30,
                "birth_time_unknown": True,
                "gender": "male",
            },
            "conflicting_unknown_birth_time",
        ),
    ),
)
async def test_three_pillar_negative_cases_422_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    case_id: str,
    tool_name: str,
    bad_args: dict[str, Any],
    expected_code: str,
) -> None:
    rest_path = rest_path_for(tool_name, all_tool_specs)
    outcomes = [
        call_python_run(tool_name, bad_args, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": tool_name, "arguments": bad_args, "as_of": e2e_as_of},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path,
            json_body=bad_args,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool(tool_name, bad_args, as_of=e2e_as_of),
    ]
    for out in outcomes:
        assert not out.ok, f"{case_id} unexpectedly succeeded"
        assert out.status_code == 422
        assert out.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(out.payload)
        assert issues and issues[0]["code"] == expected_code


# ---------------------------------------------------------------------------
# M5: Hard Safety Boundaries (`consultation_restricted`)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "tool_name", "restricted_args", "raw_probe"),
    (
        (
            "horary_death",
            "horary_chart",
            {
                "question_year": 2026,
                "question_month": 10,
                "question_day": 19,
                "question_hour": 12,
                "longitude": 116.4,
                "latitude": 39.9,
                "category": "death",
            },
            "death",
        ),
        (
            "election_surgery",
            "evaluate_election_time",
            {
                "candidate_year": 2026,
                "candidate_month": 10,
                "candidate_day": 19,
                "candidate_hour": 12,
                "longitude": 116.4,
                "latitude": 39.9,
                "topic_id": "surgery",
            },
            "surgery",
        ),
        (
            "meihua_lifespan_zh",
            "meihua_time_cast",
            {
                "analysis_year": 2026,
                "analysis_month": 10,
                "analysis_day": 19,
                "analysis_hour": 12,
                "question": "我还能活多久",
            },
            "我还能活多久",
        ),
        (
            "meihua_lifespan_en",
            "meihua_time_cast",
            {
                "analysis_year": 2026,
                "analysis_month": 10,
                "analysis_day": 19,
                "analysis_hour": 12,
                "question": "How long will I live?",
            },
            "How long will I live?",
        ),
        (
            "meihua_zero_width_bypass",
            "meihua_time_cast",
            {
                "analysis_year": 2026,
                "analysis_month": 10,
                "analysis_day": 19,
                "analysis_hour": 12,
                "question": "我的死\u200b亡时间",
            },
            "死\u200b亡",
        ),
    ),
)
async def test_consultation_restricted_across_all_5_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    case_id: str,
    tool_name: str,
    restricted_args: dict[str, Any],
    raw_probe: str,
) -> None:
    rest_path = rest_path_for(tool_name, all_tool_specs)
    py_out = call_python_run(tool_name, restricted_args, as_of=e2e_as_of)
    mcp_out = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {"tool": tool_name, "arguments": restricted_args, "as_of": e2e_as_of},
    )
    rest_out = call_rest(
        rest_client,
        "POST",
        rest_path,
        json_body=restricted_args,
        params=[("as_of", e2e_as_of)],
    )
    cli_out = call_cli_tool(tool_name, restricted_args, as_of=e2e_as_of)
    batch_out = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [{"id": "c1", "tool": tool_name, "arguments": restricted_args}],
            "as_of": e2e_as_of,
        },
    )
    assert batch_out.ok and batch_out.payload["status"] == "error"
    batch_err = batch_out.payload["results"][0]["error"]

    for out in (py_out, mcp_out, rest_out, cli_out):
        assert not out.ok, f"{case_id} unexpectedly succeeded"
        assert out.status_code == 422

    for err_payload in (
        py_out.payload,
        mcp_out.payload,
        rest_out.payload,
        cli_out.payload,
        batch_err,
    ):
        assert err_payload.get("error_code") == "consultation_restricted"
        assert err_payload.get("retryable") is False
        assert "run_metadata" not in err_payload
        issues = extract_error_issues(err_payload)
        assert issues and issues[0]["code"] == "consultation_restricted"
        assert (
            issues[0].get("constraints", {}).get("policy")
            == "consultation_boundaries_v1"
        )
        assert raw_probe not in json.dumps(err_payload, ensure_ascii=False)


@pytest.mark.asyncio
async def test_consultation_neutral_control_not_blocked(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    args = {
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 19,
        "analysis_hour": 12,
        "question": "奇门死门是什么意思",
    }
    rest_path = rest_path_for("meihua_time_cast", all_tool_specs)
    for out in (
        call_python_run("meihua_time_cast", args, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": "meihua_time_cast", "arguments": args, "as_of": e2e_as_of},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path,
            json_body=args,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool("meihua_time_cast", args, as_of=e2e_as_of),
    ):
        assert out.ok, out.payload


# ---------------------------------------------------------------------------
# M8: Unified `ErrorEnvelope` & 4-Surface Parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("inc_val", "fields_val"),
    ((["*"], ["run_metadata"]), ([], []), ([], ["run_metadata"]), (["*"], [])),
)
async def test_conflicting_delivery_controls_422_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    inc_val: list[str],
    fields_val: list[str],
) -> None:
    tool_name = "gua_lookup"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    py_issues = _assert_python_parameter_error(
        tool_name, payload, as_of=e2e_as_of, include=inc_val, fields=fields_val
    )
    assert any(i["code"] == "conflicting_delivery_controls" for i in py_issues)

    mcp_out = await call_mcp_tool(
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
    batch_out = call_rest(
        rest_client,
        "POST",
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
    assert not mcp_out.ok and mcp_out.status_code == 422
    assert not batch_out.ok and batch_out.status_code == 422
    for out in (mcp_out, batch_out):
        issues = extract_error_issues(out.payload)
        assert any(i["code"] == "conflicting_delivery_controls" for i in issues)

    if inc_val and fields_val:
        rest_single = call_rest(
            rest_client,
            "POST",
            rest_path_for(tool_name, all_tool_specs),
            json_body=payload,
            params=[("as_of", e2e_as_of), ("include", "*"), ("fields", "run_metadata")],
        )
        cli_single = call_cli_tool(
            tool_name, payload, as_of=e2e_as_of, include=inc_val, fields=fields_val
        )
        assert not rest_single.ok and rest_single.status_code == 422
        assert not cli_single.ok and cli_single.exit_code == 1
        for out in (rest_single, cli_single):
            assert any(
                i["code"] == "conflicting_delivery_controls"
                for i in extract_error_issues(out.payload)
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("control", "bad_path", "expected_code", "expected_suggestion"),
    (
        ("include", "rootz", "unknown_projection_path", "roots"),
        ("fields", "day_mastur", "unknown_projection_path", "day_master"),
        ("include", "", "invalid_projection_path", None),
        ("fields", "a..b", "invalid_projection_path", None),
        ("fields", "favorable_elements_status.0", "non_object_projection_path", None),
    ),
)
async def test_invalid_projection_paths_diagnostics_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
    control: str,
    bad_path: str,
    expected_code: str,
    expected_suggestion: str | None,
) -> None:
    tool_name = "bazi_overview"
    payload = augmented_inputs_for(tool_name, all_tool_specs)
    rest_path = rest_path_for(tool_name, all_tool_specs)
    inc_arg = [bad_path] if control == "include" else None
    fld_arg = [bad_path] if control == "fields" else None

    py_issues = _assert_python_parameter_error(
        tool_name, payload, as_of=e2e_as_of, include=inc_arg, fields=fld_arg
    )
    mcp_out = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": payload,
            "as_of": e2e_as_of,
            control: [bad_path],
        },
    )
    rest_out = call_rest(
        rest_client,
        "POST",
        rest_path,
        json_body=payload,
        params=[("as_of", e2e_as_of), (control, bad_path)],
    )
    cli_out = call_cli_tool(
        tool_name, payload, as_of=e2e_as_of, include=inc_arg, fields=fld_arg
    )

    assert not mcp_out.ok and mcp_out.status_code == 422
    assert not rest_out.ok and rest_out.status_code == 422
    assert not cli_out.ok and cli_out.exit_code == 1 and cli_out.status_code == 422

    for issues in (
        py_issues,
        extract_error_issues(mcp_out.payload),
        extract_error_issues(rest_out.payload),
        extract_error_issues(cli_out.payload),
    ):
        assert issues and issues[0]["code"] == expected_code
        constraints = issues[0].get("constraints", {})
        if expected_code == "unknown_projection_path":
            assert constraints.get("available")
        if expected_suggestion is not None:
            assert expected_suggestion in (constraints.get("suggestions") or [])


@pytest.mark.asyncio
async def test_extra_forbidden_typo_and_synonym_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    # 1. Domain argument typo: birth_huor -> suggests birth_hour + allowed_fields
    tool_name = "bazi_birth_chart"
    bad_payload = {**augmented_inputs_for(tool_name, all_tool_specs), "birth_huor": 10}
    rest_path = rest_path_for(tool_name, all_tool_specs)

    mcp_out = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {"tool": tool_name, "arguments": bad_payload, "as_of": e2e_as_of},
    )
    rest_out = call_rest(
        rest_client,
        "POST",
        rest_path,
        json_body=bad_payload,
        params=[("as_of", e2e_as_of)],
    )
    cli_out = call_cli_tool(tool_name, bad_payload, as_of=e2e_as_of)

    assert not mcp_out.ok and mcp_out.status_code == 422
    assert not rest_out.ok and rest_out.status_code == 422
    assert not cli_out.ok and cli_out.exit_code == 1
    for out in (mcp_out, rest_out, cli_out):
        assert out.payload.get("error_code") == "validation_error"
        issue = extract_error_issues(out.payload)[0]
        assert issue["code"] == "extra_forbidden"
        assert issue["path"] == "birth_huor"
        assert "birth_hour" in issue["constraints"]["suggestions"]
        assert "birth_hour" in issue["constraints"]["allowed_fields"]

    # 2. BatchCall synonym (`params` -> `arguments`)
    syn_batch = {
        "as_of": e2e_as_of,
        "calls": [
            {"tool": "qimen", "params": {"qimen_options": {"ju_method": "zhirun"}}}
        ],
    }
    rest_syn = call_rest(rest_client, "POST", "/api/batch", json_body=syn_batch)
    mcp_syn = await call_mcp_tool(mcp_client, "run_batch", syn_batch)
    cli_syn = call_cli(
        ["batch", "--request-file", "-"],
        stdin_text=json.dumps(syn_batch, ensure_ascii=False),
    )
    assert not rest_syn.ok and rest_syn.status_code == 422
    assert not mcp_syn.ok and mcp_syn.status_code == 422
    assert not cli_syn.ok and cli_syn.exit_code == 1
    for out in (rest_syn, mcp_syn, cli_syn):
        issue = extract_error_issues(out.payload)[0]
        assert issue["code"] == "extra_forbidden"
        assert issue["constraints"]["suggestions"][0] == "arguments"
        assert "arguments" in issue["constraints"]["allowed_fields"]

    # 3. Python SDK parity for extra_forbidden constraints
    py_out = call_python_run(tool_name, bad_payload, as_of=e2e_as_of)
    assert not py_out.ok
    py_issue = extract_error_issues(py_out.payload)[0]
    assert py_issue["code"] == "extra_forbidden"
    constraints = py_issue.get("constraints") or {}
    assert "birth_hour" in constraints["suggestions"]
    assert "birth_hour" in constraints["allowed_fields"]


@pytest.mark.asyncio
async def test_unknown_tool_invalid_date_auth_401_and_cli_usage_error(
    mcp_client: Client,
    rest_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    import fatebridge.api as api

    # 1. Invalid calendar date (Feb 31 -> 422 invalid_calendar_date) across 4 surfaces
    feb31 = {
        "birth_year": 1990,
        "birth_month": 2,
        "birth_day": 31,
        "birth_hour": 10,
        "gender": "male",
    }
    rest_path = rest_path_for("bazi_birth_chart", all_tool_specs)
    for out in (
        call_python_run("bazi_birth_chart", feb31, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": "bazi_birth_chart", "arguments": feb31, "as_of": e2e_as_of},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path,
            json_body=feb31,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool("bazi_birth_chart", feb31, as_of=e2e_as_of),
    ):
        assert not out.ok and out.status_code == 422
        assert out.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(out.payload)
        assert issues and issues[0]["code"] == "invalid_calendar_date"

    # 2. unknown_tool 404 + suggestions on MCP run_calculation, MCP run_batch, REST /api/tools
    mcp_unk = await call_mcp_tool(
        mcp_client, "run_calculation", {"tool": "bazi_birth_chrat", "arguments": {}}
    )
    assert not mcp_unk.ok and mcp_unk.status_code == 404
    assert mcp_unk.payload.get("error_code") == "unknown_tool"
    assert (
        "bazi_birth_chart"
        in extract_error_issues(mcp_unk.payload)[0]["constraints"]["suggestions"]
    )

    batch_unk = await call_mcp_tool(
        mcp_client,
        "run_batch",
        {
            "calls": [{"id": "bad", "tool": "bazi_birth_chrat", "arguments": {}}],
            "as_of": e2e_as_of,
        },
    )
    assert batch_unk.ok and batch_unk.payload["status"] == "error"
    assert batch_unk.payload["succeeded"] == 0 and batch_unk.payload["failed"] == 1
    batch_unk_err = batch_unk.payload["results"][0]["error"]
    assert batch_unk_err.get("status_code") == 404
    assert batch_unk_err.get("error_code") == "unknown_tool"
    assert (
        "bazi_birth_chart"
        in extract_error_issues(batch_unk_err)[0]["constraints"]["suggestions"]
    )

    rest_unk = call_rest(
        rest_client, "GET", "/api/tools", params={"tool": "bazi_birth_chrat"}
    )
    assert not rest_unk.ok and rest_unk.status_code == 404
    rest_unk_issues = extract_error_issues(rest_unk.payload)
    assert rest_unk_issues and rest_unk_issues[0]["code"] == "unknown_tool"
    assert "bazi_birth_chart" in rest_unk_issues[0]["constraints"]["suggestions"]

    # 3. CLI usage_error (exit 2) for legacy --detail flag and missing batch --request-file
    cli_detail = call_cli_tool(
        "gua_lookup",
        augmented_inputs_for("gua_lookup", all_tool_specs),
        as_of=e2e_as_of,
        extra_flags=["--detail", "compact"],
    )
    cli_no_file = call_cli(["batch"])
    for out in (cli_detail, cli_no_file):
        assert not out.ok and out.exit_code == 2
        assert out.payload.get("error_code") == "usage_error"

    # 4. REST 401 authentication_required with WWW-Authenticate: APIKey
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={"e2e": "secret-k"}),
    )
    try:
        with TestClient(api.app) as auth_client:
            resp = auth_client.post(
                rest_path_for("gua_lookup", all_tool_specs),
                json=augmented_inputs_for("gua_lookup", all_tool_specs),
            )
            assert resp.status_code == 401
            assert resp.headers.get("WWW-Authenticate") == "APIKey"
            assert resp.json().get("error_code") == "authentication_required"
    finally:
        api._reset_runtime_state_for_tests()
