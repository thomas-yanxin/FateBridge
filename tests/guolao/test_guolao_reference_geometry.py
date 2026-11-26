"""A failed optional reference house system cannot erase a valid Guolao sky."""

import asyncio
import json
import math
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import astro_models
from fatebridge.core.astro import earth_attitude, runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao import guolao
from fatebridge.services.guolao import calculate_guolao_chart
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload
from tests.support.transports import cached_mcp_app, call_calculation

SPEC = next(spec for spec in CATALOG if spec.name == "guolao_chart")


def polar_payload(**changes):
    return {
        **astro_payload(),
        "birth_year": 2026,
        "birth_month": 6,
        "birth_day": 21,
        "birth_hour": 12,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": 18.96,
        "birth_latitude": 69.65,
        "use_true_solar_time": False,
        "house_system": 3,
        **changes,
    }


def chart(**changes):
    return calculate_guolao_chart(**polar_payload(**changes))


@pytest.mark.parametrize("latitude", [69.65, -69.65, 80.0, -80.0])
@pytest.mark.parametrize("zodiac_type", ["Tropic", "Sidereal"])
def test_real_polar_placidus_error_retains_core_and_independent_angles(
    latitude, zodiac_type: str
) -> None:
    result = chart(birth_latitude=latitude, zodiac_type=zodiac_type)
    reference = chart(birth_latitude=latitude, zodiac_type=zodiac_type, house_system=1)
    assert "error" not in result
    g = result["guolao"]
    for key in [
        "bodies",
        "life_palace",
        "palaces",
        "conditions",
        "god_positions",
        "moira_patterns",
        "mansion_boundaries",
        "rule_trace",
    ]:
        assert g[key] == reference["guolao"][key]
    assert result["angles"] == reference["angles"]
    assert result["houses"] == []
    for actual, other in zip(result["planets"], reference["planets"]):
        assert actual["house"] is None
        assert {k: v for k, v in actual.items() if k != "house"} == {
            k: v for k, v in other.items() if k != "house"
        }
    geometry = g["profile"]["reference_geometry"]
    assert geometry["status"] == "partial"
    assert geometry["houses_status"] == "unavailable"
    assert geometry["angles_status"] == "available"
    assert geometry["requested_house_code"] == "P"
    assert geometry["house_method"] is None
    assert not geometry["substituted_house_system"]
    assert result["chart_profile"]["house_system"] == "placidus"


