"""Continuous state evidence stays explicit across actual local transports."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.mcp_server import create_mcp_app
from tests.test_jyotish_longitude_motion import from_tt
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import SPECS, call_surfaces

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
@pytest.mark.parametrize("case", ["J2000", "origin_wrap", "last_business_day"])
def test_continuous_state_and_qualified_limits_across_all_surfaces(
    key, case, monkeypatch, capsys, tmp_path
):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    moment = (
        datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
        if case == "last_business_day"
        else from_tt(2451545.0 if case == "J2000" else 1825399.0722706558).utc_datetime
    )
    payload = dict(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=0,
        divisions=[],
        ephemeris_policy="require_data_files",
        name="工程合成：连续框架状态",
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        if case == "last_business_day":
            # The public target-year contract ends at9800. This is a
            # rejection check, never a successful9999 dasha calculation.
            payload["analysis_year"] = 9999
            spec = SPECS[key]
            api._reset_runtime_state_for_tests()
            monkeypatch.setattr(
                api,
                "API_KEY_AUTHENTICATOR",
                api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
            )
            response = TestClient(api.app).post(spec.rest_path, json=payload)

            async def rejected():
                async with Client(create_mcp_app()) as client:
                    return await client.call_tool(
                        spec.tool_name, payload, raise_on_error=False
                    )

            native = asyncio.run(rejected())
            request = tmp_path / "request.json"
            request.write_text(json.dumps(payload))
            capsys.readouterr()
            exit_code = run([spec.tool_name, "--subject-file", str(request)])
            cli = json.loads(capsys.readouterr().out)
            assert response.status_code == 422 and native.is_error and exit_code == 1
            for result in [response.json(), json.loads(native.content[0].text), cli]:
                assert result["error_code"] == "validation_error"
                assert any(
                    issue["path"] == "analysis_year"
                    and issue["constraints"] == {"le": 9800}
                    for issue in result["issues"]
                )
                assert "india" not in result
            return
        payload["analysis_year"] = moment.year + 1
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        ["india.charts.D1.planets", "india.profile.julian_day_tt"],
    )
    planets = {p["id"]: p for p in result["india"]["charts"]["D1"]["planets"]}
    for body in ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]:
        policy = planets[body]["physical_state"]["longitude_motion_context"][
            "continuous_frame_state"
        ]
        assert policy["status"] == "partial"
        assert (
            policy["state"]["model_id"]
            == "fatebridge_continuous_scalar_lahiri_frame_v1"
        )
        assert policy["native_center_reproduced_exactly"] is True
        assert policy["primary_D1_factors_changed"] is False
        assert policy["complete_apparent_rate_certified"] is False
        assert policy["physical_TT_clock_mapping_certified"] is False
        if body == "Moon":
            source = policy["source_derivative_state"]
            assert source["model_id"] == "continuous_lahiri_lunar_source_state_v1"
            assert source["status"] == "partial"
            assert source["primary_D1_factors_changed"] is False
            assert source["complete_apparent_rate_certified"] is False
            assert source["physical_TT_clock_mapping_certified"] is False
            assert source["native_J2000_position_difference_arcsec"] <= 1e-7
            assert source["native_J2000_radius_difference_au"] <= 1e-12
        else:
            assert "source_derivative_state" not in policy
        if case == "J2000":
            assert policy["native_position_reproduced_within_line"] is False
        if case == "origin_wrap":
            assert (
                abs(policy["state"]["spherical"]["longitude_rate_degrees_per_day"]) < 20
            )
    for node in ["Rahu", "Ketu"]:
        assert (
            "continuous_frame_state"
            not in planets[node]["physical_state"]["longitude_motion_context"]
        )
