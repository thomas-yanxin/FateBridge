"""Verify Plan A M1 contracts: default_omit, include, mutex, omitted_fields, and all 5 surfaces."""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge
import fatebridge.api as api
import fatebridge.cli as cli
from fatebridge.application.batch import BatchCall, BatchRequest, execute_batch
from fatebridge.application.description import describe_brief_spec, describe_spec
from fatebridge.application.examples import evidence_views, example_input
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError

SPECS = {spec.name: spec for spec in CATALOG}


def _dummy_spec(
    *,
    name: str = "dummy_tool",
    default_omit: tuple[str, ...] = (),
    evidence_views_map: dict[str, dict[str, object]] | None = None,
) -> ToolSpec:
    from pydantic import BaseModel

    class DummyReq(BaseModel):
        pass

    return ToolSpec(
        name=name,
        bind=lambda _req: (lambda: {}, (), {}),
        request_model=DummyReq,
        summary="dummy",
        operation_label_zh="测试工具",
        family="test",
        default_omit=default_omit,
        evidence_views_builder=(
            (lambda _v: evidence_views_map) if evidence_views_map is not None else None
        ),
    )


def test_default_omit_exact_nested_wildcard_and_omitted_fields() -> None:
    spec = _dummy_spec(
        default_omit=(
            "calendar_context",
            "absent_optional",
            "nested.heavy",
            "scopes.*.palace_map",
            "dials.*.three_factor_contacts",
        ),
        evidence_views_map={
            "scope_maps": {"fields": ["scopes.*.palace_map", "optional_missing_field"]},
            "nested_view": {"fields": ["nested.heavy"]},
        },
    )
    payload = {
        "summary": "ok",
        "calendar_context": {"birth_time_input": "10:30", "extra": 1},
        "nested": {"core": 42, "heavy": {"big": [1, 2, 3]}},
        "scopes": [
            {"name": "decadal", "palace_map": {"子": "命"}},
            {"name": "yearly", "palace_map": {"丑": "财"}},
        ],
        "dials": {
            "90": {"three_factor_contacts": ["A"], "keep": 1},
            "45": {"three_factor_contacts": ["B"], "keep": 2},
        },
        "run_metadata": {"run_id": "r1", "duration_ms": 1.2, "replay": {"as_of": "Z"}},
    }
    snapshot = copy.deepcopy(payload)

    # 1. Default omits present paths only (never absent_optional) and does not mutate input.
    default_out = deliver_response(payload, spec=spec)
    assert payload == snapshot
    assert "calendar_context" not in default_out
    assert default_out["nested"] == {"core": 42}
    assert default_out["scopes"] == [{"name": "decadal"}, {"name": "yearly"}]
    assert default_out["dials"] == {"90": {"keep": 1}, "45": {"keep": 2}}
    assert default_out["run_metadata"]["omitted_fields"] == [
        "calendar_context",
        "nested.heavy",
        "scopes.*.palace_map",
        "dials.*.three_factor_contacts",
    ]

    # 2. include=["*"] returns exact lossless canonical payload with no omitted_fields.
    full_out = deliver_response(payload, spec=spec, include=["*"])
    assert full_out == payload
    assert "omitted_fields" not in full_out["run_metadata"]

    # 3. Empty include=[] behaves like default; failed=True and fields=[...] omit omitted_fields.
    assert deliver_response(payload, spec=spec, include=[]) == default_out
    assert deliver_response(payload, spec=spec, failed=True) == payload
    fields_out = deliver_response(payload, spec=spec, fields=["summary"])
    assert set(fields_out) == {"summary", "run_metadata"}
    assert "omitted_fields" not in fields_out["run_metadata"]

    # 4. Parent include un-omits nested default_omit.
    parent_inc = deliver_response(payload, spec=spec, include=["nested"])
    assert parent_inc["nested"] == payload["nested"]
    assert "nested.heavy" not in parent_inc["run_metadata"]["omitted_fields"]

    # 5. Descendant include keeps only requested child inside omitted parent.
    desc_inc = deliver_response(
        payload, spec=spec, include=["calendar_context.birth_time_input"]
    )
    assert desc_inc["calendar_context"] == {"birth_time_input": "10:30"}
    assert "calendar_context" in desc_inc["run_metadata"]["omitted_fields"]

    # 6. Concrete wildcard specialization keeps target dial and still omits sibling dial.
    dial_inc = deliver_response(
        payload, spec=spec, include=["dials.90.three_factor_contacts"]
    )
    assert dial_inc["dials"]["90"]["three_factor_contacts"] == ["A"]
    assert "three_factor_contacts" not in dial_inc["dials"]["45"]
    assert "dials.*.three_factor_contacts" in dial_inc["run_metadata"]["omitted_fields"]

    # 7. Evidence view include un-omits matching paths and tolerates absent optional fields.
    view_inc = deliver_response(payload, spec=spec, include=["scope_maps"])
    assert view_inc["scopes"] == payload["scopes"]
    assert "scopes.*.palace_map" not in view_inc["run_metadata"]["omitted_fields"]

    # 8. Un-omitting everything omits omitted_fields completely from run_metadata.
    all_explicit = deliver_response(
        payload,
        spec=spec,
        include=[
            "calendar_context",
            "nested_view",
            "scope_maps",
            "dials.*.three_factor_contacts",
        ],
    )
    assert "omitted_fields" not in all_explicit["run_metadata"]


