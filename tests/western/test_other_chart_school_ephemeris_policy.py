"""Real selected kernels, analytic nodes and source failures across schools."""

import asyncio
import copy
import hashlib
import json
import os
import shutil
import struct
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import human_design as hd
from fatebridge.core import jyotish
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.profiles import ANALYTICAL_MEAN_NODE_MODEL
from fatebridge.core.human_design_mechanics import BODY_IDS
from fatebridge.core.jpl_ephemeris import jpl_header
from fatebridge.core.jyotish_kala import solar_packet
from fatebridge.core.jyotish_mean import geometric_points
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.human_design import calculate_human_design
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_backend import verify_full_backend_report

pytestmark = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")
FIXTURES = Path(__file__).parents[1] / "fixtures"
KERNEL = "human-design-de441-j2000.eph"
BIRTH = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
    birth_latitude=0,
    birth_longitude=0,
)
HD_BIRTH = {
    k: v for k, v in BIRTH.items() if k not in {"birth_latitude", "birth_longitude"}
}


@pytest.fixture
def selected(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    target = tmp_path / KERNEL
    target.write_bytes((FIXTURES / KERNEL).read_bytes())
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", KERNEL)
    e.configure_ephemeris_path()
    try:
        yield target
    finally:
        monkeypatch.undo()
        e.configure_ephemeris_path(previous if previous is not None else "")


def test_wider_fixture_retains_original_coefficients_and_old_fixture():
    data = (FIXTURES / KERNEL).read_bytes()
    provenance = json.loads(
        (FIXTURES / "human-design-de441-j2000.provenance.json").read_text()
    )
    assert len(data) == provenance["fixture_bytes"] == 65152
    assert hashlib.sha256(data).hexdigest() == provenance["fixture_sha256"]
    assert (
        provenance["coefficients_unmodified"]
        and not provenance["complete_original_kernel"]
    )
    coefficient = next(
        p for p in provenance["download_parts"] if p["part"] == "coefficients"
    )
    assert hashlib.sha256(data[16288:]).hexdigest() == coefficient["sha256"]
    old = (
        Path(__file__).parents[1] / "data/astrodice/tables/de441-j2000.eph"
    ).read_bytes()
    assert (
        hashlib.sha256(old).hexdigest()
        == "5e298b899542373c2f5814c8397cdea5a4627d1e4f5f6d1a89a11810955441cf"
    )
    assert data[5 * 8144 :] == old[2 * 8144 :]
    header = jpl_header(FIXTURES / KERNEL)
    assert header["start_julian_day_tdb"] == 2451408.5
    assert header["end_julian_day_tdb"] == 2451600.5
    assert (
        header["start_julian_day_tdb"],
        header["end_julian_day_tdb"],
    ) == struct.unpack_from("<2d", data, 2652)
    assert "start_julian_day_tt" not in header and "end_julian_day_tt" not in header
    assert "legacy_tt_range_fields" not in header


def test_original_96_day_subset_still_fails_unchanged_hd_root_bracket(selected):
    selected.write_bytes(
        (
            Path(__file__).parents[1] / "data/astrodice/tables/de441-j2000.eph"
        ).read_bytes()
    )
    with pytest.raises(EphemerisSourceError):
        hd.chart_at_tt(2451545.0, "true")


def test_jpl_does_not_silently_satisfy_compressed_swiss_requirement(selected):
    result = calculate_human_design(**HD_BIRTH, require_swiss_files=True)
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["issues"] == [
        {
            "path": "runtime.ephemeris_data",
            "code": "jpl_swiss_file_requirement_conflict",
        }
    ]


@pytest.mark.parametrize("node_mode", ["mean", "true"])
def test_india_all_physical_frames_honor_selected_jpl(selected, node_mode):
    raw = jyotish.positions(build_astro_birth_info(**BIRTH), node_mode=node_mode)
    assert raw["ephemeris_models"] == ["jpl"]
    assert raw["ephemeris_model_scope"] == "physical_bodies"
    assert all(raw["ephemeris_by_body"][name] == "jpl" for name in jyotish.GRAHAS[:7])
    assert all(row["ephemeris_model"] == "jpl" for row in raw["equatorial"].values())
    with e.preserve_ephemeris_path():
        e.swe.set_jpl_file(KERNEL)
        e.swe.set_sid_mode(e.swe.SIDM_LAHIRI, 0, 0)
        for name in jyotish.GRAHAS[:7]:
            coords, flags = e.swe.calc(
                raw["julian_day_tt"],
                getattr(e.swe, name.upper()),
                e.swe.FLG_JPLEPH | e.swe.FLG_SIDEREAL | e.swe.FLG_SPEED,
            )
            assert flags & e.swe.FLG_JPLEPH
            assert raw["longitudes"][name] == coords[0]
    if node_mode == "mean":
        assert raw["ephemeris_by_body"]["Rahu"] == ANALYTICAL_MEAN_NODE_MODEL
    assert raw["native_node_return_flags"]["Rahu"] & e.swe.FLG_JPLEPH


def test_motion_and_solar_event_checks_honor_selected_jpl(selected):
    geometric = geometric_points(2451545.0, "require_data_files")
    assert len(geometric) == 5
    assert all(row["ephemeris_model"] == "jpl" for row in geometric.values())
    packet = solar_packet(2451545, 0, 0, "require_data_files")
    assert packet["ephemeris_models"] == ["jpl"]
    assert packet["events"]


def test_no_data_summaries_exclude_analytical_node(selected, monkeypatch, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    e.configure_ephemeris_path()
    raw = jyotish.positions(build_astro_birth_info(**BIRTH))
    assert raw["ephemeris_models"] == ["moshier"]
    assert raw["nonphysical_factor_models"]["Rahu"] == ANALYTICAL_MEAN_NODE_MODEL
    assert raw["native_node_return_flags"]["Rahu"] & e.swe.FLG_SWIEPH
    result = calculate_human_design(**HD_BIRTH, node_mode="mean")
    assert "error" not in result
    assert result["calculation_policy"]["ephemeris_model"] == "moshier"
    for side, models in result["calculation_policy"][
        "nonphysical_factor_models"
    ].items():
        assert models["NorthNode"] == models["SouthNode"] == ANALYTICAL_MEAN_NODE_MODEL
        node = next(a for a in result["activations"][side] if a["body"] == "NorthNode")
        assert node["native_return_flag_model"] == "swieph"


@pytest.mark.parametrize("mode", ["mean", "true"])
def test_hd_primary_chart_survives_forbidden_optional_reference(selected, mode):
    result = calculate_human_design(**HD_BIRTH, node_mode=mode)
    assert "error" not in result
    policy = result["calculation_policy"]
    assert policy["ephemeris_model"] == "jpl"
    assert policy["physical_backend_policy"] == "strict_jpl"
    assert 70 < result["design_solver"]["days_before_birth"] < 110
    assert (
        result["ephemeris_backend_comparison"]["status"]
        == "reference_disabled_by_strict_jpl_policy"
    )
    assert (
        result["ephemeris_backend_comparison"]["reference_computation_performed"]
        is False
    )
    assert verify_full_backend_report(result)["errors"] == []
    for rows in result["activations"].values():
        assert all(a["ephemeris_model"] == "jpl" for a in rows if a["body"] in BODY_IDS)
    bad = copy.deepcopy(result)
    bad["calculation_policy"]["physical_backend_policy"] = "auto"
    assert verify_full_backend_report(bad)["errors"]


@pytest.mark.parametrize("layer", ["india", "motion", "solar", "hd"])
@pytest.mark.parametrize("problem", ["missing", "truncated", "out_of_range"])
def test_selected_source_failures_never_become_analytical_results(
    selected, monkeypatch, layer, problem
):
    epoch = 2451545.0
    birth = BIRTH
    if problem == "missing":
        monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing.eph")
    elif problem == "truncated":
        selected.write_bytes(selected.read_bytes()[:-8])
    else:
        epoch = 2453372.5
        birth = {**BIRTH, "birth_year": 2005}
    with pytest.raises(EphemerisSourceError):
        if layer == "india":
            jyotish.positions(build_astro_birth_info(**birth))
        elif layer == "motion":
            geometric_points(epoch, "auto")
        elif layer == "solar":
            solar_packet(epoch, 0, 0, "auto")
        else:
            hd.chart_at_tt(epoch, "mean")


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_india", None),
        ("astro_chart", "india_chart"),
        ("astro_vimshottari", None),
        ("human_design", None),
    ],
)
@pytest.mark.parametrize("node_mode", ["mean", "true"])
def test_real_three_transport_policy_and_node_projection(
    selected, tmp_path, monkeypatch, capsys, key, variant, node_mode
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {**(HD_BIRTH if key == "human_design" else BIRTH), "node_mode": node_mode}
    if variant:
        payload["chart_variant"] = variant
    if key != "human_design":
        payload["ephemeris_policy"] = "require_data_files"
    if key == "astro_vimshottari":
        payload.update(
            analysis_year=2000,
            analysis_month=1,
            analysis_day=2,
            analysis_hour=12,
            analysis_timezone="UTC",
        )
    fields = (
        [
            "calculation_policy",
            "activations",
            "ephemeris_backend_comparison",
            "ephemeris_source_evidence",
        ]
        if key == "human_design"
        else ["india.profile"]
    )
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2000-01-01T12:00:00Z",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = [("fields", name) for name in fields] + [
        (k, str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in options.items()
        if k != "fields"
    ]
    rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)
    assert rest.status_code == 200, rest.text

    async def mcp():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    protocol = asyncio.run(mcp())
    assert not protocol.is_error
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request),
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--as-of",
            options["as_of"],
        ]
    )
    assert code == 0
    cli = json.loads(capsys.readouterr().out)
    for result in [rest.json(), protocol.structured_content, cli]:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        policy = (
            result["calculation_policy"]
            if key == "human_design"
            else result["india"]["profile"]
        )
        assert policy["ephemeris_model"] == "jpl"
        assert policy["ephemeris_model_scope"] == "physical_bodies"
        assert policy["physical_backend_policy"] == "strict_jpl"
        if key == "human_design":
            raw_bounds = struct.unpack_from("<2d", selected.read_bytes(), 2652)
            files = result["ephemeris_source_evidence"]["files"]
            assert files
            for item in files:
                assert item["range_time_scale"] == "TDB"
                assert (
                    item["start_julian_day_tdb"],
                    item["end_julian_day_tdb"],
                ) == raw_bounds
                assert (
                    "start_julian_day_tt" not in item
                    and "end_julian_day_tt" not in item
                )


