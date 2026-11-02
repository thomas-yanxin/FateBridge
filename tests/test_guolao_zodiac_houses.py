"""Whole-sign definition and direct Swiss oracles for selected-zodiac houses."""

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.reference import RELATIVE_HOUSE_SYSTEM_SPECS
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.fixtures.surface_payloads import astro_payload


def chart(**changes):
    return calculate_core_chart_analysis(
        **{**astro_payload(), "chart_variant": "guolao_chart", **changes}
    )


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("hsys", range(9))
def test_reference_houses_match_native_swiss_in_the_selected_zodiac(hsys, zodiacal):
    result = chart(hsys=hsys, zodiacal=zodiacal)
    assert "error" not in result, result
    jd = result["guolao"]["profile"]["julian_day_ut1"]
    person = result["person_info"]
    swe = runtime.swe
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        cusps, angles = swe.houses_ex(
            jd,
            person["birth_latitude"],
            person["birth_longitude"],
            RELATIVE_HOUSE_SYSTEM_SPECS[hsys]["swisseph_code"],
            swe.FLG_SIDEREAL if zodiacal else 0,
        )
    assert [h["cusp_longitude"] for h in result["houses"]] == list(cusps)
    assert result["angles"]["ascendant"]["longitude"] == angles[0]
    assert result["angles"]["midheaven"]["longitude"] == angles[1]
    profile = result["guolao"]["profile"]
    assert profile["astronomical_house_frame"] == (
        "selected_lahiri_sidereal_zodiac" if zodiacal else "tropical_zodiac"
    )
    assert profile["astronomical_house_method"] == (
        "swisseph_houses_ex_sidereal_lahiri"
        if zodiacal
        else "swisseph_houses_ex_tropical"
    )


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("hour", [0, 9, 18])
def test_whole_sign_cusps_and_planet_houses_obey_the_sign_definition(zodiacal, hour):
    result = chart(hsys=0, zodiacal=zodiacal, birth_hour=hour)
    asc_sign = int(result["angles"]["ascendant"]["longitude"] // 30)
    expected = [((asc_sign + i) % 12) * 30.0 for i in range(12)]
    assert [h["cusp_longitude"] for h in result["houses"]] == expected
    for planet in result["planets"]:
        sign = int(planet["longitude"] // 30)
        assert planet["house"] == (sign - asc_sign) % 12 + 1


def test_sidereal_fix_corrects_the_previously_wrong_fixture_planet_houses():
    result = chart(hsys=0, zodiacal=1)
    planets = {p["id"]: p for p in result["planets"]}
    assert 60 < planets["Jupiter"]["longitude"] < 90
    assert planets["Jupiter"]["house"] == 1  # previously 2
    assert planets["Sun"]["house"] == 10  # previously 11
    assert planets["Mercury"]["house"] == 11  # previously 12
    assert planets["Mars"]["house"] == 8  # previously 9


def test_reference_house_choice_cannot_change_source_functional_palaces():
    whole = chart(hsys=0, zodiacal=1)
    unequal = chart(hsys=3, zodiacal=1)
    assert whole["guolao"]["bodies"] == unequal["guolao"]["bodies"]
    assert whole["guolao"]["life_palace"] == unequal["guolao"]["life_palace"]
    assert whole["guolao"]["palaces"] == unequal["guolao"]["palaces"]
    assert whole["houses"] != unequal["houses"]
