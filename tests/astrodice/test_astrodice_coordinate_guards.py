"""Invalid native coordinates cannot select a false sect or change Fortune."""

import asyncio
import json
import math

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.classical import _sect
from fatebridge.core.astro.horizon import horizon_altitude
from fatebridge.core.astro.native_coordinates import require_spherical_coordinates
from fatebridge.core.local_techniques.otherbu import build_otherbu_result
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError

SPEC = next(x for x in CATALOG if x.key == "otherbu")
INPUTS = {
    "planet": "Jupiter",
    "sign": "Aries",
    "house": 0,
    "date": "2024-06-21",
    "time": "12:00",
    "zone": "UTC",
    "gps_lat": 51.5,
    "gps_lon": 0,
}


def inject_failure(monkeypatch, problem):
    original = runtime.ephemeris_call
    swe = runtime.swe
    assert swe is not None

    def inject(operation, *args, **kwargs):
        if problem == "horizon_nan" and operation == "azalt":
            result = original(operation, *args, **kwargs)
            return result[0], math.nan, result[2]
        if operation == "calc" and args[1] == swe.SUN:
            flags = args[2]
            changed = flags
            if problem == "ecliptic_to_equatorial" and not flags & swe.FLG_EQUATORIAL:
                changed |= swe.FLG_EQUATORIAL
            elif problem == "equatorial_to_ecliptic" and flags & swe.FLG_EQUATORIAL:
                changed &= ~swe.FLG_EQUATORIAL
            elif problem == "sidereal_to_tropical" and flags & swe.FLG_SIDEREAL:
                changed &= ~swe.FLG_SIDEREAL
            elif problem == "degrees_to_radians" and not flags & swe.FLG_EQUATORIAL:
                changed |= swe.FLG_RADIANS
            elif problem == "of_date_to_J2000" and not flags & swe.FLG_EQUATORIAL:
                changed |= swe.FLG_J2000
            elif problem == "apparent_to_geometric" and not flags & swe.FLG_EQUATORIAL:
                changed |= swe.FLG_TRUEPOS
            return original(operation, args[0], args[1], changed)
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", inject)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -90.0001, 90.0001])
def test_unavailable_solar_altitude_cannot_be_classified_as_night(value):
    with pytest.raises(EphemerisSourceError) as error:
        _sect(value)
    assert error.value.reason == "coordinate_values_unavailable"


@pytest.mark.parametrize(
    "altitude,expected",
    [(0.0, "day"), (-1e-15, "night"), (90.0, "day"), (-90.0, "night")],
)
def test_valid_geometric_centre_convention_is_preserved(altitude, expected):
    assert _sect(altitude) == expected


@pytest.mark.parametrize(
    "problem,zodiacal",
    [
        (p, z)
        for p in [
            "horizon_nan",
            "ecliptic_to_equatorial",
            "equatorial_to_ecliptic",
            "degrees_to_radians",
            "of_date_to_J2000",
            "apparent_to_geometric",
        ]
        for z in [0, 1]
    ]
    + [("sidereal_to_tropical", 1)],
)
def test_real_native_wrong_frame_or_nan_horizon_is_rejected_before_fortune(
    problem, zodiacal, monkeypatch
):
    normal = build_otherbu_result(**INPUTS, zodiacal=zodiacal)
    assert normal["chart"]["params"]["fortuneDefinition"]["sect_applied"] == "day"
    inject_failure(monkeypatch, problem)
    with pytest.raises(EphemerisSourceError) as error:
        build_otherbu_result(**INPUTS, zodiacal=zodiacal)
    assert error.value.reason == (
        "coordinate_values_unavailable"
        if problem == "horizon_nan"
        else "coordinate_contract_changed"
    )


@pytest.mark.parametrize(
    "index,value",
    [(0, math.nan), (1, math.nan), (1, 91.0), (2, -1.0), (4, math.inf), (5, math.nan)],
)
def test_partial_nonfinite_native_state_is_a_source_error(index, value, monkeypatch):
    original = runtime.ephemeris_call
    swe = runtime.swe
    assert swe is not None

    def inject(operation, *args, **kwargs):
        values, flags = original(operation, *args, **kwargs)
        if (
            operation == "calc"
            and args[1] == swe.SUN
            and not args[2] & swe.FLG_EQUATORIAL
        ):
            changed = list(values)
            changed[index] = value
            return changed, flags
        return values, flags

    monkeypatch.setattr(runtime, "ephemeris_call", inject)
    with pytest.raises(EphemerisSourceError) as error:
        ephemeris._swisseph_planet_state("Sun", 2451545.0, julian_day_tt=2451545.0)
    assert error.value.reason == "coordinate_values_unavailable"


def test_spherical_parser_rejects_short_coordinates():
    swe = runtime.swe
    assert swe is not None
    with pytest.raises(EphemerisSourceError) as error:
        require_spherical_coordinates((1, 2), swe.FLG_SWIEPH, native=swe)
    assert error.value.reason == "coordinate_values_unavailable"


@pytest.mark.parametrize("result", [(), (1, None, 2), (1, 91, 2)])
def test_malformed_horizon_payload_does_not_silently_select_an_approximation(
    result, monkeypatch
):
    original = runtime.ephemeris_call
    monkeypatch.setattr(
        runtime,
        "ephemeris_call",
        lambda operation, *args, **kwargs: (
            result if operation == "azalt" else original(operation, *args, **kwargs)
        ),
    )
    with pytest.raises(EphemerisSourceError) as error:
        horizon_altitude(2451545.0, 0.0, 51.5, 90.0, 0.0)
    assert error.value.reason == "coordinate_values_unavailable"


@pytest.mark.parametrize("problem", ["horizon_nan", "ecliptic_to_equatorial"])
def test_false_fortune_is_replaced_by_the_same_safe_error_in_three_transports(
    problem, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inject_failure(monkeypatch, problem)
    with TestClient(api.app) as client:
        response = client.post(SPEC.rest_path, json=INPUTS)
    assert response.status_code == 503
    expected = response.json()
    assert expected["error_code"] == "ephemeris_source_inconsistent"
    assert "chart" not in expected

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool("otherbu", INPUTS, raise_on_error=False)
            assert result.is_error
            return json.loads(result.content[0].text)

    native = asyncio.run(invoke())
    flags = [
        "otherbu",
        *(
            part
            for k, v in INPUTS.items()
            for part in ("--" + k.replace("_", "-"), str(v))
        ),
    ]
    assert run(flags) == 1
    cli = json.loads(capsys.readouterr().out)
    for current in [native, cli]:
        assert current["error_code"] == expected["error_code"]
        assert current["issues"] == expected["issues"]
        assert current["retryable"] is False
