"""Actual strict-DE441 India calculations; a refusal is not a positive pass."""

import asyncio
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.execution_context import call_clock
from fatebridge.core.jyotish import build_india, positions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.jyotish import calculate_vimshottari
from fatebridge.services.tool_catalog import CATALOG
from tests.test_jyotish_transports import call_surfaces

FIXTURES = Path(__file__).parent / "fixtures"
KERNEL = "india-de441-j2000.eph"
KERNEL_SHA = "5e298b899542373c2f5814c8397cdea5a4627d1e4f5f6d1a89a11810955441cf"
PAYLOAD = {
    "birth_year": 2000,
    "birth_month": 1,
    "birth_day": 1,
    "birth_hour": 12,
    "birth_minute": 0,
    "birth_timezone": "UTC",
    "birth_longitude": 0.0,
    "birth_latitude": 0.0,
}
OPTIONS = {"ephemeris_policy": "require_data_files", "cheshta_model": "simon1994_j2000"}


@pytest.fixture
def jpl(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    raw = (FIXTURES / "astrodice-de441-j2000.eph").read_bytes()
    assert len(raw) == 40720 and hashlib.sha256(raw).hexdigest() == KERNEL_SHA
    kernel = tmp_path / KERNEL
    kernel.write_bytes(raw)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", KERNEL)
    e.configure_ephemeris_path()
    try:
        yield kernel
    finally:
        monkeypatch.undo()
        e.configure_ephemeris_path(previous if previous is not None else "")


def assert_source(profile):
    assert profile["physical_backend_policy"] == "strict_jpl"
    assert profile["ephemeris_models"] == ["jpl"]
    source = profile["physical_ephemeris_source"]
    assert len(source["files"]) == 1
    assert source["files"][0]["sha256"] == KERNEL_SHA
    assert source["files"][0]["de_number"] == 441
    assert source["accuracy_certified"] is False
    assert source["has_unidentified_sources"] is False
    assert len(source["by_factor"]) == 19  # 7 ecliptic,7 equatorial,5 geometric.
    assert all(r["model"] == "jpl" for r in source["by_factor"].values())
    policy = source["time_scale_policy"]
    assert policy["raw_header_time_scale"] == "TDB"
    assert policy["native_api_time_scale"] == "TT"
    assert policy["tt_tdb_conversion_applied"] is False


@pytest.mark.parametrize("node_mode", ["mean", "true"])
@pytest.mark.parametrize("entry", ["india", "vimshottari"])
def test_actual_strict_jpl_all_frames_optional_motion_and_birth_grid(
    jpl, node_mode, entry
):
    with call_clock("2026-10-23T00:00:00Z"):
        if entry == "india":
            result = build_india(
                build_astro_birth_info(**PAYLOAD, preserve_instant=True),
                divisions=[9, 10],
                node_mode=node_mode,
                birth_time_uncertainty_minutes=1,
                **OPTIONS,
            )
        else:
            service = calculate_vimshottari(
                **PAYLOAD,
                analysis_year=2001,
                divisions=[9, 10],
                node_mode=node_mode,
                birth_time_uncertainty_minutes=1,
                **OPTIONS,
            )
            assert "error" not in service
            result = service["india"]
            assert service["vimshottari"]
    assert_source(result["profile"])
    grid = result["birth_time_sensitivity"]
    assert grid["sample_count"] == 5
    assert grid["sampled_ephemeris_fallback_bodies"] == []
    assert len(grid["source_comparison"]["sample_source_indices"]) == 5
    assert all(
        r["model"] == "jpl"
        for source in grid["source_comparison"]["physical_ephemeris_sources"]
        for r in source["by_factor"].values()
    )
    if node_mode == "mean":
        assert (
            result["profile"]["nonphysical_factor_models"]["Rahu"]
            == "swisseph_analytical_mean_node"
        )


def test_original_reference_TT_and_geometric_sdk_output_match_independent_vectors(jpl):
    raw = (FIXTURES / "jyotish-jpl-j2000-reference.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "d94a2f582520a0a330a46342c0dad5a316cb3ac1609e80161fd8a38197b7df0e"
    )
    reference = json.loads(raw)
    # This separate synthetic input has TT exactlyJ2000, from the known
    # 64.184second TT-UTC offset. The12:00UTC integration case stays unchanged.
    birth = build_astro_birth_info(
        **{
            **PAYLOAD,
            "birth_hour": 11,
            "birth_minute": 58,
            "birth_second": 55,
            "birth_microsecond": 816000,
        },
        preserve_instant=True,
    )
    value = positions(birth, **OPTIONS)
    assert value["julian_day_tt"] == 2451545.0
    for row in reference["rows"]:
        point = value["motion_true_j2000"][row["body"]]
        assert point["ephemeris_model"] == "jpl"
        lon, lat = map(math.radians, (point["longitude"], point["latitude"]))
        v = (
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        )
        w = row["ecliptic_unit_vector"]
        cross = (
            v[1] * w[2] - v[2] * w[1],
            v[2] * w[0] - v[0] * w[2],
            v[0] * w[1] - v[1] * w[0],
        )
        error = (
            math.degrees(
                math.atan2(
                    math.sqrt(sum(x * x for x in cross)),
                    sum(a * b for a, b in zip(v, w)),
                )
            )
            * 3600
        )
        assert error <= reference["position_line_arcsec"] == 0.02


def test_parent_manual_delta_t_is_neither_inherited_nor_reset_in_strict_jpl(jpl):
    birth = build_astro_birth_info(**PAYLOAD, preserve_instant=True)
    clean = positions(birth, **OPTIONS)
    e.swe.set_delta_t_userdef(400 / 86400)
    try:
        contaminated = positions(birth, **OPTIONS)
        assert contaminated == clean
        assert e.swe.deltat_ex(2451545.0, e.swe.FLG_JPLEPH) * 86400 == 400
    finally:
        e.swe.set_delta_t_userdef(e.swe.DELTAT_AUTOMATIC)


@pytest.mark.parametrize("protected", ["kernel", "reference"])
def test_auditor_cannot_overwrite_its_kernel_or_reference(jpl, protected):
    reference = FIXTURES / "jyotish-jpl-j2000-reference.json"
    report = jpl if protected == "kernel" else reference
    before = report.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/audit_jyotish_jpl.py"),
            "--kernel",
            str(jpl),
            "--reference",
            str(reference),
            "--report",
            str(report),
        ],
        capture_output=True,
        timeout=1800,
    )
    assert result.returncode == 2
    assert report.read_bytes() == before