@pytest.mark.parametrize("latitude", [90.0, -90.0])
@pytest.mark.parametrize("zodiac_type", ["Tropic", "Sidereal"])
def test_exact_geographic_poles_have_no_assigned_rising_point_or_houses(
    latitude, zodiac_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = runtime.ephemeris_call

    def no_house_call(operation, *args, **kwargs):
        if operation == "houses_ex":
            pytest.fail(
                "A geographic pole must not get a limiting ASC or arbitrary houses"
            )
        else:
            pass
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", no_house_call)
    result = chart(birth_latitude=latitude, zodiac_type=zodiac_type)
    assert "error" not in result
    assert len(result["guolao"]["bodies"]) == 11
    assert result["houses"] == []
    assert all(p["house"] is None for p in result["planets"])
    assert result["angles"] == {
        key: {"longitude": None, "sign": None, "sign_zh": None}
        for key in ["ascendant", "midheaven"]
    }
    assert result["guolao"]["conditions"]["is_day"] == (latitude > 0)
    assert math.isfinite(result["guolao"]["conditions"]["solar_altitude"])
    assert (
        result["guolao"]["profile"]["reference_geometry"]["reason"]
        == "geographic_pole_no_unique_rising_point"
    )


def test_target_sky_and_small_limit_are_independent_of_reference_house_availability() -> (
    None
):
    target = datetime.fromisoformat("2027-06-01T00:00:00+08:00")
    unavailable = chart(analysis_datetime=target, zodiac_type="Sidereal")
    available = chart(analysis_datetime=target, zodiac_type="Sidereal", house_system=0)
    assert unavailable["guolao"]["timing"] == available["guolao"]["timing"]


def test_invalid_cusps_are_not_unwrapped_or_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = runtime.ephemeris_call
    injected = []

    def invalid(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "houses_ex" and args[3] == b"P":
            injected.append(True)
            return (0.0,) * 12, result[1]
        else:
            pass
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", invalid)
    result = chart(birth_latitude=31.22)
    assert injected
    assert "error" not in result
    assert result["houses"] == []
    assert (
        result["guolao"]["profile"]["reference_geometry"]["reason"]
        == "requested_cusps_not_a_valid_ecliptic_partition"
    )
    assert len(result["guolao"]["bodies"]) == 11


@pytest.mark.parametrize(
    "operation", ["calc", "azalt", "unexpected_house_bug", "ayanamsha"]
)
def test_essential_or_unexpected_errors_are_not_hidden_as_optional_geometry(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("injected essential computation failure")

    if operation == "unexpected_house_bug":
        original = runtime.ephemeris_call

        def failed_house(operation, *args, **kwargs):
            if operation == "houses_ex":
                fail()
            else:
                pass
            return original(operation, *args, **kwargs)

        monkeypatch.setattr(runtime, "ephemeris_call", failed_house)
    elif operation == "azalt":
        monkeypatch.setattr(
            runtime.swe, "azalt", lambda *args: (0.0, float("nan"), float("nan"))
        )
    elif operation == "ayanamsha":
        monkeypatch.setattr(runtime.swe, "get_ayanamsa_ex", lambda *args: (-1, 0.0))
    else:
        monkeypatch.setattr(runtime.swe, operation, fail)
    result = chart(zodiac_type="Sidereal")
    assert "error" in result
    assert "guolao" not in result


@pytest.mark.parametrize("latitude", [69.65, 90.0])
def test_partial_reference_geometry_across_native_mcp_rest_cli_and_projection(
    latitude: float, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = polar_payload(birth_latitude=latitude, zodiac_type="Sidereal")
    fields = ["guolao", "planets", "angles", "houses"]
    options = {
        "as_of": "2026-10-22T12:00:00+08:00",
        "fields": fields,
        "detail": "audit",
    }
    client = TestClient(api.app)
    response = client.post(
        SPEC.rest_path,
        json=payload,
        params=[
            ("as_of", options["as_of"]),
            ("detail", "audit"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native_call():
        async with Client(cached_mcp_app()) as mcp:
            return await call_calculation(
                mcp, SPEC.name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(native_call())
    assert not native.is_error
    args = [SPEC.name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        options["as_of"],
        "--detail",
        "audit",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    results = [
        {k: v for k, v in d.items() if k != "run_metadata"}
        for d in [response.json(), native.structured_content, cli]
    ]
    assert results[0] == results[1] == results[2]
    projection = client.post(
        SPEC.rest_path,
        json=payload,
        params={
            "fields": "guolao.profile.reference_geometry.houses_status",
        },
    )
    assert projection.status_code == 200, projection.text
    projected = projection.json()
    assert projected["guolao"]["profile"]["reference_geometry"] == {
        "houses_status": "unavailable"
    }


def test_sidereal_only_house_error_preserves_selected_angles_and_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = runtime.ephemeris_call
    injected = []
    expected = chart(birth_latitude=31.22, zodiac_type="Sidereal", house_system=1)

    def fail_sidereal(operation, *args, **kwargs):
        if operation != "houses_ex":
            return original(operation, *args, **kwargs)
        else:
            pass
        flags = kwargs.get("flags", args[4] if len(args) > 4 else 0)
        if args[3] == b"P" and flags & runtime.swe.FLG_SIDEREAL:
            injected.append(True)
            raise runtime.swe.Error("injected sidereal house unavailability")
        else:
            pass
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", fail_sidereal)
    actual = chart(birth_latitude=31.22, zodiac_type="Sidereal")
    assert injected
    assert "error" not in actual
    assert actual["guolao"]["bodies"] == expected["guolao"]["bodies"]
    assert actual["angles"] == expected["angles"]
    assert actual["houses"] == []
    assert actual["guolao"]["profile"]["reference_geometry"]["status"] == "partial"
