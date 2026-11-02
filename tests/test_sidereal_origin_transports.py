"""Boundary repair and its retained native evidence survive local protocols."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import sidereal_origin_motion as origin
from fatebridge.mcp_server import create_mcp_app
from fatebridge.utils.errors import EphemerisSourceError
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_longitude_motion import from_tt
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import SPECS, call_surfaces
from tests.test_sidereal_origin_motion import BEFORE, ORACLE

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_actual_boundary_rates_signs_and_original_native_values_cross_all_surfaces(
    key, monkeypatch, capsys
):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    row = next(
        r
        for r in BEFORE["rows"]
        if r["offset_seconds"] == 30 and r["node_mode"] == "mean"
    )
    moment = from_tt(row["epoch_jd_tt"]).utc_datetime
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
        name="工程合成：圆周原点跨界",
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = moment.year + 1
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        ["india.charts.D1.planets", "india.profile.julian_day_tt"],
    )
    assert result["india"]["profile"]["julian_day_tt"] == row["epoch_jd_tt"]
    planets = {p["id"]: p for p in result["india"]["charts"]["D1"]["planets"]}
    for name in ["Moon", "Jupiter", "Saturn", "Rahu", "Ketu"]:
        state = planets[name]["physical_state"]
        assert abs(state["longitude_speed_native_degrees_per_day"]) > 300000
        assert abs(state["longitude_speed_degrees_per_day"]) < 20
        context = state["longitude_motion_context"]
        policy = context["traditional_sidereal_origin_wrap"]
        assert policy["whole_turns_removed"] == -1
        assert policy["longitude_speed_correction"] == -360000
        assert policy["center_origin_reproduced_exactly"] is True
        assert policy["complete_origin_derivative_certified"] is False
        if name in {"Saturn", "Rahu", "Ketu"}:
            assert state["motion"] == "retrograde"
        if name in {"Jupiter", "Saturn", "Rahu", "Ketu"}:
            oracle = ORACLE[
                row["epoch_jd_tt"], "Mean Node" if name in {"Rahu", "Ketu"} else name
            ]
            assert (
                abs(
                    state["longitude_speed_degrees_per_day"]
                    - oracle["expected_same_source_circular_speed"]
                )
                * 3600
                <= 1e-6
            )


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_nonreproduced_origin_is_safe_error_on_all_surfaces(
    key, monkeypatch, capsys, tmp_path
):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))

    def fail(*args, **kwargs):
        raise EphemerisSourceError("sidereal_origin_not_reproduced")

    monkeypatch.setattr(origin, "circular_origin_correction", fail)
    payload = {
        **astro_payload(),
        "divisions": [],
        "birth_time_uncertainty_minutes": 0,
        "ephemeris_policy": "require_data_files",
    }
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    spec = SPECS[key]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(spec.rest_path, json=payload)

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(spec.tool_name, payload, raise_on_error=False)

    native = asyncio.run(protocol())
    capsys.readouterr()
    exit_code = run([spec.tool_name, "--subject-file", str(request)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 503 and native.is_error and exit_code == 1
    for body in [response.json(), json.loads(native.content[0].text), cli]:
        assert body["error_code"] == "ephemeris_source_inconsistent"
        assert body["retryable"] is False
        assert body["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "sidereal_origin_not_reproduced"}
        ]
        assert "india" not in body


def test_real_child_returns_origin_failure_and_is_reaped(monkeypatch):
    from fatebridge.core.astro import native_execution as execution
    from fatebridge.core.jyotish import build_india

    e.configure_ephemeris_path(str(ROOT / "ephe"))
    bootstrap = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0,{str(ROOT/'src')!r})",
            "from fatebridge.core.astro import sidereal_origin_motion, _native_worker",
            "from fatebridge.utils.errors import EphemerisSourceError",
            "def fail(*args,**kwargs):",
            "    raise EphemerisSourceError('sidereal_origin_not_reproduced')",
            "sidereal_origin_motion.circular_origin_correction=fail",
            "_native_worker.main()",
        ]
    )
    original = execution.subprocess.Popen
    children = []

    def started(args, *a, **kw):
        process = original([sys.executable, "-I", "-c", bootstrap], *a, **kw)
        children.append(process)
        return process

    monkeypatch.setattr(execution.subprocess, "Popen", started)
    with pytest.raises(EphemerisSourceError) as caught:
        build_india(from_tt(2451545.0), divisions=[])
    assert caught.value.reason == "sidereal_origin_not_reproduced"
    assert len(children) == 1
    assert children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed
