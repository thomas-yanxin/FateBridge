"""The discovered whole-second case and motion evidence on real protocols."""

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.human_design_cycle_summary import cycle_contact_facts
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")
INPUT = dict(
    birth_year=1863,
    birth_month=10,
    birth_day=25,
    birth_hour=15,
    birth_minute=1,
    birth_second=33,
    birth_timezone="UTC",
    require_swiss_files=True,
    cycle_reference_datetime="1920-01-01T00:00:00Z",
)


def test_observed_extremum_candidates_and_direction_evidence_match_three_surfaces(
    monkeypatch, capsys
):
    monkeypatch.setenv(
        "SE_EPHE_PATH", str(Path(__file__).resolve().parents[1] / "ephe")
    )
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=INPUT)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            reply = await client.call_tool(
                "human_design", {**INPUT, "response_char_limit": 0}
            )
            assert not reply.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **INPUT,
                    "fields": evidence_views(SPEC)["cycles"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert card.structured_content["cycle_summary"] == expected["cycle_summary"]
            return reply.structured_content

    mcp = asyncio.run(call())
    flags = ["human_design"]
    for key, value in INPUT.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for payload in (expected, mcp, cli):
        assert (
            verify_human_design_reading(payload)["status"]
            == "verified_fixed_template_reading"
        )
        summary = next(
            r for r in payload["cycle_summary"]["bodies"] if r["body"] == "Chiron"
        )
        assert summary["contact_count"] == 5
        facts = next(
            row
            for row in cycle_contact_facts(payload["cycle_summary"])
            if row["body"] == "Chiron"
        )
        near = [c for c in facts["contacts"] if abs(c["jd_tt"] - 2419723.795) < 1]
        assert len(near) == 2
        assert [c["motion_evidence"]["search_segment_phase_trend"] for c in near] == [
            "decreasing",
            "increasing",
        ]
        assert near[1]["motion"] == "retrograde"
        assert (
            near[1]["motion_evidence"]["native_speed_agrees_with_segment_trend"]
            is False
        )
        assert payload["cycle_context"]["timing_accuracy_certified"] is False
        payload.pop("run_metadata")
    assert expected == mcp == cli
