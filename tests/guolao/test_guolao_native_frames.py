"""Actual alternate native units/frames cannot be consumed as date degrees."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao import guolao, guolao_timing
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import call_calculation
from tests.unit_test.fixtures.guolao import fixed_moshier as fixed_moshier

CASES = json.loads(
    (Path(__file__).parents[1] / "data/guolao/native_frame_cases.json").read_bytes()
)
BIRTH = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=0,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=15.761059045869185,
    birth_latitude=40,
    use_true_solar_time=True,
)


def inject_case(monkeypatch, case):
    original = guolao.runtime.ephemeris_call
    s = e.swe
    calls = []

    def alternate(operation, *args, **kwargs):
        site, change = case["site"], case["change"]
        selected = (
            (
                site == "seven_physical_equatorial"
                and operation == "calc"
                and args[1] == s.SUN
                and args[2] & s.FLG_EQUATORIAL
            )
            or (
                site == "mean_node_ecliptic"
                and operation == "calc"
                and args[1] == s.MEAN_NODE
                and not args[2] & s.FLG_EQUATORIAL
            )
            or (
                site == "mean_apogee_equatorial"
                and operation == "calc"
                and args[1] == s.MEAN_APOG
                and args[2] & s.FLG_EQUATORIAL
            )
            or (site == "fixed_star_equatorial" and operation == "fixstar2")
            or (site == "solar_altitude" and operation == "azalt")
            or (
                site == "true_obliquity"
                and operation == "calc"
                and args[1] == s.ECL_NUT
            )
        )
        if not selected:
            return original(operation, *args, **kwargs)
        else:
            pass
        calls.append((operation, args))
        if change in ["RADIANS", "J2000", "missing_EQUATORIAL", "missing_extra_speed"]:
            changed = list(args)
            if change in ["RADIANS", "J2000"]:
                changed[-1] |= getattr(s, "FLG_" + change)
            else:
                changed[-1] &= ~getattr(
                    s,
                    "FLG_EQUATORIAL" if change == "missing_EQUATORIAL" else "FLG_SPEED",
                )
            # Native library supplies actual alternate coordinates and flags.
            return original(operation, *changed, **kwargs)
        else:
            pass
        result = original(operation, *args, **kwargs)
        if change == "altitude_91":
            return result[0], 91.0, result[2]
        else:
            pass
        values, flag = list(result[0]), result[-1]
        if change == "declination_91":
            values[1] = 91.0
        elif change == "negative_distance":
            values[2] = -1.0
        elif change == "truncated_vector":
            values = values[:1]
        elif change == "negative_status":
            flag = -1
        else:
            pytest.fail("Unrecognized held adverse case")
        return (
            (tuple(values), result[1], flag)
            if operation == "fixstar2"
            else (tuple(values), flag)
        )

    monkeypatch.setattr(guolao.runtime, "ephemeris_call", alternate)
    return calls


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["site"] + "-" + c["change"])
def test_every_held_alternate_contract_is_rejected_before_consumption(
    monkeypatch: pytest.MonkeyPatch, case
) -> None:
    calls = inject_case(monkeypatch, case)
    with pytest.raises(EphemerisSourceError):
        guolao.positions(build_astro_birth_info(**BIRTH), correct_motion=False)
    assert calls


@pytest.mark.parametrize(
    "site",
    [
        "seven_physical_equatorial",
        "mean_node_ecliptic",
        "mean_apogee_equatorial",
        "fixed_star_equatorial",
    ],
)
def test_target_sky_uses_the_same_contract_instead_of_bypassing_observer_checks(
    monkeypatch: pytest.MonkeyPatch, site: str
) -> None:

    birth = build_astro_birth_info(**BIRTH)
    natal = guolao.build_chart(birth)
    calls = inject_case(monkeypatch, dict(site=site, change="RADIANS"))
    with pytest.raises(EphemerisSourceError):
        guolao_timing.enrich_guolao_timing(
            natal, birth, datetime.fromisoformat("2027-06-01T00:00:00+08:00")
        )
    assert calls
    assert natal["guolao"]["timing"] == {"status": "not_requested"}


@pytest.mark.parametrize("tool", ["astro_guolao", "astro_chart"])
@pytest.mark.parametrize(
    "case,reason",
    [
        (
            dict(site="seven_physical_equatorial", change="RADIANS"),
            "coordinate_contract_changed",
        ),
        (
            dict(site="fixed_star_equatorial", change="J2000"),
            "coordinate_contract_changed",
        ),
        (
            dict(site="mean_node_ecliptic", change="missing_extra_speed"),
            "coordinate_motion_unavailable",
        ),
    ],
)
def test_rejected_contract_agrees_across_actual_rest_mcp_cli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tool: str,
    case,
    reason: str,
) -> None:
    spec = next(s for s in CATALOG if s.key == tool)
    payload = dict(BIRTH)
    if tool == "astro_chart":
        payload["chart_variant"] = "guolao_chart"
    else:
        pass
    calls = inject_case(monkeypatch, case)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(spec.rest_path, json=payload)
    assert rest.status_code == 503, rest.text

    async def native_call():
        async with Client(create_mcp_app()) as client:
            native = await call_calculation(
                client, spec.tool_name, payload, raise_on_error=False
            )
            assert native.is_error
            return native.structured_content

    native = asyncio.run(native_call())
    arguments = [spec.tool_name]
    for key, value in payload.items():
        arguments.extend(["--" + key.replace("_", "-"), str(value)])
    capsys.readouterr()
    assert run(arguments) == 1
    cli = json.loads(capsys.readouterr().out)
    for result in [rest.json(), native, cli]:
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [{"path": "runtime.ephemeris_data", "code": reason}]
        assert "guolao" not in result
    assert calls