def test_default_omit_no_match_leaves_omitted_fields_absent() -> None:
    spec = _dummy_spec(default_omit=("missing_key", "empty_list.*.sub"))
    payload = {
        "summary": "ok",
        "empty_list": [],
        "run_metadata": {"run_id": "r1"},
    }
    out = deliver_response(payload, spec=spec)
    assert out == payload
    assert "omitted_fields" not in out["run_metadata"]


def test_include_validation_diagnostics_and_edge_cases() -> None:
    spec = _dummy_spec(
        default_omit=("declared_empty.*.sub",),
        evidence_views_map={"core_view": {"fields": ["summary"]}},
    )
    payload = {
        "summary": "ok",
        "declared_empty": [],
        "undeclared_empty": [],
        "dials": {"90": {"three_factor_contacts": [1]}},
        "run_metadata": {"run_id": "r1"},
    }

    # ["*", "typo"] must NOT short-circuit validation on "*".
    with pytest.raises(ParameterError) as exc_info:
        deliver_response(payload, spec=spec, include=["*", "sumary"])
    issue = exc_info.value.issues[0]
    assert issue["code"] == "unknown_projection_path"
    assert "summary" in issue["constraints"]["suggestions"]
    assert "core_view" in issue["constraints"]["available"]

    # Scalar traversal fails with non_object_projection_path.
    with pytest.raises(ParameterError) as scalar_err:
        deliver_response(payload, spec=spec, include=["summary.sub"])
    assert scalar_err.value.issues[0]["code"] == "non_object_projection_path"

    # Empty/whitespace segment fails with invalid_projection_path.
    with pytest.raises(ParameterError) as invalid_err:
        deliver_response(payload, spec=spec, include=["dials..90"])
    assert invalid_err.value.issues[0]["code"] == "invalid_projection_path"

    # Empty wildcard container accepted ONLY if declared in spec.default_omit.
    ok_empty = deliver_response(payload, spec=spec, include=["declared_empty.*.sub"])
    assert ok_empty["declared_empty"] == []

    with pytest.raises(ParameterError) as bad_empty:
        deliver_response(payload, spec=spec, include=["undeclared_empty.*.sub"])
    assert bad_empty.value.issues[0]["code"] == "unknown_projection_path"

    # Wildcard nested typo reports merged available + suggestions.
    with pytest.raises(ParameterError) as bad_wild:
        deliver_response(payload, spec=spec, include=["dials.*.three_factor_contactz"])
    wild_issue = bad_wild.value.issues[0]
    assert wild_issue["code"] == "unknown_projection_path"
    assert "three_factor_contacts" in wild_issue["constraints"]["available"]
    assert "three_factor_contacts" in wild_issue["constraints"]["suggestions"]


def test_human_design_root_available_and_colliding_view_names() -> None:
    hd_spec = SPECS["human_design"]
    ex = example_input(hd_spec)
    assert ex is not None
    raw = fatebridge.run("human_design", ex)
    views = evidence_views(hd_spec) or {}
    # human_design has 48 unique root keys + evidence_views; available must not truncate at 30.
    with pytest.raises(ParameterError) as exc_info:
        deliver_response(raw, spec=hd_spec, include=["nonexistent_key_xyz"])
    available = exc_info.value.issues[0]["constraints"]["available"]
    expected_union = set(raw.keys()) | set(views.keys())
    assert len(expected_union) > 30
    assert set(available) == expected_union

    # Colliding evidence view name ("variables" is both root key and view name) succeeds.
    omitted_hd = replace(hd_spec, default_omit=("variables",))
    with_view = deliver_response(raw, spec=omitted_hd, include=["variables"])
    assert "variables" in with_view


