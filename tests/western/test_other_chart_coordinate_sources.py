"""Real coordinate-source coherence, nominal equal13 and public provenance."""

import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
import fatebridge.core.astro.chart as charts
import fatebridge.services.astrology as service
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.midpoints import PHYSICAL_BODIES
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.western.test_other_chart_solar_sources import files as files
from tests.western.test_other_chart_solar_sources import (
    restore_configuration as restore_configuration,
)

__all__ = ["files", "restore_configuration"]

pytestmark = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")

BIRTH = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_timezone="UTC",
    birth_longitude=0,
    birth_latitude=0,
)


def test_same_tt_ecliptic_and_equatorial_calls_share_configuration(
    files, tmp_path, monkeypatch
):
    empty = tmp_path / "empty"
    empty.mkdir()
    start, done = threading.Event(), threading.Event()
    acquired = []
    models = []
    actual = runtime.ephemeris_call

    def tracked(op, *args, **kwargs):
        result = actual(op, *args, **kwargs)
        if op == "calc" and args[1] == e.swe.NEPTUNE:
            models.append(e.ephemeris_model_from_retflag(result[1]))
            if len(models) == 1:
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
        result = ephemeris._swisseph_planet_state(
            "Neptune", 2407484.43125, julian_day_tt=2407484.43125
        )
    finally:
        thread.join(6)
    assert acquired == [False] and not thread.is_alive()
    assert models == ["swieph", "swieph"] and result[1] == "swieph"


