"""Actual public surfaces retain second and fractional-second Guolao inputs."""

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
from tests.guolao.test_guolao_birth_precision import CASE

AS_OF = "2026-10-22T12:00:00+08:00"
ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("polymorphic", [False, True])
@pytest.mark.parametrize("solar", [False, True])
def test_precise_record_sky_clock_and_reading_agree_on_rest_native_mcp_cli(
    monkeypatch, capsys, polymorphic, solar
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    tool = "astro_chart" if polymorphic else "astro_guolao_chart"
    spec = next(s for s in CATALOG if s.tool_name == tool)
    payload = {**CASE, "use_true_solar_time": solar}
    if polymorphic:
        payload["chart_variant"] = "guolao_chart"
    fields = ["person_info", "guolao", "interpretation", "interpretation_evidence"]
    options = dict(
        as_of=AS_OF,
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    response = TestClient(api.app).post(
        spec.rest_path,
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
            return await client.call_tool(
                tool, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    assert not native.is_error, native
    argv = [tool]
    for k, v in payload.items():
        argv += ["--" + k.replace("_", "-"), str(v)]
    argv += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    results = [
        {k: v for k, v in b.items() if k != "run_metadata"}
        for b in (response.json(), native.structured_content, cli)
    ]
    assert results[0] == results[1] == results[2]
    result = results[0]
    assert result["person_info"]["utc_datetime"] == "2000-01-01T00:00:30.500000+00:00"
    life = result["guolao"]["life_palace"]
    assert life["birth_hour_branch"] == ("丑" if solar else "子")
    assert (
        f"生时{life['birth_hour_branch']}" in result["interpretation"]["core_identity"]
    )
    assert not result["guolao"]["validation"]["full_marks_established"]


@pytest.mark.asyncio
async def test_live_dedicated_and_poly_schema_publish_actual_precision_constraints():
    async with Client(create_mcp_app(families="astro")) as client:
        tools = {t.name: t for t in await client.list_tools()}
    saved = json.loads((ROOT / "docs/contracts/astro_guolao_chart.json").read_text())
    for name in ("astro_guolao_chart", "astro_chart"):
        schema = tools[name].model_dump(by_alias=True)["inputSchema"]
        for field, maximum in (("birth_second", 59), ("birth_microsecond", 999999)):
            prop = schema["properties"][field]
            assert prop["type"] == "integer"
            assert prop["minimum"] == 0 and prop["maximum"] == maximum
            assert prop["default"] == 0
        if name == "astro_guolao_chart":
            assert schema == saved["input"]