def test_auditor_missing_kernel_is_a_failed_positive_not_a_pass(jpl, tmp_path):
    report = tmp_path / "failed-positive.json"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/audit_jyotish_jpl.py"),
            "--kernel",
            str(tmp_path / "missing.eph"),
            "--report",
            str(report),
        ],
        capture_output=True,
        timeout=1800,
    )
    assert result.returncode == 1
    value = json.loads(report.read_text())
    assert value["status"] == "failed" and value["positive_pass"] is False
    assert value["reason"] == "jpl_file_unavailable"


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_strict_jpl_positive_projection_across_real_surfaces(
    jpl, monkeypatch, capsys, key
):
    payload = {
        **PAYLOAD,
        **OPTIONS,
        "birth_time_uncertainty_minutes": 1,
        "divisions": [9, 10],
    }
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2001
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile.physical_backend_policy",
            "india.profile.ephemeris_models",
            "india.profile.physical_ephemeris_source",
            "india.birth_time_sensitivity.sample_count",
            "india.profile.nonphysical_factor_models",
        ],
    )
    assert_source(result["india"]["profile"])
    assert result["india"]["birth_time_sensitivity"]["sample_count"] == 5


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
@pytest.mark.parametrize("problem", ["missing", "truncated", "out_of_range"])
def test_strict_jpl_failures_preserve_source_errors_on_all_surfaces(
    jpl, monkeypatch, capsys, key, problem
):
    payload = {**PAYLOAD, **OPTIONS}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2001
    if problem == "missing":
        monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing.eph")
        reasons = {"jpl_file_unavailable"}
    elif problem == "truncated":
        jpl.write_bytes(jpl.read_bytes()[:-8])
        reasons = {"jpl_file_unavailable", "jpl_kernel_invalid"}
    else:
        payload["birth_year"] = 2005
        reasons = {"jpl_native_fallback", "jpl_native_failed"}
    spec = next(s for s in CATALOG if s.key == key)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(spec.rest_path, json=payload)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name, payload, raise_on_error=False
            )
            assert result.is_error
            return json.loads(result.content[0].text)

    native = asyncio.run(invoke())
    flags = [spec.tool_name]
    for name, value in payload.items():
        flags += ["--" + name.replace("_", "-"), str(value)]
    capsys.readouterr()
    assert run(flags) == 1
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 503
    for error in (rest.json(), native, cli):
        assert error["error_code"] == "ephemeris_source_inconsistent"
        assert error["retryable"] is False
        assert error["issues"][0]["path"] == "runtime.ephemeris_data"
        assert error["issues"][0]["code"] in reasons
        assert "india" not in error
        assert str(jpl.parent) not in json.dumps(error)
