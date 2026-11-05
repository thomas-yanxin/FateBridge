"""
Deterministic tests for the western *lifespan* techniques.

These techniques are pure functions of the natal positions plus a fixed table or
rate, so the assertions pin exact, hand-computable values rather than fuzzy
ranges. The natal longitudes themselves are produced by the already
ephemeris-validated chart engine, so anchoring the *derived* math here is enough
to lock the whole tool.
"""

from fatebridge.core.astrology_lifespan import (
    BALBILLUS_EXALTATION,
    BALBILLUS_SMALL_YEARS,
    DOROTHEAN_TRIPLICITY_RULERS,
    KEYPOINTS_PERIOD_NUMBERS,
    SECONDARY_SYNODIC_RATE_DEG_PER_YEAR,
    build_balbillus_payload,
    build_distributions_payload,
    build_harmonic_payload,
    build_keypoints_payload,
    build_lunation_phase_payload,
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
from fatebridge.services.western_timing_tools import calculate_solararc

# A fixed birth used across the service-level tests.
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


# ---------------------------------------------------------------------------
# Pure-builder math (exact values).
# ---------------------------------------------------------------------------


def test_harmonic_multiplies_longitude_mod_360():
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


def test_harmonic_detects_conjunction_within_orb():
    # 10*9=90 ; 11*9=99 -> 9° apart, outside orb 2 but 10 vs 10.5 collapses:
    natal = {"sun": _point(10.0), "moon": _point(10.5)}
    payload = build_harmonic_payload(natal, harmonic=2, orb=2.0)
    # 10*2=20 ; 10.5*2=21 -> 1° apart -> conjunction.
    assert len(payload["resonant_conjunctions"]) == 1
    assert payload["resonant_conjunctions"][0]["separation_degree"] == 1.0


def test_planetary_ages_table_is_ptolemaic_and_flags_active_band():
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


def test_planetary_ages_without_reference_has_no_active_band():
    natal = {
        name: _point(0.0)
        for name in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
    }
    payload = build_planetary_ages_payload(natal, current_age_years=None)
    assert payload["active_planet"] is None
    assert all(band["active"] is False for band in payload["bands"])


def test_triplicity_rulers_order_by_sect_day():
    # Sun in Leo (Fire) by day -> day order: Sun, Jupiter, Saturn.
    natal = {"sun": _point(125.0, sign="Leo"), "moon": _point(0.0, sign="Aries")}
    payload = build_triplicity_rulers_payload(natal, sect="day")
    assert payload["element"] == "Fire"
    assert [stage["ruler"] for stage in payload["stages"]] == [
        "Sun",
        "Jupiter",
        "Saturn",
    ]


def test_triplicity_rulers_order_by_sect_night():
    # Night birth reads the Moon as the sect light; Moon in Taurus (Earth)
    # -> night order: Moon, Venus, Mars.
    natal = {"sun": _point(0.0, sign="Aries"), "moon": _point(40.0, sign="Taurus")}
    payload = build_triplicity_rulers_payload(natal, sect="night")
    assert payload["element"] == "Earth"
    assert [stage["ruler"] for stage in payload["stages"]] == ["Moon", "Venus", "Mars"]
    assert payload["sect_light"] == "Moon"


def test_triplicity_age_bands_match_reference_default():
    # Default lifespan 75, thirds -> 0-25 / 25-50 / 50-75 (matches Horosa reference).
    natal = {"sun": _point(125.0, sign="Leo"), "moon": _point(0.0, sign="Aries")}
    payload = build_triplicity_rulers_payload(natal, sect="day")
    assert payload["lifespan_years"] == 75.0
    assert payload["division"] == "thirds"
    bands = [(s["start_age"], s["end_age"]) for s in payload["stages"]]
    assert bands == [(0.0, 25.0), (25.0, 50.0), (50.0, 75.0)]
    # Planetary period years exposed per ruler (Sun=19, Jupiter=12, Saturn=30).
    assert [s["planetary_period_years"] for s in payload["stages"]] == [19, 12, 30]


def test_triplicity_halves_division():
    natal = {"sun": _point(125.0, sign="Leo"), "moon": _point(0.0, sign="Aries")}
    payload = build_triplicity_rulers_payload(
        natal, sect="day", lifespan=80.0, division="halves"
    )
    bands = [(s["start_age"], s["end_age"]) for s in payload["stages"]]
    # main 0-40, secondary 40-80, participating spans the whole life.
    assert bands == [(0.0, 40.0), (40.0, 80.0), (0.0, 80.0)]


def test_dorothean_triplicity_table_is_canonical():
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


def test_lunation_phase_uses_elongation_and_fixed_rate():
    # Moon at 100, Sun at 10 -> elongation 90 -> first_quarter; next boundary 135.
    natal = {"sun": _point(10.0), "moon": _point(100.0)}
    payload = build_lunation_phase_payload(natal, max_age_years=90.0)
    assert payload["natal_elongation_degree"] == 90.0
    assert payload["natal_phase"] == "first_quarter"
    assert payload["progression_rate_deg_per_year"] == round(
        SECONDARY_SYNODIC_RATE_DEG_PER_YEAR, 6
    )
    first = payload["phase_ingresses"][0]
    assert first["phase"] == "gibbous"
    # 45° / 12.190749 °/yr ≈ 3.692 years.
    assert (
        abs(first["ingress_age_years"] - 45.0 / SECONDARY_SYNODIC_RATE_DEG_PER_YEAR)
        < 1e-3
    )


def test_distributions_first_period_starts_at_ascendant_bound():
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
    from fatebridge.core.astrology_tables import SIGNS

    natal = {}
    for planet, lon in longitudes.items():
        sign = SIGNS[int(lon % 360 // 30)]
        natal[planet.lower()] = _point(lon, sign=sign)
    return natal


def test_balbillus_small_years_sum_to_129():
    assert sum(BALBILLUS_SMALL_YEARS.values()) == 129


def test_balbillus_period_full_small_year_at_exaltation_no_fit():
    # Venus has no reduction fit; placed exactly at its exaltation -> distance 0
    # -> period = full small year (8.0).
    lons = {p: BALBILLUS_EXALTATION[p] for p in BALBILLUS_SMALL_YEARS}
    natal = _seven_planet_natal(lons)
    payload = build_balbillus_payload(natal, start_planet="Venus", mode="nearest")
    venus = payload["periods"][0]
    assert venus["planet"] == "Venus"
    assert venus["duration_years"] == 8.0


def test_balbillus_order_sorts_by_longitude_then_rotates():
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


def test_balbillus_subperiods_fill_parent_span():
    lons = {p: BALBILLUS_EXALTATION[p] for p in BALBILLUS_SMALL_YEARS}
    payload = build_balbillus_payload(_seven_planet_natal(lons), mode="nearest")
    first = payload["periods"][0]
    sub_total = sum(s["duration_years"] for s in first["sub_periods"])
    assert abs(sub_total - first["duration_years"]) < 1e-3


def test_keypoints_period_numbers_table():
    assert KEYPOINTS_PERIOD_NUMBERS == {
        "Saturn": 3,
        "Mercury": 8,
        "Sun": 18,
        "Venus": 5,
        "Mars": 7,
        "Jupiter": 9,
        "Moon": 13,
    }


def test_keypoints_position_number_and_activation():
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


def test_yearsystem129_uses_full_small_years_in_balbillus_order():
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


def test_planetary_arc_directs_whole_chart_by_source_arc():
    natal = {"Sun": 10.0, "Moon": 100.0, "Mars": 200.0}
    progressed = {"Sun": 40.0, "Moon": 130.0, "Mars": 250.0}
    # arc_source=Moon -> arc = 130-100 = 30; every point advances 30°.
    payload = build_planetary_arc_payload(natal, progressed, arc_source="Moon", orb=1.0)
    assert payload["arc_degrees"] == 30.0
    assert payload["positions"]["sun"]["absolute_degree"] == 40.0
    assert payload["positions"]["mars"]["absolute_degree"] == 230.0


def test_planetary_arc_with_sun_source_equals_solar_arc():
    """planetaryarc(arc_source=Sun) must reproduce FateBridge's own solar arc."""
    common = dict(analysis_year=2025, analysis_month=4, analysis_day=6)
    pa = calculate_planetary_arc(**BIRTH, arc_source="Sun", **common)
    sa = calculate_solararc(**BIRTH, **common)
    assert (
        abs(pa["planetary_arc"]["arc_degrees"] - sa["solararc"]["arc_degrees"]) < 1e-6
    )


# ---------------------------------------------------------------------------
# Service envelope contract.
# ---------------------------------------------------------------------------


def test_services_return_envelope_with_snapshot_and_no_error():
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
        assert result["snapshot_text"], fn.__name__
        assert key in result, fn.__name__
        assert result["analysis_context"]["engine"] == "fatebridge-offline"
        assert result["natal_reference"], fn.__name__


def test_harmonic_natal_longitude_matches_chart_engine():
    """The harmonic value must equal natal_longitude * H mod 360 exactly."""
    result = calculate_harmonic_chart(**BIRTH, harmonic=7)
    sun = result["harmonic_chart"]["positions"]["sun"]
    expected = (sun["natal_absolute_degree"] * 7) % 360.0
    assert abs(sun["absolute_degree"] - round(expected, 4)) < 1e-3
