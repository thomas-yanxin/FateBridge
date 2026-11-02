"""Native-source regression and an independent local rate calculation.

These tests concern rates of the selected analytical positions. They cannot
establish that the analytical positions match a modern physical ephemeris.
"""

import asyncio
import json
import math

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core import guolao
from fatebridge.core.astro import moshier_motion as motion
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError


@pytest.fixture
def analytical(tmp_path, monkeypatch):
    previous = e.configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    e.swe.close()
    e.configure_ephemeris_path(str(tmp_path))
    try:
        yield tmp_path
    finally:
        monkeypatch.undo()
        e.swe.close()
        e.configure_ephemeris_path(previous or "")


def birth_at_tt(jd):
    moment = datetime_from_tt(jd)
    return build_astro_birth_info(
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
    )


def native_longitude(jd, body):
    swe = e.swe
    coordinates, returned = runtime.ephemeris_call(
        "calc", jd, motion.PLANET_SWISSEPH_IDS[body], swe.FLG_MOSEPH | swe.FLG_SPEED
    )
    assert runtime.ephemeris_model_from_retflag(returned) == "moshier"
    return coordinates


def fourth_order_rate(jd, body, center, h):
    # Different order/node geometry from the production sixth-order/LS fits.
    offsets = (-2, -1, 1, 2)
    values = [
        math.remainder(native_longitude(jd + k * h, body)[0] - center, 360)
        for k in offsets
    ]
    return math.fsum(w * v for w, v in zip((1, -8, 8, -1), values)) / (12 * h)


@pytest.mark.parametrize("year", [2000, 2027, 2047, 2077])
def test_real_native_moon_uses_forward_biased_nonbinary_geometric_stencil(
    analytical, year
):
    swe = e.swe
    jd = swe.julday(year, 1, 1 if year == 2000 else 15, 12)
    h = 0.00005  # MOON_SPEED_INTV in the inspected source, not a fitted step.
    flags = (
        swe.FLG_MOSEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_TRUEPOS
        | swe.FLG_NONUT
        | swe.FLG_J2000
    )
    states = [
        runtime.ephemeris_call("calc", jd + delta, swe.MOON, flags)[0]
        for delta in (0, h, -h)
    ]
    center, plus, minus = states
    reconstructed = [
        (2 * ((plus[i] + minus[i]) / 2 - center[i]) + (plus[i] - minus[i]) / 2) / h
        for i in range(3)
    ]
    earth = runtime.ephemeris_call("calc", jd, swe.EARTH, flags | swe.FLG_HELCTR)[0]
    roundoff = 8 * math.ulp(max(1.0, *(abs(v) for v in earth[:3]))) / h
    assert reconstructed == pytest.approx(center[3:], abs=roundoff, rel=0)
    assert jd + h - jd != h
    assert jd - (jd - h) != h


@pytest.mark.parametrize("year", [1900, 2000, 2020, 2077])
@pytest.mark.parametrize("body", sorted(guolao.CN))
def test_delivered_rate_matches_independent_local_position_derivative(
    analytical, year, body
):
    jd = e.swe.julday(year, 1, 15, 12)
    raw = guolao.positions(birth_at_tt(jd), observer_geometry=False)
    assert abs(raw["julian_day_tt"] - jd) < 1e-9
    state = raw["states"][body]
    native = native_longitude(jd, body)
    assert state["longitude_speed_native"] == native[3]
    assert state["longitude"] == native[0]
    coarse = fourth_order_rate(jd, body, native[0], 2.0**-7)
    fine = fourth_order_rate(jd, body, native[0], 2.0**-8)
    extrapolated = fine + (fine - coarse) / 15
    assert abs(state["longitude_speed"] - extrapolated) * 3600 < 0.002
    assert (
        state["longitude_speed"]
        == state["longitude_speed_native"]
        + state.get("longitude_speed_rotation_correction", 0.0)
        + state["longitude_speed_position_derivative_correction"]
    )
    policy = raw["longitude_motion"]["complete_position_derivatives"][
        body + ":tropical"
    ]
    assert policy["method_id"] == motion.METHOD_ID
    assert policy["status"] == "applied"
    chosen = policy["attempts"][-1]
    assert chosen["consecutive_converged_pairs"] >= 2
    assert chosen["directional_checks"][-1]["passed"]
    assert "physical-model error" in raw["longitude_motion"]["scope"]


