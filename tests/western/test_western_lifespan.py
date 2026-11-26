"""
Deterministic tests for the western *lifespan* techniques.

These controls check selected derived arithmetic and service contracts. They do
not certify natal ephemeris accuracy, complete classical methods or prediction.
"""

import math

import pytest

from fatebridge.core.astro.astrology_lifespan import (
    BALBILLUS_SMALL_YEARS,
    DOROTHEAN_TRIPLICITY_RULERS,
    KEYPOINTS_PERIOD_NUMBERS,
    build_balbillus_payload,
    build_distributions_payload,
    build_harmonic_payload,
    build_keypoints_payload,
    build_planetary_ages_payload,
    build_planetary_arc_payload,
    build_triplicity_rulers_payload,
    build_yearsystem129_payload,
)
from fatebridge.services.western_lifespan import (
    calculate_balbillus,
    calculate_distributions,
    calculate_harmonic_chart,
    calculate_keypoints,
    calculate_lunation_phase,
    calculate_planetary_ages,
    calculate_planetary_arc,
    calculate_triplicity_rulers,
    calculate_yearsystem129,
)
from fatebridge.services.western_timing_tools import calculate_timing_tool
from tests.fixtures.surface_payloads import J2000_UNRESOLVED_ASC_SITE
from tests.support.transports import AS_OF, SPECS, business

BIRTH = dict(
    name="测试者",
    birth_year=1995,
    birth_month=6,
    birth_day=3,
    birth_hour=5,
    birth_minute=30,
    birth_timezone="+08:00",
    birth_longitude=121.47,
    birth_latitude=31.23,
)


def _point(absolute_degree: float, sign: str = "Aries", **extra) -> dict:
    """Minimal natal_reference point stub for unit-testing builders directly."""
    return {
        "absolute_degree": absolute_degree,
        "sign": sign,
        "sign_label": sign,
        "degree": absolute_degree % 30.0,
        "house": extra.get("house"),
        "house_label": extra.get("house_label"),
        "retrograde": extra.get("retrograde", False),
    }


# Pure-builder math (exact values).


def test_harmonic_multiplies_longitude_mod_360() -> None:
    natal = {
        "sun": _point(40.0),
        "moon": _point(60.0),
    }
    payload = build_harmonic_payload(natal, harmonic=9, orb=2.0)
    # 40 * 9 = 360 -> 0 ; 60 * 9 = 540 -> 180
    assert payload["positions"]["sun"]["absolute_degree"] == 0.0
    assert payload["positions"]["moon"]["absolute_degree"] == 180.0
    # 0 vs 180 are 180° apart -> not a conjunction within orb 2.
    assert payload["resonant_conjunctions"] == []


def test_harmonic_detects_conjunction_within_orb() -> None:
    # 10*9=90 ; 11*9=99 -> 9° apart, outside orb 2 but 10 vs 10.5 collapses:
    natal = {"sun": _point(10.0), "moon": _point(10.5)}
    payload = build_harmonic_payload(natal, harmonic=2, orb=2.0)
    # 10*2=20 ; 10.5*2=21 -> 1° apart -> conjunction.
    assert len(payload["resonant_conjunctions"]) == 1
    assert payload["resonant_conjunctions"][0]["separation_degree"] == 1.0


def test_harmonic_degree_keeps_the_exact_product_below_the_boundary() -> None:
    """Three times the binary64 third is exactly halfway to one from below."""
    chart = build_harmonic_payload({"sun": _point(1 / 3)}, harmonic=3, orb=2.0)

    assert chart["positions"]["sun"]["degree"] == math.nextafter(1.0, 0.0)


def test_planetary_ages_table_is_ptolemaic_and_flags_active_band() -> None:
    natal = {
        name: _point(0.0)
        for name in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
    }
    payload = build_planetary_ages_payload(natal, current_age_years=30.0)
    planets = [band["planet"] for band in payload["bands"]]
    assert planets == ["Moon", "Mercury", "Venus", "Sun", "Mars", "Jupiter", "Saturn"]
    # Age 30 falls in the Sun band (22-41).
    assert payload["active_planet"] == "Sun"
    sun_band = next(b for b in payload["bands"] if b["planet"] == "Sun")
    assert sun_band["start_age"] == 22.0 and sun_band["end_age"] == 41.0
    assert sun_band["active"] is True
    # Saturn band is open-ended.
    saturn_band = next(b for b in payload["bands"] if b["planet"] == "Saturn")
    assert saturn_band["end_age"] is None


def test_planetary_ages_without_reference_has_no_active_band() -> None:
    natal = {
        name: _point(0.0)
        for name in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
    }
    payload = build_planetary_ages_payload(natal, current_age_years=None)
    assert payload["active_planet"] is None
    assert all(band["active"] is False for band in payload["bands"])


