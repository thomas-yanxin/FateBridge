"""Native-client projection, discovery and profile contracts."""

import asyncio
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

try:
    from mcp.shared.exceptions import McpError
except ImportError:  # MCP SDK 2.x uses the capitalized spelling.
    from mcp.shared.exceptions import MCPError as McpError

import fatebridge.api as api
import fatebridge.application.discovery as discovery
import fatebridge.mcp_server as mcp
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from tests.fixtures.surface_payloads import REST_POST_CASES

BIRTH = {
    **REST_POST_CASES["/api/cn/bazi/birth"](),
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}


@pytest.fixture
def rest(monkeypatch):
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(
            header_name="X-API-Key",
            api_keys={},
        ),
    )
    return TestClient(api.app)


def command(name, inputs, flags):
    args = [sys.executable, "-m", "fatebridge.cli", name]
    for key, value in inputs.items():
        args += [
            "--" + key.replace("_", "-"),
            str(value).lower() if isinstance(value, bool) else str(value),
        ]
    result = subprocess.run(args + flags, capture_output=True, text=True, timeout=30)
    return result.returncode, json.loads(result.stdout)


def protocol_call(inputs):
    async def call():
        async with Client(mcp.app) as client:
            result = await client.call_tool("bazi_birth", inputs, raise_on_error=False)
            assert json.loads(result.content[0].text) == result.structured_content
            return result

    return asyncio.run(call())


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    "path,expected",
    [
        ("bazi_birth.day_mastr", "unknown_projection_path"),
        ("no_such_root", "unknown_projection_path"),
        ("snapshot_text.foo", "non_object_projection_path"),
        ("bazi_birth.favorable_elements.0", "non_object_projection_path"),
        ("bazi_birth..day_master", "invalid_projection_path"),
        ("run_metadata.bad", "unknown_projection_path"),
        ("", "invalid_projection_path"),
    ],
)
def test_projection_failures_are_visible_and_match_all_transports(
    rest, strict, path, expected
):
    fields = ["bazi_birth.day_master", path]
    http = rest.post(
        "/api/cn/bazi/birth",
        json=BIRTH,
        params={"fields": fields, "strict_fields": str(strict).lower()},
    )
    protocol = protocol_call({**BIRTH, "fields": fields, "strict_fields": strict})
    code, output = command(
        "bazi_birth",
        BIRTH,
        ["--strict-fields", str(strict).lower(), "--fields", *fields],
    )
    assert http.status_code == (422 if strict else 200)
    assert protocol.is_error is strict and code == int(strict)
    payloads = [http.json(), protocol.structured_content, output]
    issues_key = "issues" if strict else "projection_warnings"
    for payload in payloads:
        assert payload[issues_key] == [{"path": path, "code": expected}]
        if strict:
            assert (
                payload["error_code"] == "validation_error" and not payload["retryable"]
            )
            assert "bazi_birth" not in payload
        else:
            assert payload["bazi_birth"]["day_master"]
            model = next(s.output_model for s in CATALOG if s.key == "bazi_birth")
            Draft202012Validator(model.model_json_schema()).validate(payload)
    if not strict:
        scrubbed = [
            {k: v for k, v in p.items() if k != "run_metadata"} for p in payloads
        ]
        assert scrubbed[0] == scrubbed[1] == scrubbed[2]