@pytest.mark.parametrize("problem", ["frame", "model", "nonfinite"])
def test_moshier_probe_contract_failures_remain_errors(
    analytical, monkeypatch, problem
):
    jd = 2451545.0
    coordinates = native_longitude(jd, "Moon")
    original = runtime.ephemeris_call

    def perturb(operation, *args, **kwargs):
        value = original(operation, *args, **kwargs)
        if operation == "calc":
            state, flags = value
            if problem == "frame":
                return state, flags | e.swe.FLG_TRUEPOS
            if problem == "model":
                return state, (flags & ~e.swe.FLG_MOSEPH) | e.swe.FLG_SWIEPH
            return (math.nan, *state[1:]), flags
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", perturb)
    with pytest.raises(EphemerisSourceError):
        motion.complete_moshier_longitude_rate("Moon", jd, coordinates)


def test_unknown_version_never_receives_a_moshier_correction(monkeypatch):
    monkeypatch.setattr(motion, "binding_distribution_version", lambda *a: "future")
    rate, policy = motion.complete_moshier_longitude_rate(
        "Moon", 2451545.0, (0.0, 0.0, 1.0, 13.0)
    )
    assert rate is None and policy["reason"] == "unverified_native_version"


def test_nonconvergence_stays_explicit_and_does_not_copy_native_rate(
    analytical, monkeypatch
):
    jd = 2451545.0
    coordinates = native_longitude(jd, "Moon")
    original = runtime.ephemeris_call

    def singular(operation, *args, **kwargs):
        value = original(operation, *args, **kwargs)
        if operation == "calc":
            state, flags = value
            changed = list(state)
            x = args[0] - jd
            changed[0] = coordinates[0] + (x * math.log(abs(x)) if x else 0)
            return changed, flags
        return value

    monkeypatch.setattr(runtime, "ephemeris_call", singular)
    rate, policy = motion.complete_moshier_longitude_rate("Moon", jd, coordinates)
    assert rate is None and policy["status"] == "not_applied"
    assert policy["reason"] == "position_motion_not_converged"
    assert len(policy["attempts"]) == 2
    assert all(row["status"] == "not_converged" for row in policy["attempts"])


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize("target", [None, "2000-01-02T12:00:00+00:00"])
def test_moshier_native_and_corrected_rates_roundtrip_actual_interfaces(
    analytical, monkeypatch, capsys, tool, target
):
    spec = next(s for s in CATALOG if s.key == tool)
    payload = dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        use_true_solar_time=False,
    )
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    if target:
        payload["analysis_datetime"] = target
    fields = [
        "guolao.bodies",
        "guolao.profile.ephemeris_models",
        "guolao.profile.longitude_motion.scope",
    ]
    if target:
        fields += [
            "guolao.timing.transit_bodies",
            "guolao.timing.profile.ephemeris_models",
        ]
    options = dict(
        as_of="2000-01-02T12:00:00+00:00",
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
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    assert not native.is_error, native
    args = [spec.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        options["as_of"],
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
    results = [
        {key: value for key, value in body.items() if key != "run_metadata"}
        for body in (rest.json(), native.structured_content, cli)
    ]
    assert results[0] == results[1] == results[2]
    for body in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        chart = body["guolao"]
        assert chart["profile"]["ephemeris_models"] == ["moshier"]
        assert "physical-model error" in chart["profile"]["longitude_motion"]["scope"]
        layers = [(chart, "bodies")]
        if target:
            layers.append((chart["timing"], "transit_bodies"))
        for layer, members in layers:
            assert layer["profile"]["ephemeris_models"] == ["moshier"]
            for state in layer[members]:
                if state["id"] in guolao.CN:
                    assert "longitude_speed_native" in state
                    assert "longitude_speed_position_derivative_correction" in state
