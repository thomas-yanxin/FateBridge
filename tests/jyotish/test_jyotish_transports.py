"""Public Indian schemas, real REST/native MCP/CLI calls and same-run delivery."""

from __future__ import annotations

import asyncio
import json
from itertools import product
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_with_receipt
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish.dasha import YEAR_DAYS
from fatebridge.core.requests.jyotish import VedicChartRequest, VimshottariDashaRequest
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import cached_mcp_app, call_calculation

SPECS = {s.name: s for s in CATALOG}
AS_OF = "2026-10-22T12:00:00+08:00"
SHARED_YEAR_BASES = ("sidereal_365_25636", "tropical_365_2425", "savana_360")


def call_surfaces(monkeypatch, capsys, key, payload, fields):
    spec = SPECS[key]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    options = {"as_of": AS_OF, "detail": "audit", "fields": fields}
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("detail", "audit"),
            *[("fields", f) for f in fields],
        ],
    )

    async def protocol():
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client, spec.name, {**payload, **options}, raise_on_error=False
            )

    protocol_result = asyncio.run(protocol())
    native = protocol_result.structured_content
    args = [spec.name]
    for name, value in payload.items():
        args += [
            "--" + name.replace("_", "-"),
            *([str(x) for x in value] if isinstance(value, list) else [str(value)]),
        ]
    args += ["--as-of", AS_OF, "--detail", "audit", "--fields", *fields]
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol_result.is_error, native
    assert code == 0, cli
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [response.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    return response.json()


def test_1960_sofa_time_context_across_three_real_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vedic_chart",
        {
            **astro_payload(),
            "birth_year": 1960,
            "birth_month": 6,
            "birth_day": 15,
            "birth_hour": 12,
            "birth_minute": 34,
            "birth_timezone": "UTC",
        },
        ["vedic_chart.profile"],
    )
    profile = result["vedic_chart"]["profile"]
    assert profile["julian_day_utc"] is not None
    assert profile["time_scale_context"]["method"].startswith("SOFA_1960")


@pytest.mark.parametrize(
    "node_mode,basis", list(product(["mean", "true"], SHARED_YEAR_BASES))
)
def test_vimshottari_configurations_across_three_real_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    node_mode: str,
    basis: str,
) -> None:
    payload = {
        **astro_payload(),
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 22,
        "analysis_hour": 0,
        "analysis_minute": 0,
        "year_basis": basis,
        "node_mode": node_mode,
    }
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vimshottari_dasha",
        payload,
        ["analysis_context", "vimshottari"],
    )
    assert result["vimshottari"]["year_days"] == YEAR_DAYS[basis]
    assert result["analysis_context"]["analysis_datetime"].endswith("T00:00:00+08:00")


def test_extended_vargas_and_complete_shadbala_across_real_surfaces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = call_surfaces(
        monkeypatch,
        capsys,
        "vedic_chart",
        {**astro_payload(), "divisions": [2, 3, 7, 9, 10, 12, 30]},
        ["vedic_chart.charts", "vedic_chart.strengths", "vedic_chart.profile", "vedic_chart.yogas"],
    )
    india = result["vedic_chart"]
    assert set(india["charts"]) == {"D1", "D2", "D3", "D7", "D9", "D10", "D12", "D30"}
    assert india["strengths"]["shadbala_assessment"]["status"] == "complete"
    assert india["strengths"]["shadbala_assessment"]["total_virupa"]["Sun"] > 0
    assert len(india["strengths"]["bhava_bala"]) == 12
    for point in [
        india["charts"]["D30"]["ascendant"],
        *india["charts"]["D30"]["planets"],
    ]:
        assert point["longitude"] is None
        assert point["degree_in_sign"] is None


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", ["vedic_chart", "vimshottari_dasha"])
def test_strict_data_file_policy_rejects_fallback_on_all_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    key: str,
) -> None:
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = SPECS[key]
    payload = {**astro_payload(), "ephemeris_policy": "require_data_files"}
    response = TestClient(api.app).post(spec.rest_path, json=payload)
    assert "require_data_files" in response.text

    async def protocol():
        async with Client(cached_mcp_app()) as client:
            return await call_calculation(
                client, spec.name, payload, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert native.is_error
    assert "require_data_files" in native.structured_content["error"]


def test_discovery_has_nested_output_contracts_and_new_standalone_requests() -> None:
    expected_defs = {
        "vedic_chart": {"JyotishProfile", "VargaCharts", "VargaChart", "Nakshatra"},
        "vimshottari_dasha": {
            "Vimshottari",
            "DashaPeriod",
            "DashaSeed",
            "DashaBirthBalance",
        },
    }
    for key, defs in expected_defs.items():
        description = describe_spec(SPECS[key])
        assert description["evidence_views"]
        schema = SPECS[key].output_model.model_json_schema()
        assert defs <= set(schema["$defs"])
    req1 = VedicChartRequest.model_validate(
        {**astro_payload(), "ayanamsa": "kp", "ashtakavarga_profile": "aiyar"}
    )
    assert req1.ayanamsa == "kp" and req1.ashtakavarga_profile == "aiyar"
    req2 = VimshottariDashaRequest.model_validate(
        {**astro_payload(), "year_basis": "julian_365_25", "include_yogini": True}
    )
    assert req2.year_basis == "julian_365_25" and req2.include_yogini


def test_as_of_date_anchor_and_audit_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = SPECS["vimshottari_dasha"]
    request = spec.request_model.model_validate(astro_payload())
    result = execute_with_receipt(
        spec,
        request,
        options=ExecutionOptions(as_of="2026-10-21T20:00:00Z", detail="audit"),
    )
    assert (
        result["analysis_context"]["analysis_datetime"] == "2026-10-22T00:00:00+08:00"
    )
    assert len(result["vimshottari"]["timeline"]) == 9
    assert sum(len(p["antardashas"]) for p in result["vimshottari"]["timeline"]) == 81
