"""Solar-input prerequisite: native meaning before self-consistent inversion.

The original native guards remain. Solar-input admission is now exercised
alongside the separately declared Guolao input convention, not a complete port.
"""

import asyncio
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.astro import birth_clock as clock
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroGuolaoRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.guolao.test_guolao_native_frames import fixed_moshier  # noqa: F401

FIXTURE = Path(__file__).parents[1] / "fixtures/guolao-solar-input-preflight-v1"
JPL = FIXTURE.parent / "guolao-apparent-clock-v1"
FORMS = json.loads(
    (
        Path(__file__).parents[1] / "data/guolao/solar_clock_frame_forms.json"
    ).read_bytes()
)
SWISS = json.loads(
    (
        Path(__file__).parents[1] / "data/guolao/raw_swiss_clock_vectors.json"
    ).read_bytes()
)
CASE = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_longitude=10,
    birth_latitude=53.55,
)


def invoke(module=clock):
    time = ephemeris_time(datetime(2000, 1, 1, 12, tzinfo=timezone.utc))
    return module._sun_clock(time.jd_ut1, _julian_day_tt=time.jd_tt)


@pytest.mark.parametrize("form", FORMS)
def test_actual_native_frame_rejects_before_eot(monkeypatch, fixed_moshier, form):
    native = clock.runtime.ephemeris_call

    def alternate(operation, *args, **kwargs):
        if (
            operation == "calc"
            and args[1] == clock.runtime.swe.SUN
            and args[2] & clock.runtime.swe.FLG_EQUATORIAL
        ):
            args = list(args)
            args[2] = (
                (args[2] & ~clock.runtime.swe.FLG_EQUATORIAL)
                if form == "ecliptic"
                else args[2] | getattr(clock.runtime.swe, form)
            )
        return native(operation, *args, **kwargs)

    clock.runtime.swe.set_topo(0, 0, 0)
    clock.runtime.swe.set_sid_mode(clock.runtime.swe.SIDM_LAHIRI, 0, 0)
    monkeypatch.setattr(clock.runtime, "ephemeris_call", alternate)
    with pytest.raises(EphemerisSourceError, match="coordinate|坐标") as error:
        invoke()
    assert error.value.reason == "coordinate_contract_changed"


@pytest.mark.parametrize("row", SWISS, ids=[row["form"] for row in SWISS])
def test_all13_saved_real_swiss_frames_reject_before_source_or_clock_consumption(
    monkeypatch, fixed_moshier, row
):
    native = clock.runtime.ephemeris_call
    held = row["actual_native_calls"][0]

    def returned(operation, *args, **kwargs):
        if operation == "calc" and args[1] == clock.runtime.swe.SUN:
            return tuple(held["coordinates"]), held["returned_flags"]
        return native(operation, *args, **kwargs)

    monkeypatch.setattr(clock.runtime, "ephemeris_call", returned)
    with pytest.raises(EphemerisSourceError) as error:
        invoke()
    assert error.value.reason == "coordinate_contract_changed"


@pytest.mark.parametrize(
    "change",
    ["nan_ra", "nan_declination", "negative_distance", "short", "negative_flags"],
)
def test_invalid_native_values_reject_without_constructing_a_clock(
    monkeypatch, fixed_moshier, change
):
    native = clock.runtime.ephemeris_call

    def corrupt(operation, *args, **kwargs):
        result = native(operation, *args, **kwargs)
        if operation == "calc" and args[1] == clock.runtime.swe.SUN:
            coords, flag = result
            coords = list(coords)
            if change == "short":
                coords = coords[:2]
            elif change == "negative_flags":
                flag = -1
            elif change == "negative_distance":
                coords[2] = -1
            else:
                coords[0 if change == "nan_ra" else 1] = math.nan
            return tuple(coords), flag
        return result

    monkeypatch.setattr(clock.runtime, "ephemeris_call", corrupt)
    with pytest.raises(EphemerisSourceError):
        invoke()


@pytest.mark.parametrize(
    "hours", [-1, 24, math.inf, math.nan, None, "invalid", 10**1000]
)
def test_sidereal_result_requires_finite_hours_in_declared_range(
    monkeypatch, fixed_moshier, hours
):
    native = clock.runtime.ephemeris_call
    monkeypatch.setattr(
        clock.runtime,
        "ephemeris_call",
        lambda op, *a, **k: hours if op == "sidtime" else native(op, *a, **k),
    )
    with pytest.raises(EphemerisSourceError) as error:
        invoke()
    assert error.value.reason == "coordinate_values_unavailable"


def test_provider_source_error_is_preserved_instead_of_recategorized_as_a_value(
    monkeypatch, fixed_moshier
):
    native = clock.runtime.ephemeris_call
    failure = EphemerisSourceError("physical_configuration_changed")

    def fail(operation, *args, **kwargs):
        if operation == "sidtime":
            raise failure
        return native(operation, *args, **kwargs)

    monkeypatch.setattr(clock.runtime, "ephemeris_call", fail)
    with pytest.raises(EphemerisSourceError) as caught:
        invoke()
    assert caught.value is failure


