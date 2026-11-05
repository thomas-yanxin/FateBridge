"""Complete charts and public cycle validation retain subsecond UTC offsets."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design import verify_human_design_reading

PLAN = json.loads(
    (Path(__file__).parent / "data/human_design/numeric_offsets.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1980,
    birth_month=7,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
)


@pytest.mark.parametrize("case", PLAN["unicode_cases"], ids=lambda c: c["id"])
def test_complete_unicode_and_ascii_charts_differ_only_in_original_input_echo(case):
    values = []
    for zone in (case["offset"], case["ascii"]):
        value = execute_tool(
            SPEC, SPEC.request_model(**{**INPUT, "birth_timezone": zone})
        )
        assert "error" not in value, value
        assert (
            verify_human_design_reading(value)["status"]
            == "verified_fixed_template_reading"
        )
        assert value["calculation_policy"].pop("birth_timezone") == zone
        assert value["clock_evidence"]["input"].pop("birth_timezone") == zone
        value.pop("run_metadata")
        values.append(value)
    assert _same_value(*values)


@pytest.mark.parametrize("before_birth", [True, False])
def test_three_public_adapters_preserve_exact_cycle_reference_order(
    before_birth, monkeypatch, capsys
):
    reference = (
        "1980-07-01T12:00:00" + ("+" if before_birth else "-") + "00:00:00.036000"
    )
    params = {**INPUT, "cycle_reference_datetime": reference}
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == (422 if before_birth else 200), response.text

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            value = await client.call_tool(
                "human_design",
                {**params, "response_char_limit": 0},
                raise_on_error=False,
            )
            assert value.is_error is before_birth
            return value.structured_content

    native = asyncio.run(call())
    assert run(
        [
            "human_design",
            *["--" + k.replace("_", "-") + "=" + str(v) for k, v in params.items()],
        ]
    ) == (1 if before_birth else 0)
    cli = json.loads(capsys.readouterr().out)
    values = [response.json(), native, cli]
    for value in values:
        if before_birth:
            assert (
                value["error_code"] == "validation_error"
                and value["retryable"] is False
            )
            assert "activations" not in value
        else:
            assert (
                value["cycle_context"]["reference_utc"]
                == "1980-07-01T12:00:00.036000+00:00"
            )
            assert value["cycle_context"]["reference_ordering"]["relation"] == "after"
            assert value["cycle_summary"]["sixth_line"]["current_phase"] is None
            check = verify_human_design_reading(value)
            assert check["status"] == "verified_fixed_template_reading", check
            value.pop("run_metadata")
    if not before_birth:
        assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])