def test_include_and_fields_mutex_across_all_five_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = {"queries": ["乾"]}

    # 1. Python SDK
    with pytest.raises(ParameterError) as py_err:
        fatebridge.run("gua_lookup", args, include=["*"], fields=["results"])
    assert py_err.value.status_code == 422
    assert py_err.value.issues[0]["code"] == "conflicting_delivery_controls"
    assert py_err.value.issues[0]["constraints"]["available"] == ["include", "fields"]

    # 2. REST POST
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client_http = TestClient(api.app)
    rest_res = client_http.post(
        "/api/divination/gua",
        json=args,
        params={"include": "*", "fields": "results"},
    )
    assert rest_res.status_code == 422
    assert rest_res.json()["issues"][0]["code"] == "conflicting_delivery_controls"

    # 3. MCP run_calculation
    async def mcp_mutex():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "run_calculation",
                {
                    "tool": "gua_lookup",
                    "arguments": args,
                    "include": ["*"],
                    "fields": ["results"],
                },
                raise_on_error=False,
            )

    mcp_res = asyncio.run(mcp_mutex())
    assert mcp_res.is_error
    assert (
        mcp_res.structured_content["issues"][0]["code"]
        == "conflicting_delivery_controls"
    )

    # 4. CLI
    capsys.readouterr()
    code = cli.run(
        ["gua_lookup", "--queries", "乾", "--include", "*", "--fields", "results"]
    )
    assert code == 1
    cli_err = json.loads(capsys.readouterr().out)
    assert cli_err["issues"][0]["code"] == "conflicting_delivery_controls"

    # 5. Batch (Pydantic, REST /api/batch, MCP run_batch, CLI batch)
    batch_payload = {
        "calls": [
            {
                "tool": "gua_lookup",
                "arguments": args,
                "include": ["*"],
                "fields": ["results"],
            }
        ]
    }
    with pytest.raises(ValidationError):
        BatchRequest.model_validate(batch_payload)

    rest_batch = client_http.post("/api/batch", json=batch_payload)
    assert rest_batch.status_code == 422
    assert rest_batch.json()["issues"][0]["code"] == "conflicting_delivery_controls"

    async def mcp_batch_mutex():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "run_batch", batch_payload, raise_on_error=False
            )

    mcp_batch = asyncio.run(mcp_batch_mutex())
    assert mcp_batch.is_error
    assert (
        mcp_batch.structured_content["issues"][0]["code"]
        == "conflicting_delivery_controls"
    )

    batch_file = tmp_path / "batch_mutex.json"
    batch_file.write_text(json.dumps(batch_payload), encoding="utf-8")
    capsys.readouterr()
    assert cli.run(["batch", "--request-file", str(batch_file)]) == 1
    cli_batch = json.loads(capsys.readouterr().out)
    assert cli_batch["issues"][0]["code"] == "conflicting_delivery_controls"


def test_invalid_include_errors_with_suggestions_across_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = {"queries": ["乾"]}

    # Python API
    with pytest.raises(ParameterError) as py_err:
        fatebridge.run("gua_lookup", args, include=["resultz"])
    assert py_err.value.issues[0]["code"] == "unknown_projection_path"
    assert "results" in py_err.value.issues[0]["constraints"]["suggestions"]

    # REST
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest_res = TestClient(api.app).post(
        "/api/divination/gua",
        json=args,
        params={"include": "resultz"},
    )
    assert rest_res.status_code == 422
    rest_issue = rest_res.json()["issues"][0]
    assert rest_issue["code"] == "unknown_projection_path"
    assert "results" in rest_issue["constraints"]["suggestions"]

    # MCP
    async def mcp_bad_inc():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "run_calculation",
                {"tool": "gua_lookup", "arguments": args, "include": ["resultz"]},
                raise_on_error=False,
            )

    mcp_res = asyncio.run(mcp_bad_inc())
    assert mcp_res.is_error
    mcp_issue = mcp_res.structured_content["issues"][0]
    assert mcp_issue["code"] == "unknown_projection_path"
    assert "results" in mcp_issue["constraints"]["suggestions"]

    # CLI
    capsys.readouterr()
    assert cli.run(["gua_lookup", "--queries", "乾", "--include", "resultz"]) == 1
    cli_res = json.loads(capsys.readouterr().out)
    cli_issue = cli_res["issues"][0]
    assert cli_issue["code"] == "unknown_projection_path"
    assert "results" in cli_issue["constraints"]["suggestions"]


