"""Real uncompressed kernel, strict failures, source identity and transports."""

import asyncio
import hashlib
import json
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
from fatebridge.core.jpl_ephemeris import jpl_header
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from scripts.astrodice.audit_astrodice_kernel import angular_error_arcsec

FIXTURES = Path(__file__).parents[1] / "data/astrodice/tables"
KERNEL = "de441-j2000.eph"
SPEC = next(x for x in CATALOG if x.key == "otherbu")
INPUTS = {
    "planet": "Jupiter",
    "sign": "Aries",
    "house": 0,
    "date": "2000-01-01",
    "time": "12:00",
    "zone": "UTC",
    "gps_lat": 51.5,
    "gps_lon": 0,
}


@pytest.fixture
def jpl(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    kernel = tmp_path / KERNEL
    kernel.write_bytes((FIXTURES / KERNEL).read_bytes())
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", KERNEL)
    e.configure_ephemeris_path()
    try:
        yield kernel
    finally:
        # The tests also change these variables. Restore the whole shared
        # monkeypatch stack before restoring the runtime, in the same order.
        monkeypatch.undo()
        e.configure_ephemeris_path(previous if previous is not None else "")


def test_fixture_is_a_declared_unmodified_coefficient_subset():
    data = (FIXTURES / KERNEL).read_bytes()
    provenance = json.loads((FIXTURES / "de441-j2000.provenance.json").read_text())
    assert len(data) == provenance["fixture_bytes"] == 40720
    assert hashlib.sha256(data).hexdigest() == provenance["fixture_sha256"]
    assert provenance["complete_original_kernel"] is False
    assert (
        hashlib.sha256(data[16288:]).hexdigest()
        == provenance["source_record_subset"]["range_sha256"]
    )
    assert jpl_header(FIXTURES / KERNEL)["de_number"] == 441
    header = jpl_header(FIXTURES / KERNEL)
    assert header["time_scale"] == "TDB"
    raw_start, raw_end, _ = struct.unpack_from("<3d", data, 2652)
    assert header["start_julian_day_tdb"] == raw_start
    assert header["end_julian_day_tdb"] == raw_end
    assert "start_julian_day_tt" not in header
    assert "end_julian_day_tt" not in header
    assert "legacy_tt_range_fields" not in header


def test_uninspected_binding_does_not_inherit_the_native_clock_estimate(monkeypatch):
    from fatebridge.core.astro import physical_sources

    monkeypatch.setattr(
        physical_sources, "binding_distribution_version", lambda *args: "future-binding"
    )
    policy = physical_sources.jpl_time_scale_policy()
    assert policy["status"] == "unverified_native_version"
    assert policy["tt_tdb_conversion_applied"] is None
    assert policy["source_documented_maximum_difference_seconds"] is None


def test_jpl_satisfies_the_original_vector_threshold_at_j2000(jpl):
    fixture = json.loads((FIXTURES / "kernel-horizons.json").read_text())
    protocol = json.loads((FIXTURES / "kernel-protocol.json").read_text())
    flags = (
        e.swe.FLG_SWIEPH
        | e.swe.FLG_J2000
        | e.swe.FLG_EQUATORIAL
        | e.swe.FLG_XYZ
        | e.swe.FLG_TRUEPOS
        | e.swe.FLG_ICRS
        | e.swe.FLG_SPEED
    )
    for reference in fixture["references"]:
        row = next(x for x in reference["rows"] if x["jd_tt"] == 2451545.0)
        body = PLANET_SWISSEPH_IDS[reference["body"]]
        values, flag = e.ephemeris_call("calc", row["jd_tt"], body, flags)
        assert e.ephemeris_model_from_retflag(flag) == "jpl"
        assert (
            max(abs(a - b) for a, b in zip(values[:3], row["position_au"]))
            <= protocol["component_tolerance_au"]
        )
        assert (
            angular_error_arcsec(values[:3], row["position_au"])
            <= protocol["angular_tolerance_arcsec"]
        )


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_actual_context_exposes_jpl_identity_without_changing_symbols(jpl, zodiacal):
    plain = build_otherbu_result(planet="Jupiter", sign="Aries", house=0)
    result = build_otherbu_result(**INPUTS, zodiacal=zodiacal)
    profile = result["chart"]["params"]["chart_profile"]
    assert profile["ephemeris_model"] == "jpl"
    source = profile["physical_ephemeris_source"]
    assert not source["has_unidentified_sources"]
    assert len(source["files"]) == 1
    file = source["files"][0]
    assert file["de_number"] == 441
    assert file["sha256"] == hashlib.sha256(jpl.read_bytes()).hexdigest()
    assert file["start_julian_day_tdb"] == 2451504.5
    assert file["end_julian_day_tdb"] == 2451600.5
    assert file["matches_packaged_manifest"] is False
    policy = source["time_scale_policy"]
    assert policy["native_api_time_scale"] == "TT"
    assert policy["raw_header_time_scale"] == "TDB"
    assert policy["tt_tdb_conversion_applied"] is False
    assert policy["source_documented_maximum_difference_seconds"] == 0.002
    motion_factors = {
        "Moon_motion_geometric",
        "Moon_motion_observer_barycentric",
        "Moon_motion_retarded_barycentric",
        "Moon_motion_source_preaberration",
        "Moon_motion_source_apparent_fixed",
        "Moon_motion_observer_restored_pre",
        "Moon_motion_observer_restored_app",
        "Moon_motion_observer_restored_earth",
    }
    fixed = profile["longitude_motion"]["lunar_light_time"][
        "fixed_frame_source_derivative"
    ]
    assert fixed["status"] == "applied"
    assert fixed["selected_stencil"] == "analytic_jpl_source"
    assert fixed["sample_count"] == 0
    assert fixed["acceleration_steps_days"] == []
    assert fixed["acceleration_difference_au_per_day2"] is None
    assert fixed["observer_derivative_disagreement_arcsec_per_day"] is None
    assert (
        fixed["analytic_observer_source"]["record_sha256"]
        == hashlib.sha256(jpl.read_bytes()[3 * 8144 : 4 * 8144]).hexdigest()
    )
    assert (
        max(
            fixed["fixed_observer_rotation"][
                "state_reproduction_errors_au_or_au_per_day"
            ]
        )
        <= 2e-13
    )
    assert set(source["by_factor"]) == set(PLANET_SWISSEPH_IDS) - {"North Node"}
    assert (
        set(profile["longitude_motion"]["lunar_light_time"]["source_contexts"])
        == motion_factors
    )
    for context in profile["longitude_motion"]["lunar_light_time"][
        "source_contexts"
    ].values():
        assert context["model"] == "jpl"
        assert context["file_ids"] == [file["id"]]
    assert all(x["model"] == "jpl" for x in source["by_factor"].values())
    assert source["accuracy_certified"] is False
    for key in ("symbolic_details", "interpretation", "rule_trace", "rulesets"):
        assert result[key] == plain[key]


@pytest.mark.parametrize("name", ["../private.eph", "a" * 256, "has space", ".."])
def test_ambiguous_or_truncated_names_are_rejected(jpl, monkeypatch, name):
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", name)
    with pytest.raises(EphemerisSourceError) as error:
        build_otherbu_result(**INPUTS)
    assert error.value.reason == "jpl_filename_invalid"


@pytest.mark.parametrize("problem", ["missing", "truncated", "out_of_range"])
def test_explicit_jpl_never_downgrades_to_an_approximation(jpl, monkeypatch, problem):
    inputs = dict(INPUTS)
    if problem == "missing":
        monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing.eph")
    elif problem == "truncated":
        jpl.write_bytes(jpl.read_bytes()[:-8])
    else:
        inputs["date"] = "2005-01-01"
    with pytest.raises(EphemerisSourceError) as error:
        build_otherbu_result(**inputs)
    assert error.value.reason in {
        "jpl_file_unavailable",
        "jpl_kernel_invalid",
        "jpl_native_fallback",
        "jpl_native_failed",
    }


def test_file_change_and_configuration_change_are_detected(jpl, monkeypatch):
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    trace = PhysicalEphemerisTrace()
    trace.observe("Sun", "jpl")
    data = bytearray(jpl.read_bytes())
    data[80] ^= 1
    jpl.write_bytes(data)
    with pytest.raises(EphemerisSourceError) as error:
        trace.finish()
    assert error.value.reason == "changed_during"
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    with pytest.raises(EphemerisSourceError) as error:
        trace.finish()
    assert error.value.reason == "physical_configuration_changed"


def test_strict_mode_preserves_keyword_flags_and_rejects_analytical_request(jpl):
    _, flags = e.ephemeris_call(
        "calc", 2451545.0, e.swe.NEPTUNE, flags=e.swe.FLG_SWIEPH | e.swe.FLG_SPEED
    )
    assert flags & e.swe.FLG_JPLEPH and flags & e.swe.FLG_SPEED
    assert not flags & e.swe.FLG_SWIEPH
    with pytest.raises(EphemerisSourceError) as error:
        e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_MOSEPH)
    assert error.value.reason == "jpl_mixed_request"


