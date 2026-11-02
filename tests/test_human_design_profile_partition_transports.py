"""Nominal role partition and exact rational strings on the three surfaces."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
BASE = dict(
    birth_year=1981,
    birth_month=5,
    birth_day=6,
    birth_hour=16,
    birth_minute=22,
    birth_timezone="Europe/London",
)


def prepare(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("node_mode", ["true", "mean"])
def test_complete_partition_and_actual_profile_on_rest_mcp_cli(
    empty_files, node_mode, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    prepare(monkeypatch)
    params = {**BASE, "node_mode": node_mode}
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            value = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not value.is_error
            return value.structured_content

    mcp = asyncio.run(call())
    assert (
        run(
            [
                "human_design",
                *["--" + k.replace("_", "-") + "=" + str(v) for k, v in params.items()],
            ]
        )
        == 0
    )
    values = [response.json(), mcp, json.loads(capsys.readouterr().out)]
    for value in values:
        proof = verify_human_design_reading(value)
        assert proof["status"] == "verified_fixed_template_reading", proof
        c = value["profile_partition_context"]
        assert c["actual_profile"] == value["profile"] == "3/6"
        assert c["actual_profile_category"] == "transition"
        assert c["source_facts"]["source_wording_ambiguity"]["resolved"] is False
        assert all(type(v) is str for v in c["actual_solar_arc_residual_degrees_ratio"])
        assert value["validation"]["all_three_axes_full_marks"] is False
        value.pop("run_metadata")
    assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])


def test_published_partition_view_is_strict_and_keeps_source_scope(monkeypatch, capsys):
    prepare(monkeypatch)
    card = evidence_views(SPEC)["profile_partition"]
    fields = card["fields"]
    with TestClient(api.app) as client:
        response = client.post(
            "/api/astro/human-design",
            json=BASE,
            params=[
                *(("fields", f) for f in fields),
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
            ],
        )
    assert response.status_code == 200, response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            value = await client.call_tool(
                "human_design",
                {
                    **BASE,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not value.is_error
            return value.structured_content

    mcp = asyncio.run(call())
    assert (
        run(
            [
                "human_design",
                *["--" + k.replace("_", "-") + "=" + str(v) for k, v in BASE.items()],
                "--strict-fields",
                "--no-include-snapshot-text",
                "--fields",
                *fields,
            ]
        )
        == 0
    )
    values = [response.json(), mcp, json.loads(capsys.readouterr().out)]
    for value in values:
        assert "basis" not in value["profile_partition_context"]
        assert (
            value["profile_partition_context"]["actual_profile_category"]
            == "transition"
        )
        assert (
            "基础区段" in value["interpretation"]["profile_partition_context"]["text"]
        )
        assert value["validation"]["all_three_axes_full_marks"] is False
        value.pop("run_metadata")
    assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])
