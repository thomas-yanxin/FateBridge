"""Unknown civil timezone errors and known-place inputs on actual interfaces."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.test_guolao_timezone_source import CASE

ROOT = Path(__file__).parents[1]
AS_OF = "2026-10-22T12:00:00+08:00"


def api_ready(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )


@pytest.mark.parametrize("tool", ["astro_guolao_chart", "astro_chart"])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("place", [None, "通州区"])
def test_unresolved_missing_timezone_returns_consistent_actionable_error(
    monkeypatch, capsys, tool, solar, place
):
    api_ready(monkeypatch)
    spec = next(s for s in CATALOG if s.tool_name == tool)
    payload = {**CASE, "use_true_solar_time": solar}
    if place is not None:
        payload["birth_place"] = place
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    response = TestClient(api.app).post(spec.rest_path, json=payload)
    assert response.status_code == 400, response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(tool, payload, raise_on_error=False)
            assert result.is_error
            return json.loads(result.content[0].text)

    native = asyncio.run(call())
    argv = [tool]
    for k, v in payload.items():
        argv += ["--" + k.replace("_", "-"), str(v)]
    capsys.readouterr()
    assert run(argv) == 1
    cli = json.loads(capsys.readouterr().out)
    for result in (response.json(), native, cli):
        assert result["error_code"] == "validation_error"
        assert not result["retryable"]
        assert "未知出生时区" in result["error"]
        assert result["error"] == response.json()["error"]
        assert "birth_timezone" in result["error"]
        assert "guolao" not in result and "person_info" not in result


@pytest.mark.parametrize("zone,place", [(None, "上海"), ("UTC", None)])
def test_known_place_or_explicit_utc_still_roundtrips_all_surfaces(
    monkeypatch, capsys, zone, place
):
    api_ready(monkeypatch)
    payload = dict(CASE)
    if zone is not None:
        payload["birth_timezone"] = zone
    if place is not None:
        payload["birth_place"] = place
    fields = ["person_info", "guolao.life_palace", "interpretation"]
    options = dict(
        as_of=AS_OF,
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        "/api/astro/guolao",
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "astro_guolao_chart", {**payload, **options}, raise_on_error=False
            )
            assert not result.is_error
            return result.structured_content

    native = asyncio.run(call())
    argv = ["astro_guolao_chart"]
    for k, v in payload.items():
        argv += ["--" + k.replace("_", "-"), str(v)]
    argv += [
        "--as-of",
        AS_OF,
        "--fields",
        *fields,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in (response.json(), native, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0]["person_info"]["birth_timezone"] == (zone or "Asia/Shanghai")


@pytest.mark.asyncio
async def test_live_schema_and_generated_dedicated_contract_explain_no_utc_default():
    async with Client(create_mcp_app(families="astro")) as client:
        tools = {t.name: t for t in await client.list_tools()}
    for tool in ("astro_guolao_chart", "astro_chart"):
        schema = tools[tool].model_dump(by_alias=True)["inputSchema"]
        assert (
            "missing timezones" in schema["properties"]["birth_timezone"]["description"]
        )
        assert schema["properties"]["birth_timezone"]["default"] is None
        if tool == "astro_guolao_chart":
            saved = json.loads(
                (ROOT / "docs/contracts/astro_guolao_chart.json").read_text()
            )
            assert schema == saved["input"]
