"""A failed optional reference house system cannot erase a valid Guolao sky."""

import asyncio
import hashlib
import json
import math
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import astro_payload

SPEC = next(spec for spec in CATALOG if spec.key == "astro_guolao")


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
        "hsys": 3,
        **changes,
    }


def chart(**changes):
    return calculate_core_chart_analysis(
        chart_variant="guolao_chart", **polar_payload(**changes)
    )


@pytest.mark.parametrize("latitude", [69.65, -69.65, 80.0, -80.0])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_real_polar_placidus_error_retains_core_and_independent_angles(
    latitude, zodiacal
):
    result = chart(birth_latitude=latitude, zodiacal=zodiacal)
    reference = chart(birth_latitude=latitude, zodiacal=zodiacal, hsys=1)
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
    assert "未替换为其他宫制" in result["interpretation"]["reference_geometry"]
    assert "未替换为其他宫制" in result["snapshot_text"]


@pytest.mark.parametrize("latitude", [90.0, -90.0])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_exact_geographic_poles_have_no_assigned_rising_point_or_houses(
    latitude, zodiacal, monkeypatch
):
    def no_house_call(*args, **kwargs):
        pytest.fail("A geographic pole must not get a limiting ASC or arbitrary houses")

    monkeypatch.setattr(runtime.swe, "houses_ex", no_house_call)
    result = chart(birth_latitude=latitude, zodiacal=zodiacal)
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


def test_target_sky_and_small_limit_are_independent_of_reference_house_availability():
    target = datetime.fromisoformat("2027-06-01T00:00:00+08:00")
    unavailable = chart(analysis_datetime=target, zodiacal=1)
    available = chart(analysis_datetime=target, zodiacal=1, hsys=0)
    assert unavailable["guolao"]["timing"] == available["guolao"]["timing"]


def test_invalid_cusps_are_not_unwrapped_or_replaced(monkeypatch):
    original = runtime.swe.houses_ex

    def invalid(*args, **kwargs):
        cusps, angles = original(*args, **kwargs)
        return ((0.0,) * 12, angles) if args[3] == b"P" else (cusps, angles)

    monkeypatch.setattr(runtime.swe, "houses_ex", invalid)
    result = chart(birth_latitude=31.22)
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
    monkeypatch, operation
):
    def fail(*args, **kwargs):
        raise RuntimeError("injected essential computation failure")

    if operation == "unexpected_house_bug":
        monkeypatch.setattr(runtime.swe, "houses_ex", fail)
    elif operation == "azalt":
        monkeypatch.setattr(
            runtime.swe, "azalt", lambda *args: (0.0, float("nan"), float("nan"))
        )
    elif operation == "ayanamsha":
        monkeypatch.setattr(runtime.swe, "get_ayanamsa_ex", lambda *args: (-1, 0.0))
    else:
        monkeypatch.setattr(runtime.swe, operation, fail)
    result = chart(zodiacal=1)
    assert "error" in result
    assert "guolao" not in result


@pytest.mark.parametrize("latitude", [69.65, 90.0])
def test_partial_reference_geometry_across_native_mcp_rest_cli_and_projection(
    latitude, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    payload = polar_payload(birth_latitude=latitude, zodiacal=1)
    fields = ["guolao", "planets", "angles", "houses", "interpretation"]
    options = {
        "as_of": "2026-10-22T12:00:00+08:00",
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    client = TestClient(api.app)
    response = client.post(
        SPEC.rest_path,
        json=payload,
        params=[
            ("as_of", options["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native_call():
        async with Client(create_mcp_app()) as mcp:
            return await mcp.call_tool(
                SPEC.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(native_call())
    assert not native.is_error
    args = [SPEC.tool_name]
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
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert projection.status_code == 200, projection.text
    projected = projection.json()
    assert projected["guolao"]["profile"]["reference_geometry"] == {
        "houses_status": "unavailable"
    }


def test_sidereal_only_house_error_preserves_selected_angles_and_core(monkeypatch):
    original = runtime.swe.houses_ex
    expected = chart(birth_latitude=31.22, zodiacal=1, hsys=1)

    def fail_sidereal(*args, **kwargs):
        flags = kwargs.get("flags", args[4] if len(args) > 4 else 0)
        if args[3] == b"P" and flags & runtime.swe.FLG_SIDEREAL:
            raise runtime.swe.Error("injected sidereal house unavailability")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime.swe, "houses_ex", fail_sidereal)
    actual = chart(birth_latitude=31.22, zodiacal=1)
    assert "error" not in actual
    assert actual["guolao"]["bodies"] == expected["guolao"]["bodies"]
    assert actual["angles"] == expected["angles"]
    assert actual["houses"] == []
    assert actual["guolao"]["profile"]["reference_geometry"]["status"] == "partial"


def test_partial_geometry_complete_delivery_reuses_the_same_run(monkeypatch, tmp_path):
    from fatebridge.application import result_delivery as delivery
    from fatebridge.core import guolao

    store = delivery.ResultStore(tmp_path / "results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    response = client.post(
        SPEC.rest_path,
        json=polar_payload(zodiacal=1),
        params={"as_of": "2026-10-22T12:00:00+08:00", "response_char_limit": 8192},
    )
    assert response.status_code == 200, response.text
    shaped = response.json()
    ref = shaped["result_delivery"]

    def no_recalculation(*args, **kwargs):
        pytest.fail("Complete result delivery must reuse this partial-geometry run")

    monkeypatch.setattr(guolao, "build_chart", no_recalculation)
    chunks = []
    offset = 0
    while True:
        page = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert page.status_code == 200, page.text
        body = page.json()
        chunks.append(body["text"])
        if body["next_offset"] is None:
            break
        offset = body["next_offset"]
    raw = "".join(chunks)
    assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
    full = json.loads(raw)
    assert full["run_metadata"]["run_id"] == shaped["run_metadata"]["run_id"]
    assert len(full["guolao"]["bodies"]) == 11
    assert full["guolao"]["profile"]["reference_geometry"]["status"] == "partial"
    assert full["houses"] == []
    assert all(p["house"] is None for p in full["planets"])
    assert "未替换为其他宫制" in full["interpretation"]["reference_geometry"]
