"""Progression services use the same physical instants and zodiac as their facts.

Direct Swiss calls check coordinate/time plumbing, not independent ephemeris
accuracy or the empirical validity of symbolic progression techniques.
"""

from contextlib import nullcontext
from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import geometry
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.services.western_lifespan import (
    _body_declinations,
    calculate_jaynesprog,
    calculate_vedicprog,
)
from tests.support.ephemeris_case_runtime import native_ephemeris_files
from tests.support.ephemeris_context import empty_ephemeris_path
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
# FLINT 3.6.0: 946684800000000 µs / (36524219/100000), nearest µs.
PROGRESSED = datetime(1972, 7, 30, 23, 58, 57, 147239, tzinfo=timezone.utc)


def native_coordinates(body, moment, *, sidereal=False, equatorial=False):
    with preserve_ephemeris_path():
        flags = swe.FLG_SWIEPH
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
            flags |= swe.FLG_SIDEREAL
        else:
            pass
        if equatorial:
            flags |= swe.FLG_EQUATORIAL
        else:
            pass
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
def test_declinations_use_the_civil_instants_tt_instead_of_treating_utc_as_ut1(
    moment,
) -> None:
    actual = _body_declinations(moment)
    for body, planet in (("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS)):
        expected = native_coordinates(planet, moment, equatorial=True)[1]
        assert actual[body] == pytest.approx(expected, abs=1e-10)


def test_vedic_natal_reference_and_progressed_positions_share_native_lahiri() -> None:
    result = calculate_vedicprog(**BIRTH_INPUTS, zodiac_type="Tropic")
    assert "error" not in result, result
    assert (
        datetime.fromisoformat(result["sidereal_progressions"]["progressed_datetime"])
        == PROGRESSED
    )
    assert (
        result["sidereal_progressions"]["calculation_options"]["year_basis"]
        == "fixed_365_24219_nominal_days"
    )
    for body, planet in (
        ("sun", swe.SUN),
        ("moon", swe.MOON),
        ("mercury", swe.MERCURY),
    ):
        expected_natal = native_coordinates(planet, BIRTH, sidereal=True)[0]
        expected_progressed = native_coordinates(planet, PROGRESSED, sidereal=True)[0]
        assert result["natal_reference"][body]["absolute_degree"] == pytest.approx(
            expected_natal, abs=1e-8
        )
        assert result["sidereal_progressions"]["positions"][body][
            "absolute_degree"
        ] == pytest.approx(expected_progressed, abs=1e-8)
    assert result["analysis_context"]["zodiac_type"] == "Sidereal"


@pytest.mark.parametrize(
    "zone,hour,minute,target,expected",
    [
        (
            "Asia/Tokyo",
            9,
            18,
            (1, 1, 1),
            "1894-11-03T08:22:25.900465+09:00",
        ),
        (
            "Etc/GMT+5",
            19,
            0,
            (9999, 12, 31),
            "1922-03-21T18:09:46.521190-05:00",
        ),
    ],
    ids=["analysis-utc-year-zero", "analysis-utc-year-10000"],
)
def test_vedic_progression_from_extended_utc_analysis_clock(
    zone: str, hour: int, minute: int, target, expected: str
) -> None:
    # Fixed TZif offsets and exact rational nominal-day quotient from R133.
    year, month, day = target
    result = calculate_vedicprog(
        birth_year=1900,
        birth_month=1,
        birth_day=15,
        birth_hour=hour,
        birth_minute=minute,
        birth_timezone=zone,
        birth_longitude=139.6917,
        birth_latitude=35.6895,
        house_system="W",
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
    )
    assert "error" not in result, result
    assert result["sidereal_progressions"]["progressed_datetime"] == expected


@pytest.mark.parametrize(
    "use_files",
    [False, pytest.param(True, marks=pytest.mark.local_data)],
    ids=["moshier", "swiss-files"],
)
def test_progressions_from_birth_at_utc_year_zero(
    use_files: bool, monkeypatch: pytest.MonkeyPatch, request
) -> None:
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    if use_files:
        request.getfixturevalue("native_ephemeris_files")
    else:
        pass
    inputs = dict(
        birth_year=1,
        birth_month=1,
        birth_day=1,
        birth_hour=13,
        birth_minute=59,
        birth_timezone="Etc/GMT-14",
        birth_longitude=139.6917,
        birth_latitude=35.6895,
        house_system="W",
        analysis_year=36,
        analysis_month=1,
        analysis_day=1,
    )
    # R161: fixed integer Gregorian clock, with coordinates verified per source.
    progressed = datetime(1, 2, 4, 23, 57, 7, 245885, tzinfo=timezone.utc)
    with nullcontext() if use_files else empty_ephemeris_path():
        vedic = calculate_vedicprog(**inputs)
        jayne = calculate_jaynesprog(**inputs)
        expected_moon = (
            263.83427532265  # Frozen independent Swiss C reference.
            if use_files
            else native_coordinates(swe.MOON, progressed, sidereal=True)[0]
        )
    assert "error" not in vedic, vedic
    assert "error" not in jayne, jayne
    assert (
        vedic["sidereal_progressions"]["progressed_datetime"]
        == "0001-02-05T13:57:07.245885+14:00"
    )
    assert vedic["sidereal_progressions"]["positions"]["moon"][
        "absolute_degree"
    ] == pytest.approx(expected_moon, rel=0, abs=1e-9)
    declination = jayne["declination_progressions"]
    assert declination["progressed_datetime"] == "0001-02-04T23:57:07.245885+00:00"
    closest = declination["parallels"][0]
    assert (closest["progressed"], closest["natal"], closest["kind"]) == (
        "Mars",
        "Venus",
        "contraparallel",
    )
    if use_files:
        assert (
            closest["progressed_declination"],
            closest["natal_declination"],
            closest["orb"],
        ) == (13.0555, -13.0874, 0.0319)
    else:
        pass


@pytest.mark.parametrize("failure", ["exception", "negative_flags", "nonfinite"])
def test_vedic_native_offset_failure_never_succeeds_with_linear_approximation(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    original = geometry.runtime.ephemeris_call

    def unavailable(operation, *args, **kwargs):
        if operation not in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            return original(operation, *args, **kwargs)
        else:
            pass
        if failure == "exception":
            raise RuntimeError("synthetic native offset failure")
        else:
            pass
        return (-1, 23.0) if failure == "negative_flags" else (2, float("nan"))

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    result = calculate_vedicprog(**BIRTH_INPUTS)
    assert result.get("error"), result
    assert "sidereal_progressions" not in result


@pytest.mark.parametrize("tool", ["sidereal_progressions", "declination_progressions"])
def test_correct_progression_frames_reach_rest_mcp_cli(
    tool: str, surface_calls
) -> None:
    spec = SPECS[tool]
    key = tool
    fields = ["natal_reference", key, "analysis_context.zodiac_type"]
    query = [("fields", field) for field in fields]
    http, protocol, code, cli = surface_calls(
        spec,
        BIRTH_INPUTS,
        params=query,
        options={
            "fields": fields,
        },
        flags=["--fields", *fields],
    )
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    outputs = [http.json(), cli, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        assert datetime.fromisoformat(result[key]["progressed_datetime"]) == PROGRESSED
        assert result[key]["calculation_options"]["year_key_numerator"] == 36524219
        assert result[key]["calculation_options"]["year_key_denominator"] == 100000
        if key == "sidereal_progressions":
            expected = native_coordinates(swe.MOON, BIRTH, sidereal=True)[0]
            assert result["natal_reference"]["moon"][
                "absolute_degree"
            ] == pytest.approx(expected, abs=1e-8)
            assert result["analysis_context"]["zodiac_type"] == "Sidereal"
        else:
            assert result[key]["parallels"]
            for row in result[key]["parallels"]:
                natal_body = getattr(swe, row["natal"].upper())
                progressed_body = getattr(swe, row["progressed"].upper())
                natal_declination = native_coordinates(
                    natal_body, BIRTH, equatorial=True
                )[1]
                progressed_declination = native_coordinates(
                    progressed_body, PROGRESSED, equatorial=True
                )[1]
                assert row["natal_declination"] == round(natal_declination, 4)
                assert row["progressed_declination"] == round(progressed_declination, 4)


@pytest.mark.parametrize("arc_source,planet", [("Sun", 0), ("Moon", 1)])
def test_planetary_arc_uses_independent_secondary_clock_on_all_surfaces(
    arc_source: str, planet: int, surface_calls
) -> None:
    response, protocol, code, cli = surface_calls(
        SPECS["planetary_arc_directions"],
        {**BIRTH_INPUTS, "arc_source": arc_source},
        projection={
            "fields": ["natal_reference.sun", "planetary_arc"],
        },
    )
    assert response.status_code == 200, response.text
    assert not protocol.is_error and code == 0
    result = response.json()
    assert business(result) == business(protocol.structured_content) == business(cli)
    progression = result["planetary_arc"]
    assert datetime.fromisoformat(progression["progressed_datetime"]) == PROGRESSED
    arc = (
        native_coordinates(planet, PROGRESSED)[0] - native_coordinates(planet, BIRTH)[0]
    ) % 360
    assert progression["arc_degrees"] == pytest.approx(arc, abs=0.00005)
    natal_sun = result["natal_reference"]["sun"]["absolute_degree"]
    assert progression["positions"]["sun"]["absolute_degree"] == pytest.approx(
        (natal_sun + arc) % 360, abs=1e-8
    )
