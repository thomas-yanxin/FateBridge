"""Decimal offset precision is preserved by every actual public adapter."""

import asyncio
import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.claims import _same_value
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "tests/data/human_design/decimal_offset/plan.json").read_text()
)


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("case", PLAN["valid_cases"], ids=lambda c: c["id"])
def test_all_original_inputs_both_backends_match_rest_mcp_cli(
    case, empty_files, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = case["input"]
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == 200, response.text
    rest = response.json()

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            value = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not value.is_error
            return value.structured_content

    native = asyncio.run(call())
    flags = [
        "human_design",
        *[
            "--" + key.replace("_", "-") + "=" + str(value)
            for key, value in params.items()
        ],
    ]
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in (rest, native, cli):
        assert datetime.fromisoformat(value["birth_utc"]) == datetime.fromisoformat(
            case["expected_utc_label"]
        )
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        assert value["calculation_policy"]["ephemeris_model"] == (
            "moshier" if empty_files else "swieph"
        )
        value.pop("run_metadata")
    assert _same_value(rest, native) and _same_value(rest, cli)


@pytest.mark.parametrize("case", PLAN["reject_cases"], ids=lambda c: c["offset"])
def test_all_original_provisional_rejections_keep_the_original_magnitude_scope(
    case, monkeypatch, capsys
):
    params = dict(
        birth_year=1980,
        birth_month=7,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=case["offset"],
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    accepted = abs(Fraction(case["offset"])) <= 15
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == (200 if accepted else 422)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            value = await client.call_tool(
                "human_design",
                {**params, "response_char_limit": 0},
                raise_on_error=False,
            )
            assert value.is_error is not accepted
            return value.structured_content

    native = asyncio.run(call())
    flags = [
        "human_design",
        *[
            "--" + key.replace("_", "-") + "=" + str(value)
            for key, value in params.items()
        ],
    ]
    assert run(flags) == (0 if accepted else 1)
    cli = json.loads(capsys.readouterr().out)
    for value in (response.json(), native, cli):
        if accepted:
            check = verify_human_design_reading(value)
            assert check["status"] == "verified_fixed_template_reading", check
            assert (
                value["clock_evidence"]["timezone_rules"][
                    "rounding_error_bound_seconds"
                ]
                == "0.0000005"
            )
        else:
            assert (
                value["error_code"] == "validation_error"
                and value["retryable"] is False
            )
            assert "activations" not in value
