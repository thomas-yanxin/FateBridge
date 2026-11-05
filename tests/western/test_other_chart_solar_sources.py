"""Real Sun-source races, progressed coverage and public source contracts."""

import asyncio
import json
import math
import os
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_midpoint_payload
from fatebridge.core.astro.day_meridian import target_sun_state
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.astro.sensitivity import enrich_specialty_sensitivity
from fatebridge.core.astro.solar_arc import enrich_solar_arc, solar_arc_state
from fatebridge.core.astro.solar_ephemeris import SolarEphemerisBatch
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_germany_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError

pytestmark = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")


@pytest.fixture(autouse=True)
def restore_configuration(monkeypatch):
    previous = e.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    yield
    if previous_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", previous_env)
    e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.fixture
def files(tmp_path):
    source = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR",
            str(Path(__file__).resolve().parents[2] / "ephe"),
        )
    )
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1", "sepl_24.se1", "semo_24.se1"):
        verify_ephemeris_bytes(name, (source / name).read_bytes(), manifest)
    directory = tmp_path / "ephe"
    directory.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(source / name, directory / name)
        (directory / name).chmod(0o644)
    e.configure_ephemeris_path(str(directory))
    return source, directory


def edge_input(directory, slot=0):
    e.configure_ephemeris_path(str(directory))
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    # Library-selected coverage edge: a regression trigger, not an external
    # astronomical reference or a cherry-picked outcome event.
    edge = e.swe.get_current_file_data(slot)[2]
    center = datetime_from_tt(edge - 40).replace(microsecond=0)
    target = center + timedelta(days=40 * 365.25)
    return {
        "name": "虚构：推移太阳星历边界",
        "birth_year": center.year,
        "birth_month": center.month,
        "birth_day": center.day,
        "birth_hour": center.hour,
        "birth_minute": center.minute,
        "birth_second": center.second,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "birth_time_uncertainty_minutes": 1.0,
        "analysis_datetime": target.isoformat(),
    }


@pytest.mark.parametrize("key_years", [0, 40])
def test_other_managed_worker_cannot_change_configuration_mid_arc(
    files, tmp_path, monkeypatch, key_years
):
    _, directory = files
    empty = tmp_path / "empty"
    empty.mkdir()
    birth = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    jd = ephemeris_time(birth).jd_tt
    start, done = threading.Event(), threading.Event()
    calls, acquired = [], []
    actual = runtime.ephemeris_call

    def tracked(operation, *args, **kwargs):
        result = actual(operation, *args, **kwargs)
        if operation == "calc":
            calls.append(args[0])
            if len(calls) == 1:
                start.set()
                assert done.wait(5)
        return result

    def worker():
        if not start.wait(5):
            return
        got = e._EPHEMERIS_LOCK.acquire(blocking=False)
        acquired.append(got)
        if got:
            try:
                e.configure_ephemeris_path(str(empty))
            finally:
                e._EPHEMERIS_LOCK.release()
        done.set()

    monkeypatch.setattr(runtime, "ephemeris_call", tracked)
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        result = solar_arc_state(birth, jd, birth + timedelta(days=key_years * 365.25))
    finally:
        thread.join(6)
    assert not thread.is_alive() and acquired == [False]
    assert e.configured_ephemeris_path() == str(directory)
    assert result["sun_ephemeris_models"] == ["swieph", "swieph"]
    assert len(calls) == (1 if key_years == 0 else 2)
    if key_years == 0:
        assert result["solar_arc_degrees"] == 0
        assert result["sun_observation_indices"] == [0, 0]


def test_zero_day_and_direction_share_one_real_tt_observation(files):
    birth = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    with SolarEphemerisBatch() as batch:
        state = solar_arc_state(birth, ephemeris_time(birth).jd_tt, birth, _batch=batch)
        target = target_sun_state(birth, _batch=batch)
    assert state["sun_observation_indices"] == [0, 0]
    assert target["target_sun_observation_index"] == 0
    assert target["target_tropical_sun"] == state["natal_tropical_sun"]
    assert batch.result["query_count"] == 1


