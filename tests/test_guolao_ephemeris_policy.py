"""Real selected-kernel coverage and provenance for Guolao reference skies."""

import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.fixed_star_paths import fixed_star_search_path
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError

FIXTURES = Path(__file__).parent / "fixtures"
KERNEL = "guolao-de441-j2000.eph"
RAW_DATA = Path(__file__).parent / "data/guolao"
BIRTH = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=0,
    birth_latitude=0,
)
AS_OF = "2000-01-02T12:00:00+00:00"


def test_extended_fixture_keeps_original_records_and_required_scan_windows():
    from fatebridge.core.almanac import _solar_term_search_anchor_utc
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.core.jpl_ephemeris import jpl_header

    data = (RAW_DATA / KERNEL).read_bytes()
    proof = json.loads((RAW_DATA / "guolao-de441-j2000.provenance.json").read_text())
    assert len(data) == proof["fixture_bytes"] == 162880
    assert hashlib.sha256(data).hexdigest() == proof["fixture_sha256"]
    part = next(p for p in proof["download_parts"] if p["part"] == "coefficients")
    assert hashlib.sha256(data[16288:]).hexdigest() == part["sha256"]
    old = (FIXTURES / "human-design-de441-j2000.eph").read_bytes()
    assert (
        hashlib.sha256(old).hexdigest()
        == "3be5b3e84b7d0fcf7507d0f37b4097ab573550b5925e77981828b962c1315824"
    )
    assert data[16288 : 16288 + 6 * 8144] == old[16288:]
    assert proof["modified_header_byte_ranges"] == [[2652, 2667]]
    assert proof["coefficients_unmodified"] and not proof["complete_original_kernel"]
    header = jpl_header(RAW_DATA / KERNEL)
    assert header["start_julian_day_tdb"] == 2451408.5
    assert header["end_julian_day_tdb"] == 2451984.5
    for i in range(24):
        anchor = ephemeris_time(_solar_term_search_anchor_utc(2000, i)).jd_tt
        assert header["start_julian_day_tdb"] <= anchor - 30
        assert anchor + 30 <= header["end_julian_day_tdb"]


