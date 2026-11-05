"""Source-qualified gate contexts survive all three public transports."""

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

ROOT = Path(__file__).resolve().parents[2]
SPEC = next(s for s in CATALOG if s.key == "human_design")
BASE = dict(
    birth_year=1980,
    birth_month=9,
    birth_day=9,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="Europe/London",
)
CASES = [
    BASE,
    {**BASE, "birth_month": 11, "birth_day": 18},
    {**BASE, "birth_time_uncertainty_minutes": 1},
    {**BASE, "cycle_reference_datetime": "2029-07-01T00:00:00Z"},
    dict(
        birth_year=2016,
        birth_month=12,
        birth_day=31,
        birth_hour=23,
        birth_minute=59,
        birth_second=60,
        birth_timezone="-0.0002777775",
    ),
]


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize(
    "params", CASES, ids=["mental", "reflector", "interval", "cycles", "leap-end"]
)
def test_full_source_contexts_on_actual_rest_mcp_cli(
    params, empty_files, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
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
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        report = value["gate_activation_context"]
        assert (
            report["nominal"]["broad_unpaired_activated_gates"]
            == value["bodygraph"]["hanging_gates"]
        )
        assert report["context_count"] == 1 + len(report["witnesses"])
        assert value["calculation_policy"]["ephemeris_model"] == (
            "moshier" if empty_files else "swieph"
        )
        if value["bodygraph"]["type"] == "reflector":
            assert (
                report["nominal"]["dormant_in_undefined_centers"]
                == value["bodygraph"]["activated_gates"]
            )
            assert report["nominal"]["active_in_defined_centers"] == []
        value.pop("run_metadata")
    assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])


def test_published_context_card_is_a_strict_field_projection(monkeypatch, capsys):
    card = evidence_views(SPEC)["gate_context"]
    assert (
        "gate_activation_context.nominal.dormant_in_undefined_centers" in card["fields"]
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        response = client.post(
            "/api/astro/human-design",
            json=BASE,
            params=[
                *(("fields", field) for field in card["fields"]),
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
                    "fields": card["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not value.is_error
            return value.structured_content

    mcp = asyncio.run(call())
    flags = [
        "human_design",
        *["--" + k.replace("_", "-") + "=" + str(v) for k, v in BASE.items()],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *card["fields"],
    ]
    assert run(flags) == 0
    values = [response.json(), mcp, json.loads(capsys.readouterr().out)]
    for value in values:
        assert (
            "dormant_in_undefined_centers"
            in value["gate_activation_context"]["nominal"]
        )
        assert "gates" not in value["gate_activation_context"]["nominal"]
        assert (
            "休眠仍属于本命已激活"
            in value["interpretation"]["gate_activation_context"]["text"]
        )
        assert value["validation"]["all_three_axes_full_marks"] is False
        value.pop("run_metadata")
    assert _same_value(values[0], values[1]) and _same_value(values[0], values[2])