def test_disabling_explicit_mode_restores_default_model_selection(jpl, monkeypatch):
    e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_SWIEPH)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE")
    _, flag = e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_SWIEPH)
    assert e.ephemeris_model_from_retflag(flag) == "moshier"


def test_dice_faces_without_sky_context_do_not_require_a_jpl_file(jpl, monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing.eph")
    result = build_otherbu_result(planet="Jupiter", sign="Aries", house=0)
    assert result["chart"] is None
    assert result["diceChart"]["params"]["chartKind"] == "symbolic_whole_sign_diagram"


def test_worker_calls_restore_selected_kernel_after_foreign_changes(jpl):
    def calculate(_):
        # Third-party integrations participate in the shared managed lock.
        # The next managed call must restore the explicitly selected kernel.
        with e.preserve_ephemeris_path():
            e.swe.set_jpl_file("missing.eph")
        return e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_SWIEPH)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(calculate, range(9)))
    assert all(flag & e.swe.FLG_JPLEPH for _, flag in results)
    assert all(values == results[0][0] for values, _ in results)


@pytest.mark.parametrize("order", ["<", ">"])
def test_header_reader_supports_both_direct_access_byte_orders(tmp_path, order):
    data = bytearray((FIXTURES / KERNEL).read_bytes())
    if order == ">":
        for offset, fmt in ((2652, "3d"), (2680, "2d"), (2696, "36i"), (2840, "4i")):
            values = struct.unpack_from("<" + fmt, data, offset)
            struct.pack_into(">" + fmt, data, offset, *values)
    path = tmp_path / "header-only-synthetic.eph"
    path.write_bytes(data)
    assert jpl_header(path)["start_julian_day_tdb"] == 2451504.5