def test_strict_jpl_original_reading_verifier_retains_fidelity_checks(selected):
    spec = next(s for s in CATALOG if s.key == "human_design")
    result = execute_tool(spec, spec.request_model(**HD_BIRTH))
    checked = verify_human_design_reading(result)
    assert checked["status"] == "verified_fixed_template_reading", checked


@pytest.mark.parametrize("mode", ["mean", "true"])
def test_default_file_mode_still_performs_and_verifies_full_reference(
    selected, monkeypatch, tmp_path, mode
):
    from fatebridge.core.astro.ephemeris_integrity import (
        load_ephemeris_manifest,
        verify_ephemeris_bytes,
    )

    source = Path(
        os.environ.get("FATEBRIDGE_TEST_EPHE_DIR", str(FIXTURES.parents[1] / "ephe"))
    )
    directory = tmp_path / "swiss"
    directory.mkdir()
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1"):
        verify_ephemeris_bytes(name, (source / name).read_bytes(), manifest)
        shutil.copy2(source / name, directory / name)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    e.configure_ephemeris_path()
    result = calculate_human_design(
        **HD_BIRTH, node_mode=mode, require_swiss_files=True
    )
    assert "error" not in result
    assert result["ephemeris_backend_comparison"]["status"] == "full_backend_compared"
    checked = verify_full_backend_report(result)
    assert checked["errors"] == [] and checked["checked_snapshot_count"] == 2


