"""Common physical axes and retained polar house geometry."""

import math
from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import ephemeris
from fatebridge.core.astro.house_positions import build_ecliptic_house_projection
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.predictive.native_chart import (
    HOUSE_ATTRIBUTES,
    HOUSE_NAMES,
    build_native_subject,
)
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.unit_test.fixtures.western_natal import GREENWICH_EQUINOX_BIRTH as BIRTH


def separation(a: float, b: float) -> float:
    return abs(math.remainder(a - b, 360.0)) * 3600.0


POLAR_BIRTH = dict(
    birth_year=1900,
    birth_month=1,
    birth_day=1,
    birth_hour=0,
    birth_minute=30,
    birth_timezone="UTC",
    birth_longitude=0.0,
    birth_latitude=-80.0,
)


def test_service_summary_keeps_an_actual_geographic_pole_qualification() -> None:
    result = calculate_core_chart_analysis(
        **{**BIRTH, "birth_latitude": 90.0}, chart_variant="chart", hsys=0
    )
    note = result["chart_profile"]["angle_definition"]["note_zh"]
    assert note in result["summary"]


def test_service_summary_keeps_an_actual_partial_orbital_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ephemeris._swisseph_planet_state

    def without_venus(planet, *args, **kwargs):
        return None if planet == "Venus" else original(planet, *args, **kwargs)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", without_venus)
    result = calculate_core_chart_analysis(**BIRTH, chart_variant="chart", hsys=0)
    note = result["chart_profile"]["orbital_fallback"]["note_zh"]
    assert note in result["summary"]


@pytest.mark.parametrize("hsys", [2, 6])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_public_polar_mc_is_common_sky_point_while_tenth_cusp_retains_branch(
    hsys: int, zodiacal: int
) -> None:
    result = calculate_core_chart_analysis(
        **POLAR_BIRTH, chart_variant="chart", hsys=hsys, zodiacal=zodiacal
    )
    equal = calculate_core_chart_analysis(
        **POLAR_BIRTH, chart_variant="chart", hsys=0, zodiacal=zodiacal
    )
    assert result["angles"] == equal["angles"]
    convention = result["chart_profile"]["house_axis_convention"]
    assert (
        separation(
            result["houses"][9]["cusp_longitude"], convention["native_house_midheaven"]
        )
        < 1e-6
    )
    assert separation(
        convention["native_house_midheaven"], convention["public_midheaven"]
    ) == pytest.approx(180 * 3600, abs=1e-6)
    assert convention["note_zh"] in result["summary"]


@pytest.mark.parametrize("code", ["R", "C", "T"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_predictive_polar_mc_and_natal_use_same_physical_axis(
    code: str, zodiac: str
) -> None:
    kwargs = dict(
        name="pole test",
        local_datetime=datetime(1900, 1, 1, 0, 30, tzinfo=timezone.utc),
        longitude=0.0,
        latitude=-80.0,
        timezone_name="UTC",
        zodiac_type=zodiac,
    )
    actual = build_native_subject(**kwargs, house_system=code)
    equal = build_native_subject(**kwargs, house_system="E")
    assert actual.medium_coeli.abs_pos == equal.medium_coeli.abs_pos
    assert actual.tenth_house.abs_pos != actual.medium_coeli.abs_pos
    note = actual.calculation_basis["house_axis_convention"]
    assert note["public_midheaven"] == actual.medium_coeli.abs_pos


def test_nonprograde_makransky_cusps_retain_forward_house_labels() -> None:
    subject = build_native_subject(
        name="Makransky cusp labels",
        local_datetime=datetime(2024, 3, 20, 3, 6, tzinfo=timezone.utc),
        longitude=165.35,
        latitude=-89.0,
        timezone_name="UTC",
        house_system="i",
    )
    assert subject.calculation_basis["house_position_projection"]["house_code"] == "i"
    assert tuple(subject.points[key].house for key in HOUSE_ATTRIBUTES) == HOUSE_NAMES


@pytest.mark.parametrize("code", [b"I", b"i"])
def test_sunshine_projection_retains_its_own_declination(code: bytes) -> None:
    def projector(hour):
        moment = datetime(2024, 3, 20, hour, 6, tzinfo=timezone.utc)
        time = ephemeris_time(moment)
        return build_ecliptic_house_projection(
            julian_day_ut1=time.ut1,
            julian_day_tt=time.tt,
            geographic_latitude=-89.0,
            geographic_longitude=165.35,
            house_code=code,
        )

    def coordinates(frame):
        return tuple(frame.coordinate(longitude) for longitude in range(0, 360, 45))

    expected_a = coordinates(projector(3))
    waiting_a = projector(3)
    frame_b = projector(5)
    expected_b = coordinates(frame_b)

    assert coordinates(waiting_a) == expected_a
    assert coordinates(frame_b) == expected_b