@pytest.mark.parametrize("strict", [False, True])
def test_valid_projection_has_no_added_warning_and_preserves_metadata(rest, strict):
    fields = ["bazi_birth.day_master.stem", "run_metadata.tool_name"]
    http = rest.post(
        "/api/cn/bazi/birth",
        json=BIRTH,
        params={"fields": fields, "strict_fields": str(strict).lower()},
    )
    protocol = protocol_call({**BIRTH, "fields": fields, "strict_fields": strict})
    code, output = command(
        "bazi_birth",
        BIRTH,
        ["--strict-fields", str(strict).lower(), "--fields", *fields],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    payloads = [http.json(), protocol.structured_content, output]
    for payload in payloads:
        assert set(payload) == {"bazi_birth", "run_metadata"}
        assert set(payload["run_metadata"]) >= {
            "run_id",
            "trace_id",
            "tool_name",
            "generated_at",
            "engine",
            "engine_is_approximate",
        }
    assert (
        payloads[0]["bazi_birth"]
        == payloads[1]["bazi_birth"]
        == payloads[2]["bazi_birth"]
    )


def test_strict_projection_does_not_hide_a_domain_failure(rest):
    inputs = {
        **BIRTH,
        "birth_place": "未提供",
        "birth_longitude": None,
        "use_true_solar_time": True,
    }
    # None is represented by omission for the CLI.
    http = rest.post(
        "/api/cn/bazi/birth",
        json=inputs,
        params={"fields": "misspelled", "strict_fields": "true"},
    )
    protocol = protocol_call(
        {**inputs, "fields": ["misspelled"], "strict_fields": True}
    )
    code, output = command(
        "bazi_birth",
        {k: v for k, v in inputs.items() if v is not None},
        ["--fields", "misspelled", "--strict-fields"],
    )
    assert http.status_code == 400 and protocol.is_error and code == 1
    for payload in [http.json(), protocol.structured_content, output]:
        assert payload["error_code"] == "validation_error"
        assert "projection_warnings" not in payload and "issues" not in payload


def test_runtime_projection_accepts_extensions_nulls_and_whole_lists():
    payload = {
        "extension": {
            "unknown_to_static_schema": 0,
            "empty": {},
            "null": None,
            "items": [1, 2],
        }
    }
    assert (
        project_fields(
            payload,
            [
                "extension.unknown_to_static_schema",
                "extension.empty",
                "extension.null",
                "extension.items",
            ],
            strict_fields=True,
        )
        == payload
    )
    assert project_fields(payload, iter([]), strict_fields=True) is payload
    with pytest.raises(ParameterError) as error:
        project_fields(
            payload,
            ["extension", "extension.typo", "extension.typo"],
            strict_fields=True,
        )
    assert error.value.issues == [
        {"path": "extension.typo", "code": "unknown_projection_path"}
    ]


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"family": "bazi"},
        {"family": "bazi,astro", "q": "命盘", "surface": "mcp"},
        {"tool": "bazi_birth", "detail": "full"},
        {"q": "no_matches_expected"},
    ],
)
def test_progressive_rest_and_cli_discovery_are_identical(rest, capsys, filters):
    params = {"detail": "summary", **filters}
    http = rest.get("/api/tools", params=params)
    args = ["discover"]
    for key, value in params.items():
        args += ["--" + ("query" if key == "q" else key), value]
    assert run(args) == 0 and http.status_code == 200
    assert json.loads(capsys.readouterr().out) == http.json()
    assert http.json()["matched_count"] == len(http.json()["tools"])
    if params["detail"] == "summary":
        assert all(
            "input_schema" not in tool
            and "parameters" not in tool
            and "output_schema" not in tool
            for tool in http.json()["tools"]
        )


def test_default_discovery_and_text_list_remain_compatible(rest, capsys):
    manifest = rest.get("/api/tools").json()
    assert manifest["detail"] == "full" and len(manifest["tools"]) == len(CATALOG)
    assert all(
        "parameters" in t and "input_schema" in t and "output_schema" in t
        for t in manifest["tools"]
    )
    assert run([]) == 0
    before = capsys.readouterr().out
    assert run(["list"]) == 0 and capsys.readouterr().out == before
    assert run(["list", "--json"]) == 0
    assert (
        json.loads(capsys.readouterr().out)
        == rest.get("/api/tools", params={"detail": "summary"}).json()
    )


def test_summary_discovery_does_not_build_schemas(monkeypatch):
    monkeypatch.setattr(
        discovery,
        "describe_spec",
        lambda _: pytest.fail("summary generated full schema"),
    )
    summary = discovery.discover_specs(CATALOG, detail="summary")
    assert len(summary["tools"]) == len(CATALOG)


@pytest.mark.parametrize(
    "filters", [{"family": "astrp"}, {"family": "bazi,,astro"}, {"tool": "bazi_bith"}]
)
def test_discovery_typos_fail_with_matching_rest_cli_correction_hints(
    rest, capsys, filters
):
    http = rest.get("/api/tools", params=filters)
    args = ["discover"]
    for key, value in filters.items():
        args += ["--" + key, value]
    assert run(args) == 1 and http.status_code == 422
    output = json.loads(capsys.readouterr().out)
    assert http.json()["issues"] == output["issues"]
    assert http.json()["error_code"] == output["error_code"] == "validation_error"