def test_triplicity_rulers_order_by_sect_day() -> None:
    # Sun in Leo (Fire) by day -> day order: Sun, Jupiter, Saturn.
    natal = {"sun": _point(125.0, sign="Leo"), "moon": _point(0.0, sign="Aries")}
    payload = build_triplicity_rulers_payload(natal, sect="day")
    assert payload["element"] == "Fire"
    assert [stage["ruler"] for stage in payload["stages"]] == [
        "Sun",
        "Jupiter",
        "Saturn",
    ]


def test_triplicity_rulers_order_by_sect_night() -> None:
    # Night birth reads the Moon as the sect light; Moon in Taurus (Earth)
    # -> night order: Moon, Venus, Mars.
    natal = {"sun": _point(0.0, sign="Aries"), "moon": _point(40.0, sign="Taurus")}
    payload = build_triplicity_rulers_payload(natal, sect="night")
    assert payload["element"] == "Earth"
    assert [stage["ruler"] for stage in payload["stages"]] == ["Moon", "Venus", "Mars"]
    assert payload["sect_light"] == "Moon"


def test_triplicity_age_bands_match_reference_default() -> None:
    # Default lifespan 75, thirds -> 0-25 / 25-50 / 50-75 (matches Horosa reference).
    natal = {"sun": _point(125.0, sign="Leo"), "moon": _point(0.0, sign="Aries")}
    payload = build_triplicity_rulers_payload(natal, sect="day")
    assert payload["lifespan_years"] == 75.0
    assert payload["division"] == "thirds"
    bands = [(s["start_age"], s["end_age"]) for s in payload["stages"]]
    assert bands == [(0.0, 25.0), (25.0, 50.0), (50.0, 75.0)]
    # Planetary period years exposed per ruler (Sun=19, Jupiter=12, Saturn=30).
    assert [s["planetary_period_years"] for s in payload["stages"]] == [19, 12, 30]


def test_triplicity_halves_division() -> None:
    natal = {"sun": _point(125.0, sign="Leo"), "moon": _point(0.0, sign="Aries")}
    payload = build_triplicity_rulers_payload(
        natal, sect="day", lifespan=80.0, division="halves"
    )
    bands = [(s["start_age"], s["end_age"]) for s in payload["stages"]]
    # main 0-40, secondary 40-80, participating spans the whole life.
    assert bands == [(0.0, 40.0), (40.0, 80.0), (0.0, 80.0)]


def test_dorothean_triplicity_table_is_canonical() -> None:
    assert DOROTHEAN_TRIPLICITY_RULERS["Fire"] == {
        "day": "Sun",
        "night": "Jupiter",
        "participating": "Saturn",
    }
    assert DOROTHEAN_TRIPLICITY_RULERS["Water"] == {
        "day": "Venus",
        "night": "Mars",
        "participating": "Moon",
    }


def test_distributions_first_period_starts_at_ascendant_bound() -> None:
    # Ascendant at 2° Aries -> Jupiter bound (0-6°), Ptolemy 1°/yr.
    natal = {
        "ascendant": _point(2.0, sign="Aries"),
        "medium_coeli": _point(272.0, sign="Capricorn"),
        "sun": _point(20.0, sign="Aries"),
        "moon": _point(200.0, sign="Libra"),
        "mercury": _point(25.0, sign="Aries"),
        "venus": _point(15.0, sign="Aries"),
        "mars": _point(50.0, sign="Taurus"),
        "jupiter": _point(80.0, sign="Gemini"),
        "saturn": _point(120.0, sign="Leo"),
    }
    payload = build_distributions_payload(natal, time_key="Ptolemy", max_age_years=90.0)
    first = payload["periods"][0]
    assert first["distributor"] == "Jupiter"
    assert first["start_age_years"] == 0.0
    # Asc at 2° in a bound ending at 6° -> 4° of arc -> 4 years at 1°/yr.
    assert abs(first["end_age_years"] - 4.0) < 1e-6
    # Sun at 20° Aries -> 18° from Asc -> participant contact at age 18.
    contacts = {
        p["planet"]: p["contact_age_years"]
        for period in payload["periods"]
        for p in period["participants"]
    }
    assert abs(contacts["Sun"] - 18.0) < 1e-6