@pytest.mark.parametrize("key", ["astro_india", "human_design"])
def test_main_source_failure_remains_public_503(selected, monkeypatch, key):
    spec = next(s for s in CATALOG if s.key == key)
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing.eph")
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=HD_BIRTH if key == "human_design" else BIRTH,
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "ephemeris_source_inconsistent"
    assert response.json()["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "jpl_file_unavailable"}
    ]


def test_native_and_optional_motion_frames_share_one_configuration(
    selected, monkeypatch, tmp_path
):
    from fatebridge.core.astro import native_execution

    # Probe the worker-local managed transaction. The public wrapper now
    # runs in a fresh process, where parent monkeypatches cannot propagate;
    # test_jyotish_native_execution exercises that real process boundary.
    monkeypatch.setattr(native_execution, "_WORKER_ACTIVE", True)
    source = Path(
        os.environ.get("FATEBRIDGE_TEST_EPHE_DIR", str(FIXTURES.parents[1] / "ephe"))
    )
    directory = tmp_path / "swiss"
    directory.mkdir()
    empty = tmp_path / "empty"
    empty.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(source / name, directory / name)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    monkeypatch.delenv("SE_EPHE_PATH")
    e.configure_ephemeris_path(str(directory))
    start, done = threading.Event(), threading.Event()
    acquired = []
    actual = jyotish.geometric_points

    def between_frames(*args, **kwargs):
        start.set()
        assert done.wait(5)
        return actual(*args, **kwargs)

    def worker():
        if not start.wait(5):
            return
        locked = e._EPHEMERIS_LOCK.acquire(blocking=False)
        acquired.append(locked)
        if locked:
            try:
                e.configure_ephemeris_path(str(empty))
            finally:
                e._EPHEMERIS_LOCK.release()
        done.set()

    monkeypatch.setattr(jyotish, "geometric_points", between_frames)
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        result = jyotish.positions(
            build_astro_birth_info(**BIRTH), cheshta_model=jyotish.MOTION_MODEL
        )
    finally:
        thread.join(6)
    assert acquired == [False] and not thread.is_alive()
    assert result["ephemeris_models"] == ["swieph"]
    assert all(
        r["ephemeris_model"] == "swieph" for r in result["motion_true_j2000"].values()
    )
