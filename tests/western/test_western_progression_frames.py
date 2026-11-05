"""Progression services use the same physical instants and zodiac as their facts.

Direct Swiss calls check coordinate/time plumbing, not independent ephemeris
accuracy or the empirical validity of symbolic progression techniques.
"""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.astro import geometry
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.services.western_lifespan import _body_declinations, calculate_vedicprog
from tests.support.transports import SPECS, business, native, rest, surface_calls

BIRTH_INPUTS = dict(
    birth_year=1972,
    birth_month=7,
    birth_day=1,
    birth_hour=0,
    birth_minute=0,
    birth_timezone="UTC",
    birth_longitude=0,
    birth_latitude=40,
    analysis_year=2002,
    analysis_month=7,
    analysis_day=1,
)
BIRTH = datetime(1972, 7, 1, tzinfo=timezone.utc)
TARGET = datetime(2002, 7, 1, tzinfo=timezone.utc)


def native_coordinates(body, moment, *, sidereal=False, equatorial=False):
    with preserve_ephemeris_path():
        flags = swe.FLG_SWIEPH
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flags |= swe.FLG_SIDEREAL
        if equatorial:
            flags |= swe.FLG_EQUATORIAL
        coordinates, returned = ephemeris_call(
            "calc", ephemeris_time(moment).jd_tt, body, flags
        )
    assert returned >= 0
    return coordinates


@pytest.mark.parametrize(
    "moment",
    [
        BIRTH,
        datetime(1990, 5, 17, tzinfo=timezone.utc),
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    ],
)
def test_declinations_use_the_civil_instants_tt_instead_of_treating_utc_as_ut1(moment):
    actual = _body_declinations(moment)
    for body, planet in (("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS)):
        expected = native_coordinates(planet, moment, equatorial=True)[1]
        assert actual[body] == pytest.approx(expected, abs=1e-10)


def test_vedic_natal_reference_and_progressed_positions_share_native_lahiri():
    result = calculate_vedicprog(**BIRTH_INPUTS, zodiac_type="Tropic")
    assert "error" not in result, result
    age = (TARGET - BIRTH).total_seconds() / (365.2425 * 86400)
    progressed = BIRTH + timedelta(days=age)
    for body, planet in (
        ("sun", swe.SUN),
        ("moon", swe.MOON),
        ("mercury", swe.MERCURY),
    ):
        expected_natal = native_coordinates(planet, BIRTH, sidereal=True)[0]
        expected_progressed = native_coordinates(planet, progressed, sidereal=True)[0]
        assert result["natal_reference"][body]["absolute_degree"] == pytest.approx(
            expected_natal, abs=1e-8
        )
        assert result["vedic_progression"]["positions"][body][
            "absolute_degree"
        ] == pytest.approx(expected_progressed, abs=1e-8)
    assert result["analysis_context"]["zodiac_type"] == "Sidereal"


@pytest.mark.parametrize("failure", ["exception", "negative_flags", "nonfinite"])
def test_vedic_native_offset_failure_never_succeeds_with_linear_approximation(
    monkeypatch, failure
):
    original = geometry.runtime.ephemeris_call

    def unavailable(operation, *args, **kwargs):
        if operation not in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            return original(operation, *args, **kwargs)
        if failure == "exception":
            raise RuntimeError("synthetic native offset failure")
        return (-1, 23.0) if failure == "negative_flags" else (2, float("nan"))

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    result = calculate_vedicprog(**BIRTH_INPUTS)
    assert result.get("error"), result
    assert "vedic_progression" not in result


@pytest.mark.parametrize("tool", ["astro_vedicprog", "astro_jaynesprog"])
def test_correct_progression_frames_reach_rest_mcp_cli(tool, surface_calls):
    spec = SPECS[tool]
    key = "vedic_progression" if tool == "astro_vedicprog" else "jaynes_declination"
    fields = ["natal_reference", key, "analysis_context.zodiac_type"]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    http, protocol, code, cli = surface_calls(
        spec,
        BIRTH_INPUTS,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        if key == "vedic_progression":
            expected = native_coordinates(swe.MOON, BIRTH, sidereal=True)[0]
            assert result["natal_reference"]["moon"][
                "absolute_degree"
            ] == pytest.approx(expected, abs=1e-8)
            assert result["analysis_context"]["zodiac_type"] == "Sidereal"
        else:
            assert result[key]["parallels"]
            age = (TARGET - BIRTH).total_seconds() / (365.2425 * 86400)
            progressed = BIRTH + timedelta(days=age)
            for row in result[key]["parallels"]:
                natal_body = getattr(swe, row["natal"].upper())
                progressed_body = getattr(swe, row["progressed"].upper())
                natal_declination = native_coordinates(
                    natal_body, BIRTH, equatorial=True
                )[1]
                progressed_declination = native_coordinates(
                    progressed_body, progressed, equatorial=True
                )[1]
                assert row["natal_declination"] == round(natal_declination, 4)
                assert row["progressed_declination"] == round(progressed_declination, 4)