def test_jpl_source_projects_identically_across_three_transports(
    jpl, capsys, monkeypatch
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = [
        "chart.params.chart_profile.ephemeris_model",
        "chart.params.chart_profile.physical_ephemeris_source",
        "chart.params.chart_profile.longitude_motion.lunar_light_time.fixed_frame_source_derivative",
    ]
    with TestClient(api.app) as client:
        response = client.post(
            SPEC.rest_path,
            json=INPUTS,
            params={"fields": fields, "strict_fields": True},
        )
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)
    assert expected["chart"]["params"]["chart_profile"]["ephemeris_model"] == "jpl"
    policy = expected["chart"]["params"]["chart_profile"]["physical_ephemeris_source"][
        "time_scale_policy"
    ]
    assert policy["raw_header_time_scale"] == "TDB"
    assert policy["tt_tdb_conversion_applied"] is False

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **INPUTS,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            return result.structured_content

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in INPUTS.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        result.pop("run_metadata")
    assert expected == native == cli


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "out_of_range",
        "native_unavailable",
        "initialization_error",
        "jpl_kinematics_invalid",
        "jpl_kinematics_outside_source",
        "jpl_kinematics_frame_mismatch",
    ],
)
def test_jpl_failure_is_preserved_across_three_transports(
    jpl, capsys, monkeypatch, problem
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(INPUTS)
    if problem == "missing":
        monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "missing.eph")
    elif problem == "out_of_range":
        inputs["date"] = "2005-01-01"
    elif problem == "native_unavailable":
        from fatebridge.core.astro import runtime

        monkeypatch.setattr(runtime, "swe", None)
        # Whole-sign geometry is supported offline, so only the explicit JPL
        # requirement must reject this context (not the old house-system gate).
        inputs["hsys"] = 0
        with pytest.raises(ImportError, match="explicitly selected JPL mode"):
            build_otherbu_result(**inputs)
    elif problem.startswith("jpl_kinematics"):
        from fatebridge.core.astro import jpl_kinematics

        def fail_source(*args, **kwargs):
            raise EphemerisSourceError(problem)

        monkeypatch.setattr(jpl_kinematics, "source_kinematics", fail_source)
    else:

        def fail(_):
            raise RuntimeError("private native initialization detail")

        monkeypatch.setattr(e.swe, "set_jpl_file", fail)
    with TestClient(api.app) as client:
        response = client.post(SPEC.rest_path, json=inputs)
    assert response.status_code == 503
    expected = response.json()
    assert expected["error_code"] == (
        "dependency_missing"
        if problem == "native_unavailable"
        else "ephemeris_source_inconsistent"
    )
    assert expected["retryable"] is False
    if problem != "native_unavailable":
        assert expected["issues"][0]["path"] == "runtime.ephemeris_data"
    assert "chart" not in expected
    assert str(jpl.parent) not in json.dumps(expected)
    assert "private native initialization detail" not in json.dumps(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool("otherbu", inputs, raise_on_error=False)
            assert result.is_error
            return json.loads(result.content[0].text)

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 1
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        assert result["error_code"] == expected["error_code"]
        assert result.get("issues") == expected.get("issues")
        assert result["retryable"] is False
