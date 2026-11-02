"""Actual REST/MCP/CLI output and published apparent-position projection."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.parametrize("empty_path", [False, True])
def test_complete_apparent_context_and_strict_view_match_three_surfaces(
    empty_path,
    tmp_path,
    monkeypatch,
    capsys,
):
    if empty_path:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    params = dict(
        birth_year=2236,
        birth_month=3,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
    )
    fields = evidence_views(SPEC)["apparent_positions"]["fields"]
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=params)
        assert response.status_code == 200, response.text
        full_rest = response.json()
        response = rest.post(
            SPEC.rest_path,
            params=[
                *(("fields", f) for f in fields),
                ("strict_fields", "true"),
                ("include_snapshot_text", "false"),
            ],
            json=params,
        )
        assert response.status_code == 200, response.text
        view_rest = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            complete = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            selected = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not complete.is_error and not selected.is_error
            return complete.structured_content, selected.structured_content

    full_mcp, view_mcp = asyncio.run(call())
    args = ["human_design"]
    for k, v in params.items():
        args.extend(["--" + k.replace("_", "-"), str(v)])
    assert run(args) == 0
    full_cli = json.loads(capsys.readouterr().out)
    assert (
        run(
            [
                *args,
                "--fields",
                *fields,
                "--strict-fields",
                "true",
                "--include-snapshot-text",
                "false",
            ]
        )
        == 0
    )
    view_cli = json.loads(capsys.readouterr().out)
    for result in (full_rest, full_mcp, full_cli):
        check = verify_human_design_reading(result)
        assert check["status"] == "verified_fixed_template_reading", check
        assert (
            check["apparent_position_context_status"]
            == "verified_supplied_native_batch_geometry"
        )
        result.pop("run_metadata")
    assert full_rest == full_mcp == full_cli
    for selected in (view_rest, view_mcp, view_cli):
        assert (
            selected["apparent_position_context"]["nominal_side_batch_ids"]
            == full_rest["apparent_position_context"]["nominal_side_batch_ids"]
        )
        assert (
            selected["interpretation"]["apparent_position_context"]
            == full_rest["interpretation"]["apparent_position_context"]
        )
        assert "batches" not in selected["apparent_position_context"]
        assert selected["validation"]["all_three_axes_full_marks"] is False
        # A partial projection cannot masquerade as the complete original run.
        assert verify_human_design_reading(selected)["status"] == "rejected"