def test_unexpected_actual_equatorial_model_is_a_source_error(files, monkeypatch):
    actual = runtime.ephemeris_call

    def use_real_analytical_equatorial(op, *args, **kwargs):
        if op == "calc" and args[2] & e.swe.FLG_EQUATORIAL:
            args = (
                *args[:2],
                (args[2] & ~e.swe.FLG_SWIEPH) | e.swe.FLG_MOSEPH,
                *args[3:],
            )
        return actual(op, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", use_real_analytical_equatorial)
    with pytest.raises(EphemerisSourceError, match="ecliptic and equatorial"):
        ephemeris._swisseph_planet_state("Neptune", 2451545.0, julian_day_tt=2451545.0)


def test_unavailable_declination_preserves_successful_ecliptic_state(
    files, monkeypatch
):
    actual = runtime.ephemeris_call

    def fail_equatorial(op, *args, **kwargs):
        value = actual(op, *args, **kwargs)
        if op == "calc" and args[2] & e.swe.FLG_EQUATORIAL:
            return value[0], -1
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", fail_equatorial)
    state, model = ephemeris._swisseph_planet_state(
        "Sun", 2451545.0, julian_day_tt=2451545.0
    )
    assert model == "swieph" and "declination" not in state
    assert 0 <= state["longitude"] < 360


def test_file_changed_after_first_coordinate_is_not_an_orbital_fallback(
    files, monkeypatch
):
    _, directory = files
    actual = runtime.ephemeris_call

    def mutate_after_equatorial(op, *args, **kwargs):
        value = actual(op, *args, **kwargs)
        if op == "calc" and args[2] & e.swe.FLG_EQUATORIAL:
            p = directory / "sepl_18.se1"
            p.write_bytes(p.read_bytes() + b"changed after ecliptic identity")
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", mutate_after_equatorial)
    with pytest.raises(EphemerisSourceError, match="file changed during"):
        ephemeris._swisseph_planet_state("Sun", 2451545.0, julian_day_tt=2451545.0)


def test_configuration_change_inside_call_is_not_swallowed_as_approximation(
    files, tmp_path, monkeypatch
):
    empty = tmp_path / "empty"
    empty.mkdir()
    actual = runtime.ephemeris_call

    def switch(op, *args, **kwargs):
        value = actual(op, *args, **kwargs)
        if op == "calc":
            e.configure_ephemeris_path(str(empty))
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", switch)
    with pytest.raises(EphemerisSourceError, match="configuration changed"):
        ephemeris._swisseph_planet_state("Sun", 2451545.0, julian_day_tt=2451545.0)


def test_whole_chart_lock_spans_physical_and_lahiri_passes(
    files, tmp_path, monkeypatch
):
    empty = tmp_path / "empty"
    empty.mkdir()
    start, done = threading.Event(), threading.Event()
    acquired = []
    actual = charts.native_lahiri_positions

    def between_passes(*args, **kwargs):
        start.set()
        assert done.wait(5)
        return actual(*args, **kwargs)

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

    monkeypatch.setattr(charts, "native_lahiri_positions", between_passes)
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        result = charts.build_core_chart_payload(
            build_astro_birth_info(**BIRTH), "chart13", zodiacal=1
        )
    finally:
        thread.join(6)
    assert acquired == [False] and not thread.is_alive()
    source = result["chart_profile"]["physical_ephemeris_source"]
    assert set(source["by_factor"]) == set(PHYSICAL_BODIES)
    assert all(row["model"] == "swieph" for row in source["by_factor"].values())


def test_explicit_base_fallback_does_not_discard_native_midpoint_layer(
    files, monkeypatch
):
    actual = ephemeris._swisseph_planet_state
    monkeypatch.setattr(
        ephemeris,
        "_swisseph_planet_state",
        lambda name, *a, **kw: None if name == "Neptune" else actual(name, *a, **kw),
    )
    result = service.calculate_germany_chart_analysis(**BIRTH)
    assert "error" not in result
    base = result["base_chart"]["chart_profile"]["physical_ephemeris_source"]
    native = result["midpoint_analysis"]["profile"]["physical_ephemeris_source"]
    assert (
        base["by_factor"]["Neptune"]["model"] == "fatebridge_approximate_orbital_model"
    )
    assert base["by_factor"]["Neptune"]["file_ids"] == []
    assert native["by_factor"]["Neptune"]["model"] == "swieph"
    assert result["midpoint_analysis"]["status"] == "computed"


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_chart13", None),
        ("astro_chart", "chart13"),
        ("astro_germany", None),
        ("astro_chart", "germany"),
    ],
)
def test_nominal_source_and_metadata_across_three_surfaces(
    files, tmp_path, monkeypatch, capsys, key, variant
):
    _, directory = files
    empty = tmp_path / "empty"
    empty.mkdir()
    spec = next(s for s in CATALOG if s.key == key)
    germany = key == "astro_germany" or variant == "germany"
    path = (
        "base_chart.chart_profile" if germany else "chart_profile"
    ) + ".physical_ephemeris_source"
    payload = {**BIRTH, "birth_time_uncertainty_minutes": 1.0}
    if variant:
        payload["chart_variant"] = variant
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

    if not germany:
        actual = service.build_core_chart_payload

        def change_after_nominal(*args, **kwargs):
            e.configure_ephemeris_path(str(directory))
            result = actual(*args, **kwargs)
            e.configure_ephemeris_path(str(empty))
            return result

        with monkeypatch.context() as patch:
            patch.setattr(service, "build_core_chart_payload", change_after_nominal)
            rest, protocol, code, cli = surfaces()
            assert rest.status_code == 503 and protocol.is_error and code == 1
            for error in (rest.json(), json.loads(protocol.content[0].text), cli):
                assert error["issues"] == [
                    {
                        "path": "runtime.ephemeris_data",
                        "code": "nominal_source_mismatch",
                    }
                ]
                assert (
                    error["error_code"] == "ephemeris_source_inconsistent"
                    and error["retryable"] is False
                )
                assert str(directory) not in json.dumps(error)
    e.configure_ephemeris_path(str(directory))
    rest, protocol, code, cli = surfaces()
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    sources = []
    for body in (rest.json(), protocol.structured_content, cli):
        for component in path.split("."):
            body = body[component]
        sources.append(body)
    assert sources[0] == sources[1] == sources[2]
    assert set(sources[0]["by_factor"]) == set(PHYSICAL_BODIES)
    assert all(row["model"] == "swieph" for row in sources[0]["by_factor"].values())
    assert (
        sources[0]["atomic_file_read_proven"] is False
        and sources[0]["accuracy_certified"] is False
    )
    assert str(directory) not in json.dumps(sources[0])
    Draft202012Validator(spec.output_model.model_json_schema()).validate(rest.json())