def _seven_planet_natal(longitudes: dict) -> dict:
    """Build a natal_reference stub from {planet: absolute_degree}."""
    from fatebridge.core.astro.astrology_tables import SIGNS

    natal = {}
    for planet, lon in longitudes.items():
        sign = SIGNS[int(lon % 360 // 30)]
        natal[planet.lower()] = _point(lon, sign=sign)
    return natal


def test_balbillus_small_years_sum_to_129() -> None:
    assert sum(BALBILLUS_SMALL_YEARS.values()) == 129


def test_balbillus_order_sorts_by_longitude_then_rotates() -> None:
    lons = {
        "Sun": 10.0,
        "Moon": 50.0,
        "Mercury": 100.0,
        "Venus": 150.0,
        "Mars": 200.0,
        "Jupiter": 250.0,
        "Saturn": 300.0,
    }
    payload = build_balbillus_payload(_seven_planet_natal(lons), start_planet="Mercury")
    # Ascending by longitude is Sun..Saturn; rotated to start at Mercury.
    assert payload["zodiacal_order"] == [
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Sun",
        "Moon",
    ]


def test_keypoints_period_numbers_table() -> None:
    assert KEYPOINTS_PERIOD_NUMBERS == {
        "Saturn": 3,
        "Mercury": 8,
        "Sun": 18,
        "Venus": 5,
        "Mars": 7,
        "Jupiter": 9,
        "Moon": 13,
    }


def test_keypoints_position_number_and_activation() -> None:
    # Release = Moon at 0° Aries (sign 0). Sun at 60° Gemini (sign 2) -> k = 3.
    natal = _seven_planet_natal(
        {
            "Sun": 60.0,
            "Moon": 0.0,
            "Mercury": 0.0,
            "Venus": 0.0,
            "Mars": 0.0,
            "Jupiter": 0.0,
            "Saturn": 0.0,
        }
    )
    payload = build_keypoints_payload(natal, release_mode="soul", max_age_years=20)
    sun_pos = next(p for p in payload["positions"] if p["planet"] == "Sun")
    assert sun_pos["position_number"] == 3
    assert sun_pos["period_number"] == 18
    by_age = {row["age"]: row for row in payload["activations"]}
    # Age 3 = multiple of k(3) -> Sun position-active.
    assert any(x["planet"] == "Sun" for x in by_age[3]["position_active"])
    # Age 18 = multiple of Sun's period (18) -> Sun period-active.
    assert any(x["planet"] == "Sun" for x in by_age[18]["period_active"])


def test_yearsystem129_uses_full_small_years_in_balbillus_order() -> None:
    lons = {
        "Sun": 10.0,
        "Moon": 50.0,
        "Mercury": 100.0,
        "Venus": 150.0,
        "Mars": 200.0,
        "Jupiter": 250.0,
        "Saturn": 300.0,
    }
    payload = build_yearsystem129_payload(_seven_planet_natal(lons), start_planet="Sun")
    # Full small-years, no exaltation reduction.
    first = payload["periods"][0]
    assert first["planet"] == "Sun"
    assert first["duration_years"] == float(BALBILLUS_SMALL_YEARS["Sun"])
    assert payload["total_cycle_years"] == 129
    # Same zodiacal ordering primitive as Balbillus.
    assert payload["zodiacal_order"][0] == "Sun"
    assert payload["sequence_model"] == "zodiacal"


def test_planetary_arc_directs_whole_chart_by_source_arc() -> None:
    natal = {"Sun": 10.0, "Moon": 100.0, "Mars": 200.0}
    progressed = {"Sun": 40.0, "Moon": 130.0, "Mars": 250.0}
    # arc_source=Moon -> arc = 130-100 = 30; every point advances 30°.
    payload = build_planetary_arc_payload(natal, progressed, arc_source="Moon", orb=1.0)
    assert payload["arc_degrees"] == 30.0
    assert payload["positions"]["sun"]["absolute_degree"] == 40.0
    assert payload["positions"]["mars"]["absolute_degree"] == 230.0


def test_planetary_arc_with_sun_source_equals_solar_arc() -> None:
    """planetaryarc(arc_source=Sun) must reproduce FateBridge's own solar arc."""
    common = dict(analysis_year=2025, analysis_month=4, analysis_day=6)
    pa = calculate_planetary_arc(**BIRTH, arc_source="Sun", **common)
    sa = calculate_timing_tool("solararc", **BIRTH, **common)
    assert (
        abs(pa["planetary_arc"]["arc_degrees"] - sa["solararc"]["arc_degrees"]) < 1e-6
    )


# Service envelope contract.


def test_services_return_envelope_with_snapshot_and_no_error() -> None:
    cases = [
        (calculate_harmonic_chart, {}, "harmonic_chart"),
        (
            calculate_planetary_ages,
            {"analysis_year": 2025, "analysis_month": 6, "analysis_day": 3},
            "planetary_ages",
        ),
        (calculate_triplicity_rulers, {}, "triplicity_rulers"),
        (calculate_lunation_phase, {}, "lunation_phase"),
        (calculate_distributions, {}, "distributions"),
        (calculate_balbillus, {}, "balbillus"),
        (calculate_keypoints, {}, "keypoints"),
        (calculate_yearsystem129, {}, "yearsystem129"),
        (calculate_planetary_arc, {}, "planetary_arc"),
    ]
    for fn, extra, key in cases:
        result = fn(**BIRTH, **extra)
        assert "error" not in result, (fn.__name__, result)
        assert key in result, fn.__name__
        assert result["analysis_context"]["engine"] == "fatebridge-offline"
        assert result["natal_reference"], fn.__name__


def test_harmonic_natal_longitude_matches_chart_engine() -> None:
    """The harmonic value must equal natal_longitude * H mod 360 exactly."""
    result = calculate_harmonic_chart(**BIRTH, harmonic=7)
    sun = result["harmonic_chart"]["positions"]["sun"]
    expected = (sun["natal_absolute_degree"] * 7) % 360.0
    assert abs(sun["absolute_degree"] - round(expected, 4)) < 1e-3


def test_planetary_ages_pre_birth_date_reports_pre_birth_status() -> None:
    pre_birth = calculate_planetary_ages(
        **BIRTH, analysis_year=1990, analysis_month=1, analysis_day=1
    )
    ages = pre_birth["planetary_ages"]
    assert ages["status"] == "pre_birth"
    assert ages["active_planet"] is None
    assert ages["active_planet_label"] is None
    assert ages["current_age_years"] < 0
    assert all(band["active"] is False for band in ages["bands"])
    assert "未指定参照日期" not in pre_birth["summary"]
    assert "早于出生时刻" in pre_birth["summary"]

    unspecified = calculate_planetary_ages(**BIRTH)
    assert unspecified["planetary_ages"]["status"] == "reference_date_unspecified"
    assert "未指定参照日期" in unspecified["summary"]

    active = calculate_planetary_ages(
        **BIRTH, analysis_year=2025, analysis_month=6, analysis_day=3
    )
    assert active["planetary_ages"]["status"] == "active"
    assert active["planetary_ages"]["active_planet"] == "Sun"


def test_singular_ascendant_blocks_ascendant_dependent_results() -> None:
    singular_birth = dict(
        name="奇点",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        **J2000_UNRESOLVED_ASC_SITE,
    )
    distributions = calculate_distributions(**singular_birth, house_system="W")
    dist_payload = distributions["distributions"]
    assert (
        distributions["natal_reference"]["calculation_basis"]["angle_definition"][
            "geometric_ascendant_resolved"
        ]
        is False
    )
    assert dist_payload["status"] == "underdetermined_ascendant"
    assert dist_payload["ascendant_resolved"] is False
    assert dist_payload["ascendant_absolute_degree"] is None
    assert dist_payload["periods"] == []
    assert "本命上升未解析" in distributions["summary"]

    harmonic = calculate_harmonic_chart(**singular_birth, house_system="W", orb=15.0)
    assert "sun" in harmonic["harmonic_chart"]["positions"]
    assert "ascendant" not in harmonic["harmonic_chart"]["positions"]
    assert all(
        "Ascendant" not in conjunction["points"]
        for conjunction in harmonic["harmonic_chart"]["resonant_conjunctions"]
    )

    body_kp = calculate_keypoints(
        **singular_birth, house_system="W", release_mode="body"
    )
    kp_body_payload = body_kp["keypoints"]
    assert kp_body_payload["status"] == "underdetermined_ascendant"
    assert kp_body_payload["ascendant_resolved"] is False
    assert kp_body_payload["release_sign_index"] is None
    assert kp_body_payload["positions"] == []
    assert kp_body_payload["activations"] == []
    assert "本命上升未解析" in body_kp["summary"]

    soul_kp = calculate_keypoints(
        **singular_birth, house_system="W", release_mode="soul"
    )
    kp_soul_payload = soul_kp["keypoints"]
    assert "status" not in kp_soul_payload
    assert len(kp_soul_payload["positions"]) == 7
    assert len(kp_soul_payload["activations"]) > 0
    assert kp_soul_payload["release_sign_index"] is not None


@pytest.mark.parametrize(
    "age_limit,expected_count", [(19.0, 1), (math.nextafter(19.0, math.inf), 2)]
)
def test_small_year_preview_is_half_open_on_all_surfaces(
    age_limit: float, expected_count: int, surface_calls
) -> None:
    response, protocol, code, cli = surface_calls(
        SPECS["planetary_periods_129_years"],
        {**BIRTH, "max_age_years": age_limit, "start_planet": "Sun"},
        projection={
            "fields": ["yearsystem129"],
            "detail": "audit",
        },
        rest_as_of=AS_OF,
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    result = response.json()
    assert business(result) == business(protocol.structured_content) == business(cli)
    periods = result["yearsystem129"]["periods"]
    assert len(periods) == expected_count
    assert periods[0]["planet"] == "Sun"
    assert periods[0]["duration_years"] == 19
    if expected_count == 2:
        assert periods[1]["start_age_years"] == 19