def test_reentrant_configuration_change_is_rejected(files, tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    actual = runtime.ephemeris_call

    def change(operation, *args, **kwargs):
        result = actual(operation, *args, **kwargs)
        if operation == "calc":
            e.configure_ephemeris_path(str(empty))
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", change)
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        with SolarEphemerisBatch() as batch:
            batch.sun(2451545.0)


def test_mutated_sun_file_is_rejected_on_batch_exit(files, monkeypatch):
    _, directory = files
    with pytest.raises(EphemerisSourceError, match="file changed during"):
        with SolarEphemerisBatch() as batch:
            batch.sun(2451545.0)
            file = directory / "sepl_18.se1"
            file.write_bytes(file.read_bytes() + b"changed after real Sun query")


@pytest.mark.parametrize("sidereal", [False, True])
def test_native_and_recomputed_natal_sun_cannot_silently_change_model(
    files, tmp_path, sidereal
):
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    payload = build_midpoint_payload(birth, zodiacal=int(sidereal))
    enrich_specialty_sensitivity(payload, birth, kind="germany", uncertainty_minutes=0)
    empty = tmp_path / "empty"
    empty.mkdir()
    e.configure_ephemeris_path(str(empty))
    with pytest.raises(EphemerisSourceError, match="Natal Sun source differs"):
        enrich_solar_arc(payload, birth, datetime(2040, 1, 1, tzinfo=timezone.utc))


def test_legitimate_different_epoch_models_remain_explicit(files):
    _, directory = files
    args = edge_input(directory)
    args["analysis_datetime"] = datetime.fromisoformat(args["analysis_datetime"])
    args["birth_time_uncertainty_minutes"] = 0
    result = calculate_germany_chart_analysis(**args)
    assert "error" not in result
    solar = result["midpoint_analysis"]["solar_arc_analysis"]
    assert solar["profile"]["sun_ephemeris_models"] == ["swieph", "swieph"]
    assert solar["daily_meridian"]["profile"]["target_sun_ephemeris_model"] == "moshier"
    batch = solar["profile"]["sun_ephemeris_source"]
    target = batch["observations"][
        solar["daily_meridian"]["profile"]["target_sun_observation_index"]
    ]
    assert target["model"] == "moshier" and target["file_ids"] == []
    assert (
        batch["accuracy_certified"] is False
        and batch["atomic_file_read_proven"] is False
    )


def test_internal_moon_fallback_is_not_hidden_by_an_unchanged_swiss_sun_flag(files):
    source, directory = files
    # Planet data span both sides; only the next lunar segment is missing.
    shutil.copy2(source / "sepl_24.se1", directory / "sepl_24.se1")
    payload = edge_input(directory, slot=1)
    payload["analysis_datetime"] = datetime.fromisoformat(payload["analysis_datetime"])
    center = datetime(
        payload["birth_year"],
        payload["birth_month"],
        payload["birth_day"],
        payload["birth_hour"],
        payload["birth_minute"],
        payload["birth_second"],
        tzinfo=timezone.utc,
    )
    observed = []
    for seconds in (-60, -30, 0, 30, 60):
        moment = center + timedelta(seconds=seconds)
        if seconds > 0:
            # The library's top-level Swiss bit is insufficient: the missing
            # lunar dependency is now rejected before any mixed source escapes.
            with pytest.raises(EphemerisSourceError) as fault:
                solar_arc_state(
                    moment, ephemeris_time(moment).jd_tt, payload["analysis_datetime"]
                )
            assert fault.value.reason == "swiss_dependency_unavailable"
        else:
            state = solar_arc_state(
                moment, ephemeris_time(moment).jd_tt, payload["analysis_datetime"]
            )
            observed.append(state["sun_ephemeris_models"])
    assert observed == [["swieph", "swieph"]] * 3
    partial = calculate_germany_chart_analysis(**payload)
    assert partial["error_code"] == "ephemeris_source_inconsistent"
    assert partial["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "swiss_dependency_unavailable"}
    ]
    shutil.copy2(source / "semo_24.se1", directory / "semo_24.se1")
    e.configure_ephemeris_path(str(directory))
    complete = calculate_germany_chart_analysis(**payload)
    assert "error" not in complete
    samples = complete["midpoint_analysis"]["solar_arc_analysis"][
        "birth_time_sensitivity"
    ]["samples"]
    assert [row["offset_seconds"] for row in samples] == [-60, -30, 0, 30, 60]
    assert all(row["sun_ephemeris_models"] == ["swieph", "swieph"] for row in samples)


@pytest.mark.parametrize("jd", [math.nan, math.inf, -math.inf])
def test_nonfinite_sun_epoch_is_rejected(jd):
    with pytest.raises(ValueError, match="finite"):
        with SolarEphemerisBatch() as batch:
            batch.sun(jd)


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
def test_progressed_boundary_error_and_same_complete_grid_across_surfaces(
    files, monkeypatch, tmp_path, capsys, key, variant
):
    source, directory = files
    payload = edge_input(directory)
    if variant:
        payload["chart_variant"] = variant
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    spec = next(s for s in CATALOG if s.key == key)
    path = "midpoint_analysis.solar_arc_analysis"
    options = dict(
        fields=[path],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-22T00:00:00Z",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))

    def surfaces():
        params = [("fields", path)] + [
            (k, str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in options.items()
            if k != "fields"
        ]
        rest = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

        async def mcp():
            async with Client(create_mcp_app()) as client:
                return await client.call_tool(
                    spec.tool_name, {**payload, **options}, raise_on_error=False
                )

        protocol = asyncio.run(mcp())
        capsys.readouterr()
        code = run(
            [
                spec.tool_name,
                "--subject-file",
                str(request),
                "--fields",
                path,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
                "--as-of",
                options["as_of"],
            ]
        )
        cli = json.loads(capsys.readouterr().out)
        return rest, protocol, code, cli

    rest, protocol, code, cli = surfaces()
    assert rest.status_code == 503 and protocol.is_error and code == 1
    for error in (rest.json(), json.loads(protocol.content[0].text), cli):
        assert error["error_code"] == "ephemeris_source_inconsistent"
        assert error["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "model_changed"}
        ]
        assert error["retryable"] is False and str(directory) not in json.dumps(error)
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(source / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    rest, protocol, code, cli = surfaces()
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    solar = [
        body["midpoint_analysis"]["solar_arc_analysis"]
        for body in (rest.json(), protocol.structured_content, cli)
    ]
    assert solar[0] == solar[1] == solar[2]
    for result in solar:
        samples = result["birth_time_sensitivity"]["samples"]
        assert len(samples) == 5 and [s["offset_seconds"] for s in samples] == [
            -60,
            -30,
            0,
            30,
            60,
        ]
        assert all(s["sun_ephemeris_models"] == ["swieph", "swieph"] for s in samples)
        batch = result["profile"]["sun_ephemeris_source"]
        assert (
            batch["query_count"] == 11
        )  # nominal reuses central sample; target distinct
        assert len({o["julian_day_tt"] for o in batch["observations"]}) == 11
        for sample in samples:
            for index, tt in zip(
                sample["sun_observation_indices"],
                (sample["julian_day_tt"], sample["progressed_julian_day_tt"]),
            ):
                assert batch["observations"][index]["julian_day_tt"] == tt
    Draft202012Validator(spec.output_model.model_json_schema()).validate(rest.json())