@pytest.mark.parametrize("index", [0, 1])
def test_existing_independent_jpl_solar_phase_reference_keeps_its_original_tolerance(
    fixed_moshier, index
):
    ref = json.loads((JPL / "reference.json").read_text())

    def rows(name):
        raw = (
            json.loads((JPL / name).read_text())["result"]
            .split("$$SOE\n")[1]
            .split("$$EOE")[0]
        )
        return list(csv.reader(io.StringIO(raw)))

    sun, sidereal = (
        rows("geocentric_sun.json")[index],
        rows("greenwich_sidereal.json")[index],
    )
    c = ref["boundary_case"]
    lon = c["birth_longitude"]
    expected = (
        Fraction(12)
        + Fraction(sidereal[3].strip())
        + (Fraction(lon) - Fraction(sun[3].strip())) / 15
    ) % 24
    moment = datetime(
        c["birth_year"],
        c["birth_month"],
        c["birth_day"],
        c["birth_hour"],
        index,
        tzinfo=timezone.utc,
    )
    result = clock.solar_clock_components(moment, lon, "local_apparent_solar")
    actual = ((result["julian_day_solar"] + Fraction(1, 2)) % 1) * 24
    error = (actual - expected + 12) % 24 - 12
    assert abs(float(error) * 3600) < ref["external_solar_clock_tolerance_seconds"]


@pytest.mark.parametrize(
    "tool,basis,failed",
    [
        pytest.param(
            tool,
            basis,
            failed,
            marks=(
                pytest.mark.native_engine_fault
                if tool == "astro_india" and failed
                else []
            ),
        )
        for tool in ["astro_chart", "astro_chart13", "astro_india", "astro_germany"]
        for basis, failed in [
            ("local_mean_solar", False),
            ("local_apparent_solar", False),
            ("local_apparent_solar", True),
        ]
    ],
)
def test_actual_three_surfaces_use_same_conversion_and_full_source_error_mapping(
    monkeypatch, fixed_moshier, capsys, record_testsuite_property, tool, basis, failed
):
    if failed:
        native = clock.runtime.ephemeris_call

        def radians(operation, *args, **kwargs):
            if (
                operation == "calc"
                and args[1] == clock.runtime.swe.SUN
                and args[2] & clock.runtime.swe.FLG_EQUATORIAL
            ):
                args = list(args)
                args[2] |= clock.runtime.swe.FLG_RADIANS
            return native(operation, *args, **kwargs)

        monkeypatch.setattr(clock.runtime, "ephemeris_call", radians)
    spec = next(s for s in CATALOG if s.key == tool)
    payload = {**CASE, "birth_clock_basis": basis}
    if tool == "astro_chart":
        payload["chart_variant"] = "chart13"
    options = dict(
        as_of="2026-10-25T00:00:00+08:00",
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
        params={
            k: str(v).lower() if isinstance(v, bool) else str(v)
            for k, v in options.items()
        },
    )
    assert rest.status_code == (503 if failed else 200), rest.text

    async def protocol():
        async with Client(create_mcp_app()) as client:
            r = await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )
            assert r.is_error is failed
            return json.loads(r.content[0].text) if failed else r.structured_content

    mcp = asyncio.run(protocol())
    args = [spec.tool_name]
    for k, v in payload.items():
        args.extend(["--" + k.replace("_", "-"), str(v)])
    args.extend(
        [
            "--as-of",
            options["as_of"],
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ]
    )
    capsys.readouterr()
    assert run(args) == int(failed)
    cli = json.loads(capsys.readouterr().out)
    wire = dict(rest_status=rest.status_code, rest=rest.json(), mcp=mcp, cli=cli)
    if folder := os.environ.get("FATEBRIDGE_PREFLIGHT_TEST_WIRE_DIR"):
        # Test-only evidence destination, including the marked internal-engine
        # fault worker whose suite properties do not reach its parent pytest.
        path = Path(folder) / f"{tool}-{basis}-{failed}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(wire, stream, ensure_ascii=False)
    record_testsuite_property(
        f"preflight-wire-{tool}-{basis}-{failed}",
        json.dumps(wire, ensure_ascii=False),
    )
    values = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in [rest.json(), mcp, cli]
    ]
    if failed:
        assert values[2] == {**values[0], "status_code": rest.status_code}
        assert values[1] == {**values[2], "operation": spec.operation_label_zh}
        assert values[0]["error_code"] == "ephemeris_source_inconsistent"
        assert "person_info" not in values[0]
    else:
        assert values[0] == values[1] == values[2]
        chart = values[0]["base_chart"] if tool == "astro_germany" else values[0]
        assert chart["person_info"]["clock_conversion"]["input_clock_basis"] == basis


@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_guolao_public_and_service_admit_explicit_solar_input(basis):
    args = {**CASE, "birth_clock_basis": basis}
    assert AstroGuolaoRequest(**args).birth_clock_basis == basis
    assert (
        AstroChartPolyRequest(**args, chart_variant="guolao_chart").birth_clock_basis
        == basis
    )
    value = calculate_core_chart_analysis(**args, chart_variant="guolao_chart")
    assert "error" not in value, value
    assert value["guolao"]["profile"]["input_clock"]["input_clock_basis"] == basis
