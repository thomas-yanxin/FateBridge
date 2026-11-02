"""Actual specialty transports and independent reconstruction of returned inputs."""

import asyncio
import json
import math
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge import api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG


def three_surfaces(spec, payload, fields, as_of, tmp_path, monkeypatch, capsys):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", as_of),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": as_of,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload, ensure_ascii=False))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request),
            "--as-of",
            as_of,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    assert protocol.structured_content == json.loads(protocol.content[0].text)
    bodies = []
    for label, body in [
        ("rest", response.json()),
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        (tmp_path / f"{label}.json").write_text(
            json.dumps(
                body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            )
        )
        body = dict(body)
        body.pop("run_metadata")
        bodies.append(body)
    assert bodies[0] == bodies[1] == bodies[2]
    return bodies[0]


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize(
    "mode",
    [
        "normal",
        "north",
        "south",
        "asc_only",
        "range_start",
        "range_end",
        "unknown_interval",
        "solar_clock",
    ],
)
def test_day_reference_and_source_coherence_across_real_surfaces(
    key, variant, zodiacal, mode, tmp_path, monkeypatch, capsys
):
    spec = next(s for s in CATALOG if s.key == key)
    birth = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    target = datetime(2050, 1, 1, tzinfo=timezone.utc)
    payload = dict(
        name="虚构：日推运资格三端核验",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=10,
        birth_latitude=20,
        hsys=1,
        zodiacal=zodiacal,
        birth_time_uncertainty_minutes=0.5,
    )
    if variant:
        payload["chart_variant"] = variant
    if mode in ("north", "south"):
        payload.update(
            birth_latitude=90 if mode == "north" else -90,
            birth_time_uncertainty_minutes=0,
        )
        target = birth
    elif mode == "asc_only":
        payload.update(
            birth_latitude=-66.56232328397007,
            birth_longitude=169.5414439374805,
            birth_time_uncertainty_minutes=1,
        )
    elif mode in ("range_start", "range_end"):
        payload.update(birth_latitude=90, birth_time_uncertainty_minutes=1)
        target = birth + timedelta(days=(0 if mode == "range_start" else 150) * 365.25)
    elif mode == "unknown_interval":
        payload.update(birth_latitude=90, birth_time_uncertainty_minutes=None)
    elif mode == "solar_clock":
        payload.pop("birth_timezone")
        payload.update(
            birth_clock_basis="local_apparent_solar", birth_time_uncertainty_minutes=0.7
        )
    payload["analysis_datetime"] = target.isoformat()
    fields = [
        "midpoint_analysis.profile",
        "midpoint_analysis.factors",
        "midpoint_analysis.time_sensitivity",
        "midpoint_analysis.solar_arc_analysis.profile",
        "midpoint_analysis.solar_arc_analysis.daily_meridian",
    ]
    body = three_surfaces(
        spec, payload, fields, target.isoformat(), tmp_path, monkeypatch, capsys
    )
    layer = body["midpoint_analysis"]
    solar = layer["solar_arc_analysis"]
    day = solar["daily_meridian"]
    profile = day["profile"]
    sensitivity = day["birth_time_sensitivity"]
    assert day["input_coherence"]["status"] == "verified"
    assert (
        day["input_coherence"]["birth_julian_day_tt"]
        == layer["profile"]["julian_day_tt"]
    )
    values = {r["id"]: r["longitude"] for r in layer["factors"]}
    phase = math.radians(
        values["Midheaven"]
        + solar["profile"]["solar_arc_degrees"]
        - solar["profile"]["natal_tropical_sun"]
        + profile["target_tropical_sun"]
    )
    expected = math.degrees(math.atan2(math.sin(phase), math.cos(phase))) % 360
    unresolved = mode in (
        "north",
        "south",
        "range_start",
        "range_end",
        "unknown_interval",
    )
    coords = profile["backend_convention"] if unresolved else profile
    assert coords["upper_meridian_longitude"] == pytest.approx(
        expected, abs=1e-10, rel=0
    )
    if unresolved:
        assert (
            profile["upper_meridian_longitude"] is None and day["status"] == "partial"
        )
    else:
        assert day["status"] == "computed"
    if mode == "unknown_interval":
        assert sensitivity["status"] == "not_assessed" and "samples" not in sensitivity
        assert day["input_coherence"]["sample_count"] is None
        return
    raw = layer["time_sensitivity"]["samples"]
    samples = sensitivity["samples"]
    assert len(samples) == len(raw) == day["input_coherence"]["sample_count"]
    for native, row in zip(raw, samples):
        assert (
            row["offset_seconds"] == native["offset_seconds"]
            and row["effective_utc"] == native["effective_utc"]
            and row["julian_day_tt"] == native["julian_day_tt"]
        )
        if row.get("status") == "unavailable":
            assert mode in ("range_start", "range_end")
            assert "backend_convention" not in row and "solar_arc_degrees" not in row
            continue
        phase = math.radians(
            native["factor_longitudes"]["Midheaven"]
            + row["solar_arc_degrees"]
            - row["natal_tropical_sun"]
            + profile["target_tropical_sun"]
        )
        expected = math.degrees(math.atan2(math.sin(phase), math.cos(phase))) % 360
        computed = row["backend_convention"] if unresolved else row
        assert computed["upper_meridian_longitude"] == pytest.approx(
            expected, abs=1e-10, rel=0
        )
        observations = solar["profile"]["sun_ephemeris_source"]["observations"]
        n, p = (observations[i] for i in row["sun_observation_indices"])
        assert (
            n["julian_day_tt"] == row["julian_day_tt"]
            and n["longitude"] == row["natal_tropical_sun"]
        )
        assert p["julian_day_tt"] == row["progressed_julian_day_tt"]
    if mode in ("range_start", "range_end"):
        assert (
            sensitivity["unavailable_sample_count"] == 2
            and sensitivity["unresolved_reference_sample_count"] == 3
        )
    if mode == "asc_only":
        assert profile["angle_definition"]["geometric_ascendant_resolved"] is False
        assert profile["upper_meridian_longitude"] is not None
    if mode == "solar_clock":
        assert sensitivity["input_clock_basis"] == "local_apparent_solar"
