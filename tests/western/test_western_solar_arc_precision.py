"""Symbolic solar-arc source controls; no observed-date precision claim."""

import math
from datetime import datetime, timezone
from fractions import Fraction as F
from types import SimpleNamespace

from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.predictive import native_chart
from fatebridge.core.predictive._common import TIMING_POINT_NAMES, point_attribute_name
from fatebridge.core.predictive.solar_arc import build_solar_arc_payload
from tests.support.transports import SPECS, business, rest, surface_calls


def subjects(sun, progressed_sun, moon):
    positions = {p: 5.0 for p in TIMING_POINT_NAMES}
    positions.update(Sun=sun, Moon=moon, Mercury=31.5)
    natal = SimpleNamespace(
        **{
            point_attribute_name(k): SimpleNamespace(abs_pos=v)
            for k, v in positions.items()
        }
    )
    return (
        natal,
        SimpleNamespace(sun=SimpleNamespace(abs_pos=progressed_sun)),
        positions,
    )


def test_source_exact_rotation_controls_sign_and_aspect_eligibility_before_display():
    natal, progressed, positions = subjects(1.0, 11.1, 19.9)
    out = build_solar_arc_payload(natal, progressed)
    exact = (F(positions["Moon"]) + F(11.1) - F(1.0)) % 360
    assert exact < 30
    assert out["moon"]["sign"] == "Aries"
    assert not any(
        h["source"] == "Moon"
        and h["target"] == "Mercury"
        and h["aspect"] == "conjunction"
        for h in out["hits"]
    )
    # This pair is strictly outside the unchanged1.5-degree orb from the raw source formula.
    assert F(31.5) - exact > F(1.5)


def test_all_thirty_degree_cuts_neighbor_floats_and_both_arc_signs():
    for sun, progressed_sun in [(1.0, 11.1), (11.1, 1.0)]:
        arc = (F(progressed_sun) - F(sun)) % 360
        for boundary in range(0, 360, 30):
            source = float((F(boundary) - arc) % 360)
            for moon in [
                math.nextafter(source, -math.inf),
                source,
                math.nextafter(source, math.inf),
            ]:
                natal, progressed, _ = subjects(sun, progressed_sun, moon)
                exact = (F(moon) + F(progressed_sun) - F(sun)) % 360
                out = build_solar_arc_payload(natal, progressed)
                assert (
                    out["moon"]["sign"]
                    == (
                        "Aries",
                        "Taurus",
                        "Gemini",
                        "Cancer",
                        "Leo",
                        "Virgo",
                        "Libra",
                        "Scorpio",
                        "Sagittarius",
                        "Capricorn",
                        "Aquarius",
                        "Pisces",
                    )[int(exact // 30)]
                ), (
                    sun,
                    progressed_sun,
                    boundary,
                    moon,
                    exact,
                    out["moon"],
                )
                assert 0 <= out["moon"]["longitude"] < 360
                assert out["sun"]["longitude"] == progressed_sun
                assert out["arc_degrees"] == round(float(arc), 4)


def test_public_solar_arc_keeps_source_rotation_side_and_orb_on_all_surfaces(
    monkeypatch, surface_calls
):
    birth_tt = ephemeris_time(datetime(2000, 5, 3, tzinfo=timezone.utc)).jd_tt
    original = native_chart._swisseph_planet_state

    def controlled(planet, *args, **kwargs):
        value = original(planet, *args, **kwargs)
        if value is None:
            return value
        state, model = value
        jd = kwargs["julian_day_tt"]
        if (planet == "Sun") or (planet in {"Moon", "Mercury"} and jd == birth_tt):
            state = {
                **state,
                "longitude": (
                    (1.0 if jd == birth_tt else 11.1)
                    if planet == "Sun"
                    else 19.9 if planet == "Moon" else 31.5
                ),
            }
        return state, model

    monkeypatch.setattr(native_chart, "_swisseph_planet_state", controlled)
    spec = SPECS["solararc"]
    inputs = dict(
        birth_year=2000,
        birth_month=5,
        birth_day=3,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=40.0,
        analysis_year=2001,
        analysis_month=5,
        analysis_day=3,
        analysis_hour=0,
        analysis_minute=0,
        house_system="W",
    )
    fields = [
        "solararc",
        "natal_reference.sun",
        "natal_reference.moon",
        "analysis_context",
    ]
    query = [("fields", f) for f in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http, mcp, code, cli = surface_calls(
        spec,
        inputs,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--strict-fields", "--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not mcp.is_error
    outputs = [http.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    exact = (F(19.9) + F(11.1) - F(1.0)) % 360
    for out in outputs:
        assert out["natal_reference"]["sun"]["longitude"] == 1.0
        assert out["natal_reference"]["moon"]["longitude"] == 19.9
        assert out["solararc"]["moon"]["sign"] == "Aries", out["solararc"]["moon"]
        assert out["solararc"]["arc_degrees"] == 10.1