def test_calculation_detail_rejected_and_discovery_detail_preserved(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import inspect

    # Python run() removes detail from signature and rejects detail as extra_forbidden;
    # discover() preserves brief|summary|full.
    run_params = inspect.signature(fatebridge.run).parameters
    assert "detail" not in run_params
    assert {"include", "fields", "as_of"} <= set(run_params)
    py_err = fatebridge.run("gua_lookup", {"queries": ["乾"]}, detail="audit")
    assert py_err["error_code"] == "validation_error"
    assert py_err["status_code"] == 422
    assert py_err["issues"][0]["path"] == "detail"
    assert py_err["issues"][0]["code"] == "extra_forbidden"
    assert fatebridge.discover(tool="gua_lookup", detail="brief")["detail"] == "brief"

    # CLI calculation rejects --detail with exit 2 usage_error; discover preserves --detail.
    capsys.readouterr()
    assert cli.run(["gua_lookup", "--queries", "乾", "--detail", "audit"]) == 2
    assert json.loads(capsys.readouterr().out)["error_code"] == "usage_error"
    assert cli.run(["discover", "gua_lookup", "--detail", "brief"]) == 0
    assert json.loads(capsys.readouterr().out)["detail"] == "brief"

    # Batch models reject detail.
    with pytest.raises(ValidationError):
        BatchRequest.model_validate(
            {"detail": "compact", "calls": [{"tool": "gua_lookup"}]}
        )
    with pytest.raises(ValidationError):
        BatchCall.model_validate({"tool": "gua_lookup", "detail": "audit"})

    # REST OpenAPI exposes include/fields/as_of without detail; GET /api/tools preserves detail.
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client_http = TestClient(api.app)
    openapi = client_http.get("/openapi.json").json()
    gua_params = {
        param["name"]
        for param in openapi["paths"]["/api/divination/gua"]["post"]["parameters"]
    }
    assert gua_params == {"include", "fields", "as_of"}
    assert (
        client_http.get(
            "/api/tools", params={"tool": "gua_lookup", "detail": "brief"}
        ).status_code
        == 200
    )

    # MCP rejects detail on run_calculation and run_batch, preserves discover_tools detail.
    async def mcp_checks():
        async with Client(create_mcp_app()) as client:
            bad_calc = await client.call_tool(
                "run_calculation",
                {
                    "tool": "gua_lookup",
                    "arguments": {"queries": ["乾"]},
                    "detail": "compact",
                },
                raise_on_error=False,
            )
            bad_batch = await client.call_tool(
                "run_batch",
                {"calls": [{"tool": "gua_lookup"}], "detail": "compact"},
                raise_on_error=False,
            )
            disc = await client.call_tool(
                "discover_tools", {"tool": "gua_lookup", "detail": "brief"}
            )
            return bad_calc, bad_batch, disc

    bad_calc, bad_batch, disc = asyncio.run(mcp_checks())
    assert bad_calc.is_error
    assert bad_batch.is_error
    assert not disc.is_error and disc.structured_content["detail"] == "brief"


def test_batch_raw_cache_reused_across_different_include_and_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.application.batch as batch_mod

    exec_calls = 0
    orig_exec = batch_mod.execute_with_receipt

    def spy_exec(spec, request, *, options=None):
        nonlocal exec_calls
        exec_calls += 1
        return orig_exec(spec, request, options=options)

    monkeypatch.setattr(batch_mod, "execute_with_receipt", spy_exec)
    base_spec = SPECS["gua_lookup"]
    omitted_spec = replace(base_spec, default_omit=("results",))

    req = BatchRequest.model_validate(
        {
            "as_of": "2026-10-12T12:00:00+08:00",
            "calls": [
                {
                    "id": "default",
                    "tool": "gua_lookup",
                    "arguments": {"queries": ["乾"]},
                },
                {
                    "id": "full",
                    "tool": "gua_lookup",
                    "arguments": {"queries": ["乾"]},
                    "include": ["*"],
                },
                {
                    "id": "proj",
                    "tool": "gua_lookup",
                    "arguments": {"queries": ["乾"]},
                    "fields": ["analysis_type"],
                },
            ],
        }
    )
    res = execute_batch({"gua_lookup": omitted_spec}, req)
    assert res["status"] == "ok" and res["succeeded"] == 3
    assert exec_calls == 1
    by_id = {item["id"]: item["result"] for item in res["results"]}
    assert "results" not in by_id["default"]
    assert by_id["default"]["run_metadata"]["omitted_fields"] == ["results"]
    assert "results" in by_id["full"]
    assert "omitted_fields" not in by_id["full"]["run_metadata"]
    assert set(by_id["proj"]) == {"analysis_type", "run_metadata"}
    assert "omitted_fields" not in by_id["proj"]["run_metadata"]


def test_description_surfaces_default_omit_without_compact_fields() -> None:
    omitted_spec = replace(SPECS["gua_lookup"], default_omit=("results",))
    full_desc = describe_spec(omitted_spec)
    brief_desc = describe_brief_spec(omitted_spec)
    assert full_desc["default_omit"] == ["results"]
    assert brief_desc["default_omit"] == ["results"]
    assert "compact_fields" not in full_desc
    assert "compact_fields" not in brief_desc

    plain_desc = describe_spec(SPECS["gua_lookup"])
    assert "default_omit" not in plain_desc
    assert "compact_fields" not in plain_desc
