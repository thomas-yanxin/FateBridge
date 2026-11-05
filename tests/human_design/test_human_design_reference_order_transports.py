"""Real adapters preserve input rejections and exact-order evidence."""

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
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[2]
PLAN = json.loads(
    (ROOT / "tests/fixtures/human-design-reference-order-plan.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


def flags(params):
    return [
        "human_design",
        *(
            part
            for key, value in params.items()
            for part in ("--" + key.replace("_", "-"), str(value))
        ),
    ]


@pytest.mark.parametrize(
    "case",
    [c for c in PLAN["cases"] if not c["expected_accepted"]],
    ids=lambda c: c["id"],
)
def test_each_frozen_rejection_on_rest_mcp_cli(rest, capsys, case):
    params = case["input"]
    assert rest.post(SPEC.rest_path, json=params).status_code == 422

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", params, raise_on_error=False
            )
            assert result.is_error

    asyncio.run(call())
    assert run(flags(params)) != 0
    assert "validation_error" in capsys.readouterr().out


@pytest.mark.parametrize("empty_files", [False, True])
def test_microsecond_positive_full_result_and_card_on_rest_mcp_cli(
    rest, capsys, monkeypatch, tmp_path, empty_files
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    params = next(c["input"] for c in PLAN["cases"] if c["id"] == "normal_after_1us")
    response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not result.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["cycles"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["cycle_summary"]["reference_ordering"]
                == expected["cycle_summary"]["reference_ordering"]
            )
            return result.structured_content

    native = asyncio.run(call())
    assert run(flags(params)) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in (expected, native, cli):
        proof = value["cycle_context"]["reference_ordering"]
        assert proof["relation"] == "after"
        assert proof["birth"]["physical_jd_tt"] == proof["reference"]["physical_jd_tt"]
        report = verify_human_design_reading(value)
        assert report["status"] == "verified_fixed_template_reading", report
        value.pop("run_metadata")
    assert expected == native == cli