def test_mcp_resources_and_annotations_match_rest_and_cli(rest, capsys):
    async def check():
        async with Client(mcp.app) as client:
            resources = await client.list_resources()
            assert any(
                str(resource.uri) == "fatebridge://catalog/summary"
                for resource in resources
            )
            summary = json.loads(
                (await client.read_resource("fatebridge://catalog/summary"))[0].text
            )
            family = json.loads(
                (await client.read_resource("fatebridge://families/bazi"))[0].text
            )
            full = json.loads(
                (await client.read_resource("fatebridge://tools/bazi_birth"))[0].text
            )
            tools = await client.list_tools()
            return summary, family, full, tools

    summary, family, full, tools = asyncio.run(check())
    assert (
        summary
        == rest.get("/api/tools", params={"detail": "summary", "surface": "mcp"}).json()
    )
    assert (
        family
        == rest.get(
            "/api/tools",
            params={"detail": "summary", "surface": "mcp", "family": "bazi"},
        ).json()
    )
    assert (
        full
        == rest.get(
            "/api/tools",
            params={"detail": "full", "surface": "mcp", "tool": "bazi_birth"},
        ).json()
    )
    assert run(["discover", "--surface", "mcp"]) == 0
    assert json.loads(capsys.readouterr().out) == summary
    records = {t["tool"]: t for t in summary["tools"]}
    for tool in tools:
        annotations = tool.annotations.model_dump(by_alias=True, exclude_none=True)
        assert annotations == records[tool.name]["annotations"]
        assert annotations == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }


def test_mcp_family_profile_filters_real_tools_and_resource_contracts(rest):
    async def check():
        async with Client(mcp.create_mcp_app("bazi,knowledge")) as client:
            tools = await client.list_tools()
            summary = json.loads(
                (await client.read_resource("fatebridge://catalog/summary"))[0].text
            )
            result = await client.call_tool("bazi_birth", BIRTH)
            assert not result.is_error
            with pytest.raises(McpError):
                await client.read_resource("fatebridge://tools/astro_chart")
            return tools, summary

    tools, summary = asyncio.run(check())
    expected = rest.get(
        "/api/tools",
        params={"family": "bazi,knowledge", "surface": "mcp", "detail": "summary"},
    ).json()
    assert summary == expected
    assert {tool.name for tool in tools} == {tool["tool"] for tool in summary["tools"]}
    with pytest.raises(ParameterError):
        mcp.create_mcp_app("astrp")


def test_host_environment_profile_and_invalid_startup_are_enforced():
    script = (
        "import asyncio,json; import fatebridge.mcp_server as m; "
        "print(json.dumps([tool.name for tool in asyncio.run(m.app.list_tools(run_middleware=False))]))"
    )
    env = {**os.environ, "FATEBRIDGE_MCP_FAMILIES": "bazi"}
    process = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 0
    assert set(json.loads(process.stdout)) == {
        spec.tool_name for spec in CATALOG if spec.mcp_name and spec.family == "bazi"
    }
    env["FATEBRIDGE_MCP_FAMILIES"] = "astrp"
    rejected = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert rejected.returncode != 0 and "工具分类无效" in rejected.stderr
    assert not rejected.stdout


def test_execution_annotation_overrides_are_shared_and_not_hardcoded():
    from dataclasses import replace

    from fastmcp import FastMCP

    from fatebridge.application.description import describe_spec
    from fatebridge.application.tool_spec import ExecutionHints
    from fatebridge.transports.mcp import register_mcp

    original = next(spec for spec in CATALOG if spec.key == "bazi_birth")
    synthetic = replace(
        original,
        execution_hints=ExecutionHints(
            read_only=False, destructive=True, idempotent=False, open_world=True
        ),
    )
    server = FastMCP("hint regression")
    register_mcp(
        server,
        [synthetic],
        render_response=mcp._render_protocol_response,
        render_error=mcp._render_protocol_error,
    )

    async def check():
        async with Client(server) as client:
            return (await client.list_tools())[0].annotations.model_dump(
                by_alias=True, exclude_none=True
            )

    assert (
        asyncio.run(check())
        == discovery.summarize_spec(synthetic)["annotations"]
        == describe_spec(synthetic)["annotations"]
    )
