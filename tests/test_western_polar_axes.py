"""Common physical axes and retained polar house geometry."""

from datetime import datetime, timezone

import pytest

from fatebridge.core.astro import ephemeris, runtime
from fatebridge.core.astro.house_axes import canonical_house_axes
from fatebridge.core.predictive.native_chart import build_native_subject
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.test_western_accuracy import BIRTH
from tests.test_western_house_reference import REFERENCE, separation

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


def test_service_summary_keeps_an_actual_geographic_pole_qualification():
    result = calculate_core_chart_analysis(
        **{**BIRTH, "birth_latitude": 90.0}, chart_variant="chart", hsys=0
    )
    note = result["chart_profile"]["angle_definition"]["note_zh"]
    assert note in result["summary"] and note in result["snapshot_text"]
    assert (
        "chart_profile.angle_definition"
        in result["interpretation_evidence"]["signature"]["source_paths"]
    )


def test_service_summary_keeps_an_actual_partial_orbital_fallback(monkeypatch):
    original = ephemeris._swisseph_planet_state

    def without_venus(planet, *args, **kwargs):
        return None if planet == "Venus" else original(planet, *args, **kwargs)

    monkeypatch.setattr(ephemeris, "_swisseph_planet_state", without_venus)
    result = calculate_core_chart_analysis(**BIRTH, chart_variant="chart", hsys=0)
    note = result["chart_profile"]["orbital_fallback"]["note_zh"]
    assert note in result["summary"] and note in result["snapshot_text"]


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_common_axes_on_every_frozen_geometry_preserve_native_house_branch(case):
    p = case["input"]
    for code in REFERENCE["protocol"]["systems"]:
        try:
            cusps, native = runtime.ephemeris_call(
                "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], code.encode()
            )
        except runtime.swe.Error:
            assert code in {"P", "K"} and abs(p["latitude"]) == 80
            continue
        original = tuple(cusps)
        physical, convention = canonical_house_axes(
            julian_day_ut1=p["jd_ut1"],
            latitude=p["latitude"],
            longitude=p["longitude"],
            house_code=code.encode(),
            native_angles=native,
        )
        assert tuple(cusps) == original
        for i, key in enumerate(["ascendant", "midheaven"]):
            assert separation(physical[i], case["erfa_vector_angles"][key]) <= 1.0
        if convention:
            assert convention["native_house_midheaven"] == native[1]
            assert convention["public_midheaven"] == physical[1]
            assert convention["native_cusps_and_projection_retained"] is True


@pytest.mark.parametrize("hsys", [2, 6])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_public_polar_mc_is_common_sky_point_while_tenth_cusp_retains_branch(
    hsys, zodiacal
):
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
    assert (
        "chart_profile.house_axis_convention"
        in result["interpretation_evidence"]["social_style"]["source_paths"]
    )


@pytest.mark.parametrize("code", ["R", "C", "T"])
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
def test_predictive_polar_mc_and_natal_use_same_physical_axis(code, zodiac):
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