@pytest.fixture
def selected(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    target = tmp_path / KERNEL
    shutil.copyfile(RAW_DATA / KERNEL, target)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", KERNEL)
    e.swe.close()
    e.configure_ephemeris_path()
    try:
        yield target
    finally:
        monkeypatch.undo()
        e.swe.close()
        e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.mark.parametrize("sidereal,observer", [(0, True), (1, True), (1, False)])
def test_all_seven_physical_bodies_and_frames_use_selected_kernel(
    selected, sidereal, observer
):
    raw = guolao.positions(
        build_astro_birth_info(**BIRTH),
        zodiacal=sidereal,
        observer_geometry=observer,
    )
    proof = raw["ephemeris_provenance"]
    assert raw["models"] == ["jpl"]
    assert proof["physical_backend_policy"] == "strict_jpl"
    assert proof["physical_model_scope"] == "seven_bodies_ecliptic_and_equatorial"
    assert len(proof["by_body"]) == 7
    with e.preserve_ephemeris_path():
        e.swe.set_jpl_file(KERNEL)
        for name, state in raw["states"].items():
            body = getattr(e.swe, name.upper())
            xyz, flag = e.swe.calc(
                raw["julian_day_tt"], body, e.swe.FLG_JPLEPH | e.swe.FLG_SPEED
            )
            eq, eq_flag = e.swe.calc(
                raw["julian_day_tt"],
                body,
                e.swe.FLG_JPLEPH | e.swe.FLG_SPEED | e.swe.FLG_EQUATORIAL,
            )
            assert state["longitude"] == xyz[0]
            assert state["latitude"] == xyz[1]
            assert state["longitude_speed_native"] == xyz[3]
            assert (
                state["longitude_speed_reference_frame"] == "tropical_ecliptic_of_date"
            )
            assert state["right_ascension"] == eq[0]
            assert state["declination"] == eq[1]
            assert proof["by_body"][name] == {
                "ecliptic_model": "jpl",
                "equatorial_model": "jpl",
                "ecliptic_return_flags": flag,
                "equatorial_return_flags": eq_flag,
            }
        if sidereal:
            e.swe.set_sid_mode(e.swe.SIDM_LAHIRI, 0, 0)
            _, ayanamsha = e.swe.get_ayanamsa_ex(raw["julian_day_tt"], e.swe.FLG_JPLEPH)
            assert raw["ayanamsha"] == ayanamsha
    assert proof["nonphysical_factor_models"] == {
        "罗": "mean_lunar_node",
        "孛": "mean_lunar_apogee",
        "计": "opposite_mean_lunar_node",
        "炁": "horosa_linear_fit_not_classical_calibrated",
    }
    assert not proof["absolute_astronomical_accuracy_certified"]


def test_distance_stars_and_actual_earth_observer_honor_selected_kernel(
    selected, monkeypatch
):
    raw = guolao.positions(build_astro_birth_info(**BIRTH))
    proof = raw["ephemeris_provenance"]
    assert proof["fixed_star_observer_ephemeris_model"] == "jpl"
    assert proof["fixed_star_observer_return_flags"] & e.swe.FLG_JPLEPH
    assert all(f & e.swe.FLG_JPLEPH for f in proof["fixed_star_native_return_flags"])
    with e.preserve_ephemeris_path():
        with fixed_star_search_path(guolao.DATA, str(selected.parent)) as search:
            with monkeypatch.context() as scoped:
                scoped.setenv("SE_EPHE_PATH", search)
                e.swe.close()
                e.swe.set_ephe_path(search)
                e.swe.set_jpl_file(KERNEL)
                try:
                    for i, boundary in enumerate(raw["boundaries"]):
                        xyz, _, flag = e.swe.fixstar2(
                            f"FBJ{i:02}",
                            raw["julian_day_tt"],
                            e.swe.FLG_JPLEPH | e.swe.FLG_EQUATORIAL,
                        )
                        assert flag & e.swe.FLG_JPLEPH
                        assert boundary["right_ascension"] == xyz[0] % 360
                finally:
                    e.swe.close()
    assert os.environ["SE_EPHE_PATH"] == str(selected.parent)
    assert e.configured_ephemeris_path() == str(selected.parent)


def test_automatic_empty_directory_keeps_star_echo_separate_from_earth_model(
    selected, monkeypatch
):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    raw = guolao.positions(build_astro_birth_info(**BIRTH))
    proof = raw["ephemeris_provenance"]
    assert raw["models"] == ["moshier"]
    assert proof["physical_backend_policy"] == "auto"
    assert proof["fixed_star_observer_ephemeris_model"] == "moshier"
    assert proof["fixed_star_observer_return_flags"] & e.swe.FLG_MOSEPH
    assert all(f & e.swe.FLG_SWIEPH for f in proof["fixed_star_native_return_flags"])
    assert proof["nonphysical_return_flags"]["罗"]["ecliptic"] & e.swe.FLG_SWIEPH


@pytest.mark.parametrize("failure", ["missing", "truncated", "outside"])
def test_selected_source_failures_are_not_replaced_by_moshier(selected, failure):
    birth = dict(BIRTH)
    if failure == "missing":
        selected.unlink()
    elif failure == "truncated":
        selected.write_bytes(selected.read_bytes()[:200])
    else:
        birth["birth_year"] = 2020
    with pytest.raises(EphemerisSourceError):
        guolao.positions(build_astro_birth_info(**birth))


def test_shorter_fixture_still_rejects_full_year_after_wider_year_was_cached(selected):
    spec = next(s for s in CATALOG if s.key == "astro_guolao")
    request = spec.request_model.model_validate({**BIRTH, "use_true_solar_time": False})
    result = execute_tool(spec, request, include_metadata=False)
    assert "error" not in result
    selected.write_bytes((FIXTURES / "human-design-de441-j2000.eph").read_bytes())
    e.swe.close()
    result = execute_tool(spec, request, include_metadata=False)
    assert result["error_code"] == "ephemeris_source_inconsistent"
    assert result["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "jpl_native_fallback"}
    ]


def test_star_failure_restores_operator_path_and_strict_kernel(selected, monkeypatch):
    before = e.configured_ephemeris_path()

    def fail(*args, **kwargs):
        raise e.swe.Error("fixture star failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(e.swe, "fixstar2", fail)
        with pytest.raises(EphemerisSourceError, match="Native calculation failed"):
            guolao.positions(build_astro_birth_info(**BIRTH))
    assert e.configured_ephemeris_path() == before
    assert os.environ["SE_EPHE_PATH"] == str(selected.parent)
    assert os.environ["FATEBRIDGE_JPL_FILE"] == KERNEL
    _, flag = e.ephemeris_call("calc", 2451545.0, e.swe.SUN)
    assert flag & e.swe.FLG_JPLEPH


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("sidereal,target", [(0, None), (1, None), (1, AS_OF)])
def test_strict_source_provenance_agrees_across_rest_mcp_cli(
    selected, monkeypatch, capsys, tool, sidereal, target
):
    spec = next(s for s in CATALOG if s.key == tool)
    payload = {**BIRTH, "use_true_solar_time": False, "zodiacal": sidereal}
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    if target is not None:
        payload["analysis_datetime"] = target
    fields = [
        "guolao.profile.ephemeris_provenance",
        "guolao.profile.longitude_motion",
        "guolao.bodies",
        "guolao.timing",
    ]
    options = dict(
        as_of=AS_OF,
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(protocol())
    assert not native.is_error, native
    args = [spec.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in x.items() if k != "run_metadata"}
        for x in [rest.json(), native.structured_content, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    for body in bodies:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        proof = body["guolao"]["profile"]["ephemeris_provenance"]
        assert proof["physical_backend_policy"] == "strict_jpl"
        assert proof["fixed_star_observer_ephemeris_model"] == "jpl"
        assert all(p["ecliptic_model"] == "jpl" for p in proof["by_body"].values())
        motion = body["guolao"]["profile"]["longitude_motion"]
        assert motion["reference_frame"] == "tropical_ecliptic_of_date"
        assert set(motion["physical_ephemeris_source"]["by_factor"]) == set(guolao.CN)
        for state in body["guolao"]["bodies"]:
            if state["id"] in guolao.CN:
                assert "longitude_speed_native" in state
                assert (
                    state["longitude_speed_reference_frame"]
                    == "tropical_ecliptic_of_date"
                )
        if target:
            assert body["guolao"]["timing"]["profile"]["ephemeris_provenance"] == proof
            target_motion = body["guolao"]["timing"]["profile"]["longitude_motion"]
            assert target_motion["reference_frame"] == motion["reference_frame"]
            assert set(target_motion["physical_ephemeris_source"]["by_factor"]) == set(
                guolao.CN
            )


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("failure", ["missing", "outside"])
def test_selected_source_errors_agree_across_rest_mcp_cli(
    selected, monkeypatch, capsys, tool, failure
):
    spec = next(s for s in CATALOG if s.key == tool)
    payload = {**BIRTH, "use_true_solar_time": False}
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    if failure == "missing":
        selected.unlink()
    else:
        payload["birth_year"] = 2020
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(spec.rest_path, json=payload)
    assert rest.status_code == 503

    async def protocol():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name, payload, raise_on_error=False
            )
            assert result.is_error
            return json.loads(result.content[0].text)

    native = asyncio.run(protocol())
    args = [spec.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    capsys.readouterr()
    assert run(args) == 1
    cli = json.loads(capsys.readouterr().out)
    for body in [rest.json(), native, cli]:
        assert body["error_code"] == "ephemeris_source_inconsistent"
        assert body["retryable"] is False
        assert body["issues"] == rest.json()["issues"]
        assert "guolao" not in body
        assert str(selected.parent) not in json.dumps(body)
