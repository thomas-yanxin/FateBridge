"""Native meridian factor positions and samples through three real transports."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG

AS_OF = "2026-01-01T00:00:00Z"


def _roundtrip(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal, *, available=True
):
    specs = {spec.key: spec for spec in CATALOG}
    spec = specs[key]
    fields = [*evidence_views(specs["astro_germany"])["meridian_placement"]["fields"]]
    if available:
        fields.append("midpoint_analysis.time_sensitivity.samples")
    payload = dict(
        name="虚构：子午宫完整方向投影验收",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=1,
        analysis_datetime="2000-02-01T00:00:00Z",
    )
    if variant:
        payload["chart_variant"] = variant
    if not available:
        payload.pop("birth_time_uncertainty_minutes")
        payload.pop("analysis_datetime")
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in fields],
        ],
    )

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": AS_OF,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    mcp = asyncio.run(native())
    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(subject),
            "--as-of",
            AS_OF,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not mcp.is_error and code == 0
    results = [response.json(), mcp.structured_content, cli]
    bodies = [
        {k: v for k, v in result.items() if k != "run_metadata"} for result in results
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        layer = result["midpoint_analysis"]
        m = layer["meridian_houses"]
        if not available:
            assert m["status"] == "unavailable"
            assert isinstance(m["reason"], str) and m["reason"]
            assert "factor_placement" not in m
            assert m["real_world_efficacy"] == "not_tested"
            continue
        p = m["factor_placement"]
        assert p["factor_count"] == len(p["factors"]) == 19
        assert (
            p["physical_factor_count"],
            p["hypothetical_factor_count"],
            p["node_factor_count"],
        ) == (10, 8, 1)
        assert p["full_original_method_accepted"] is False
        assert p["real_world_efficacy"] == "not_tested"
        assert "unreconciled" in p["source_example_reconciliation"]
        samples = layer["time_sensitivity"]["samples"]
        assert len(samples) == 5
        assert all(len(s["meridian_factor_positions"]) == 19 for s in samples)
        for summary in m["birth_time_sensitivity"]["factor_placement_summary"]:
            rows = [
                next(
                    r
                    for r in s["meridian_factor_positions"]
                    if r["id"] == summary["id"]
                )
                for s in samples
            ]
            assert summary["sampled_houses"] == sorted({r["house"] for r in rows})
            assert summary["unresolved_sample_count"] == 0
        assert any(
            r["input_ecliptic_latitude"] != 0
            for r in p["factors"]
            if r["kind"] == "physical_body"
        )


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_factor_placement_and_every_sample_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    _roundtrip(monkeypatch, capsys, tmp_path, key, variant, zodiacal)


def test_published_parent_view_also_delivers_actual_backend_unavailability(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(runtime, "swe", None)
    _roundtrip(monkeypatch, capsys, tmp_path, "astro_germany", None, 0, available=False)
