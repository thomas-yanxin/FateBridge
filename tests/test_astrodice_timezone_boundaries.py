"""Frozen ERFA clock references, DST discontinuities and public transports."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.native_execution import decode, encode
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

FIXTURES = Path(__file__).parent / "fixtures"
PROTOCOL = json.loads(
    (FIXTURES / "astrodice-timezone-boundary-protocol.json").read_text()
)
REFERENCE = json.loads(
    (FIXTURES / "astrodice-timezone-boundary-reference-v2.json").read_text()
)
SPEC = next(spec for spec in CATALOG if spec.key == "otherbu")


@pytest.mark.parametrize(
    "case,reference", tuple(zip(PROTOCOL["cases"], REFERENCE["rows"]))
)
def test_frozen_independent_calendar_reference(case, reference):
    local = datetime.fromisoformat(case["date"] + "T" + case["time"]).replace(
        tzinfo=parse_timezone_name(case["zone"])
    )
    validate_local_clock(local)
    calendar = utc_calendar(local)
    assert (*calendar.date_parts, *calendar.time_parts) == tuple(case["utc"])
    assert calendar.as_datetime() is None
    assert _julian_day(local) == reference["expected_jd_utc"]


@pytest.mark.parametrize(
    "zone,clock,kind",
    [
        ("America/New_York", "2026-03-08T02:30:00", "nonexistent"),
        ("America/New_York", "2026-11-01T01:30:00", "ambiguous"),
        ("Australia/Lord_Howe", "2026-10-04T02:15:00", "nonexistent"),
        ("Australia/Lord_Howe", "2026-04-05T01:45:00", "ambiguous"),
        ("Pacific/Apia", "2011-12-30T12:00:00", "nonexistent"),
        ("Europe/Kyiv", "1990-07-01T01:30:00", "ambiguous"),
    ],
)
@pytest.mark.parametrize("fold", [0, 1])
def test_dst_and_political_gaps_folds_remain_rejected(zone, clock, kind, fold):
    local = datetime.fromisoformat(clock).replace(
        tzinfo=parse_timezone_name(zone), fold=fold
    )
    with pytest.raises(ValueError, match=kind + " local time"):
        validate_local_clock(local)


@pytest.mark.parametrize("case", PROTOCOL["cases"][:2])
def test_extended_birth_round_trips_native_envelope_without_fake_utc(case):
    local = datetime.fromisoformat(case["date"] + "T" + case["time"])
    birth = build_astro_birth_info(
        birth_year=local.year,
        birth_month=local.month,
        birth_day=local.day,
        birth_hour=local.hour,
        birth_minute=local.minute,
        birth_timezone=case["zone"],
        birth_longitude=0,
        birth_latitude=0,
    )
    restored = decode(encode(birth))
    assert restored == birth
    assert restored.utc_datetime is None
    assert restored.utc_isoformat == birth.utc_isoformat
    with pytest.raises(ValueError, match="unchanged physical instant"):
        _ = restored.require_utc_datetime


@pytest.mark.parametrize("case", PROTOCOL["cases"][:2])
def test_extended_utc_is_preserved_across_rest_mcp_cli(case, monkeypatch, capsys):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = {
        "planet": "Saturn",
        "sign": "Aries",
        "house": 0,
        "date": case["date"],
        "time": case["time"],
        "zone": case["zone"],
        "gps_lat": 0,
        "gps_lon": 0,
        "hsys": 0,
    }
    fields = [
        "chart.params.calculationTimeLocal",
        "chart.params.calculationTimeUtc",
        "chart.params.chart_profile.julian_day_tt",
        "chart.params.chart_profile.julian_day_ut1",
        "chart.params.chart_profile.time_scale",
        "chart.params.chart_profile.future_leap_seconds_assumed_unchanged",
    ]
    with TestClient(api.app) as client:
        response = client.post(
            SPEC.rest_path,
            json=inputs,
            params={"fields": fields, "strict_fields": True},
        )
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            return result.structured_content

    native = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        result.pop("run_metadata")
    assert expected == native == cli
    utc_label = expected["chart"]["params"]["calculationTimeUtc"]
    assert utc_label.startswith("0000-" if case["utc"][0] == 0 else "+010000-")
