"""Primary time table and visually checked classical facts, no outcome claims."""

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import (
    GRAHAS,
    build_india,
    divisional_chart,
    positions,
    topic_evidence,
)
from fatebridge.core.jyotish_strength import (
    SOURCE,
    SOURCE_ID,
    degree_condition,
    physical_state,
    solar_orb_condition,
)

FIXTURES = Path(__file__).parent / "fixtures"
TIME_REFERENCE = json.loads((FIXTURES / "jyotish-time-reference.json").read_text())
CLASSICAL = json.loads((FIXTURES / "jyotish-santhanam-vol1-reference.json").read_text())
UTC = timezone.utc


def iers_offsets():
    # Parse only the independently fetched IERS response, never production data.
    entries = []
    for line in TIME_REFERENCE["source_text"].splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        _, day, month, year, offset = fields
        entries.append(
            (datetime(int(year), int(month), int(day), tzinfo=UTC), int(offset))
        )
    return entries


def birth_at(instant):
    return build_astro_birth_info(
        birth_year=instant.year,
        birth_month=instant.month,
        birth_day=instant.day,
        birth_hour=instant.hour,
        birth_minute=instant.minute,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )


def independent_tt(instant, offset):
    # Gregorian elapsed calendar days plus primary IERS offset, exact rational
    # arithmetic until the final JD double; no FateBridge calendar/SWE converter.
    elapsed = instant - datetime(1970, 1, 1, tzinfo=UTC)
    seconds = Fraction(elapsed.days * 86400 + elapsed.seconds) + Fraction(
        elapsed.microseconds, 10**6
    )
    return float(
        Fraction(4881175, 2) + (seconds + offset + Fraction(32184, 1000)) / 86400
    )


def assert_default_position_tt_trace(seen, raw, expected):
    """Account for every default mean-node call, including solar-disc geometry.

    The independent IERS epoch applies to every frame. Exact multisets reject
    omitted, repeated or unclassified calls rather than accepting a new count.
    """
    swe = runtime.swe
    planets = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
    sidereal = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    equatorial = swe.FLG_SWIEPH | swe.FLG_EQUATORIAL
    required = Counter(
        (getattr(swe, planet.upper()), flags)
        for planet in planets
        for flags in (sidereal, equatorial)
    )
    required[(swe.MEAN_NODE, sidereal)] += 1
    policy = raw["apparent_position_policy"]
    assert policy["epoch_jd_tt"] == pytest.approx(expected, abs=5e-10, rel=0)
    assert set(policy["bodies"]) == set(planets) - {"Sun", "Moon"}
    computed = set()
    for planet, result in policy["bodies"].items():
        assert result["status"] in {"computed", "not_evaluated"}
        if result["status"] == "computed":
            computed.add(planet)
    models = {raw["ephemeris_by_body"][planet] for planet in computed}
    assert models <= {"swieph", "jpl"}
    frame = equatorial | swe.FLG_XYZ | swe.FLG_ICRS | swe.FLG_J2000
    for _ in models:
        for body in (swe.EARTH, swe.SUN):
            required[(body, frame | swe.FLG_BARYCTR | swe.FLG_TRUEPOS)] += 1
    for planet in computed:
        required[
            (getattr(swe, planet.upper()), frame | swe.FLG_NOGDEFL | swe.FLG_NOABERR)
        ] += 1
    assert all(abs(jd - expected) <= 5e-10 for jd, _, _ in seen), "native TT mismatch"
    assert Counter((body, flags) for _, body, flags in seen) == required


def test_primary_iers_response_is_frozen_and_dates_are_ordered():
    assert (
        hashlib.sha256(TIME_REFERENCE["source_text"].encode()).hexdigest()
        == TIME_REFERENCE["response_sha256"]
    )
    assert "Bulletin 72" in TIME_REFERENCE["source_text"]
    entries = iers_offsets()
    assert len(entries) == 28
    assert entries == sorted(entries)
    assert entries[0] == (datetime(1972, 1, 1, tzinfo=UTC), 10)
    assert entries[-1] == (datetime(2017, 1, 1, tzinfo=UTC), 37)
    context = positions(birth_at(datetime(2026, 1, 1, tzinfo=UTC)))[
        "time_scale_context"
    ]
    assert context["leap_table_sha256"] == TIME_REFERENCE["response_sha256"]
    assert context["leap_table_expires_at"] == "2027-06-28T00:00:00+00:00"


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("effective,offset", iers_offsets())
def test_native_planets_use_primary_iers_tt_at_each_offset_transition(
    effective, offset, monkeypatch
):
    from fatebridge.core import jyotish

    real_calc = runtime.ephemeris_call
    real_motion = jyotish.longitude_motion
    real_continuous = jyotish.continuous_state_evidence
    continuous_epochs = []
    seen = []
    auxiliary = []
    motion_epochs = []
    in_auxiliary = False

    def motion(planet, julian_day_tt, *args, **kwargs):
        nonlocal in_auxiliary
        # Classify only the actual domain call, not arbitrary off-epoch calls.
        # The original displayed-coordinate multiset below remains exact.
        assert julian_day_tt == pytest.approx(expected, abs=5e-10, rel=0)
        motion_epochs.append((planet, julian_day_tt))
        in_auxiliary = True
        try:
            result = real_motion(planet, julian_day_tt, *args, **kwargs)
            assert result["longitude_motion_context"]["epoch_jd_tt"] == julian_day_tt
            return result
        finally:
            in_auxiliary = False

    def continuous(planet, julian_day_tt, *args, **kwargs):
        nonlocal in_auxiliary
        assert julian_day_tt == pytest.approx(expected, abs=5e-10, rel=0)
        continuous_epochs.append((planet, julian_day_tt))
        in_auxiliary = True
        try:
            result = real_continuous(planet, julian_day_tt, *args, **kwargs)
            assert result["epoch_jd_tt"] == julian_day_tt
            return result
        finally:
            in_auxiliary = False

    def calculate(operation, *args, **kwargs):
        # This domain endpoint preserves source guards. Their retarded source
        # probes run internally, outside the displayed-coordinate request.
        if operation == "calc":
            (auxiliary if in_auxiliary else seen).append(tuple(args))
        return real_calc(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", calculate)
    monkeypatch.setattr(jyotish, "continuous_state_evidence", continuous)
    monkeypatch.setattr(jyotish, "longitude_motion", motion)
    # The previous second is valid UTC calendar notation; the unrepresentable
    # 23:59:60 leap label itself is deliberately not invented by datetime.
    instants = [(effective, offset)]
    if effective.year > 1972 or effective.month > 1:
        instants.append((effective - timedelta(seconds=1), offset - 1))
    for instant, tai_minus_utc in instants:
        seen.clear()
        auxiliary.clear()
        motion_epochs.clear()
        continuous_epochs.clear()
        expected = independent_tt(instant, tai_minus_utc)
        raw = positions(birth_at(instant), instant)
        assert raw["julian_day_tt"] == pytest.approx(expected, abs=5e-10, rel=0)
        assert_default_position_tt_trace(seen, raw, expected)
        assert Counter(planet for planet, _ in motion_epochs) == Counter(
            ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
        )
        assert Counter(planet for planet, _ in continuous_epochs) == Counter(
            ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")
        )
        assert auxiliary
        assert not raw["time_scale_context"]["future_leap_seconds_assumed_unchanged"]


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("year", [2030, 2050, 2099, 2200])
def test_future_utc_never_silently_switches_to_ut1_or_claims_known_future_leaps(
    year, monkeypatch
):
    def cannot_use_heuristic(*args):
        pytest.fail(
            "Post-1972 UTC must use the explicit leap policy, not Swiss UTC/UT1 heuristics"
        )

    monkeypatch.setattr(runtime.swe, "utc_to_jd", cannot_use_heuristic)
    instant = datetime(year, 7, 1, tzinfo=UTC)
    raw = positions(birth_at(instant))
    assert raw["julian_day_tt"] == pytest.approx(
        independent_tt(instant, 37), abs=5e-10, rel=0
    )
    context = raw["time_scale_context"]
    assert context["future_leap_seconds_assumed_unchanged"] is True
    assert context["houses_timescale"] == "UT1_model_estimate"
    # This checks the selected model's fixed point, not independent future EOP.
    delta = runtime.ephemeris_call(
        "deltat_ex", raw["julian_day_ut"], runtime.swe.FLG_SWIEPH
    )
    assert abs(raw["julian_day_tt"] - raw["julian_day_ut"] - delta) * 86400 < 0.00005


def test_leap_table_expiry_is_reported_at_the_exact_boundary():
    expiry = datetime(2027, 6, 28, tzinfo=UTC)
    for instant, assumed in [(expiry - timedelta(seconds=1), False), (expiry, True)]:
        raw = positions(birth_at(instant), instant)
        assert (
            raw["time_scale_context"]["future_leap_seconds_assumed_unchanged"]
            is assumed
        )


def test_historical_input_is_labeled_as_ut1_assumption_without_invented_utc_jd():
    raw = positions(birth_at(datetime(1900, 1, 1, tzinfo=UTC)))
    assert raw["julian_day_utc"] is None
    assert (
        raw["time_scale_context"]["houses_timescale"]
        == "historical_UT1_input_assumption"
    )
    assert "pre_1972" in raw["time_scale_context"]["method"]


@pytest.mark.parametrize(
    "stamp,offset",
    json.loads((FIXTURES / "jyotish-historical-time-reference.json").read_text())[
        "cases"
    ],
)
def test_indian_historical_utc_uses_independent_iers_affine_offset(stamp, offset):
    instant = datetime.fromisoformat(stamp)
    raw = positions(birth_at(instant))
    assert raw["julian_day_utc"] is not None
    assert raw["julian_day_tt"] == pytest.approx(
        independent_tt(instant, Fraction(str(offset))), abs=5e-10, rel=0
    )
    assert raw["time_scale_context"]["houses_timescale"] == "UT1_model_estimate"
    assert (
        raw["time_scale_context"]["method"]
        == "IERS_1961_1971_UTC_drift_to_TT_swiss_delta_t_to_UT1"
    )
    primary = json.loads(
        (FIXTURES / "jyotish-historical-time-reference.json").read_text()
    )
    assert (
        raw["time_scale_context"]["historical_utc_source_sha256"]
        == primary["source_sha256"]
    )


def test_birth_uncertainty_reports_when_only_part_of_the_interval_uses_future_assumptions():
    birth = birth_at(datetime(2027, 6, 27, 23, 59, tzinfo=UTC))
    india = build_india(birth, divisions=[], birth_time_uncertainty_minutes=2)
    assert (
        india["profile"]["time_scale_context"]["future_leap_seconds_assumed_unchanged"]
        is False
    )
    assert (
        india["birth_time_sensitivity"]["sampled_future_leap_seconds_assumed_unchanged"]
        is True
    )


def test_identified_scan_and_visually_reviewed_worked_example_override_bad_ocr():
    assert SOURCE_ID == CLASSICAL["source_id"]
    assert SOURCE["sha256"] == CLASSICAL["scan_sha256"]
    worked = CLASSICAL["worked_uchcha"]
    actual = degree_condition(worked["planet"], worked["longitude_degrees"])[
        "uchcha_bala"
    ]["value"]
    assert actual == worked["expected_virupa"] == 50.75
    assert actual != worked["ocr_misreading"]


@pytest.mark.parametrize("planet,orbs", list(CLASSICAL["solar_orbs"].items()))
def test_author_specific_solar_orbs_both_directions_and_adjacent_float_boundaries(
    planet, orbs
):
    for direction, speed in [("direct", 0.1), ("retrograde", -0.1)]:
        orb = orbs[direction]
        if orb is None:
            assert (
                solar_orb_condition(planet, 0, 0, speed)["status"]
                == "direction_not_covered"
            )
            continue
        at = solar_orb_condition(planet, orb, 0, speed)
        assert at["orb_degrees"] == orb
        assert at["status"] == "at_orb_boundary"
        assert at["angular_criterion_met"] is None
        assert (
            solar_orb_condition(planet, math.nextafter(orb, -math.inf), 0, speed)[
                "angular_criterion_met"
            ]
            is True
        )
        assert (
            solar_orb_condition(planet, math.nextafter(orb, math.inf), 0, speed)[
                "angular_criterion_met"
            ]
            is False
        )
        assert at["source_layer"] == "translator_commentary"


def test_solar_orb_wrap_and_stationary_ambiguity_are_not_rounded_away():
    assert solar_orb_condition("Venus", 7, 359, -0.1)["status"] == "at_orb_boundary"
    assert (
        solar_orb_condition("Venus", math.nextafter(7, -math.inf), 359, -0.1)[
            "angular_criterion_met"
        ]
        is True
    )
    assert solar_orb_condition("Mercury", 13, 0, 0.1)["angular_criterion_met"] is True
    assert solar_orb_condition("Mercury", 13, 0, -0.1)["angular_criterion_met"] is False
    assert (
        solar_orb_condition("Mercury", 13, 0, 0)["status"]
        == "stationary_direction_ambiguous"
    )
    assert solar_orb_condition("Saturn", 15.5, 0, 0)["angular_criterion_met"] is True


@pytest.mark.parametrize("point", ["Sun", "Rahu", "Ketu"])
def test_sun_and_nodes_are_never_assigned_an_author_solar_orb_verdict(point):
    assert "combustion" not in physical_state(point, 0, 0, 0, -0.1)
    with pytest.raises(ValueError):
        solar_orb_condition(point, 0, 0, -0.1)


def test_empty_division_selection_does_not_project_physical_conditions_to_vargas():
    india = build_india(birth_at(datetime(1990, 4, 6, tzinfo=UTC)), divisions=[])
    assert set(india["charts"]) == {"D1"}
    assert india["profile"]["time_scale_context"]["planet_timescale"] == "TT"
    assert (
        "D1_Santhanam_commentary_solar_orb_criterion"
        in india["coverage"]["implemented"]
    )


@pytest.mark.parametrize(
    "status,phrase",
    [
        ("within_orb", "符合 Santhanam"),
        ("outside_orb", "本条件未触发"),
        ("at_orb_boundary", "保留未裁定"),
        ("stationary_direction_ambiguous", "黄经速度为零"),
        ("direction_not_covered", "此项未覆盖"),
    ],
)
def test_topic_interpretation_states_the_actual_solar_orb_result(status, phrase):
    # Synthetic structured evidence tests narration routing only. It is neither
    # a celestial reference case nor a real-world prediction sample.
    raw = {"ascendant": 0.0, "longitudes": {p: 40.0 for p in GRAHAS}}
    chart = divisional_chart(raw, 1)
    for point in chart["planets"]:
        point["physical_state"] = physical_state(point["id"], 40, 0, 0, 0.1)
        if "combustion" in point["physical_state"]:
            point["physical_state"]["combustion"]["status"] = status
    factors = [
        f
        for f in topic_evidence({"D1": chart})["career"]["factors"]
        if f["rule_id"] == "jyotish.santhanam_solar_orb.v1"
    ]
    # Aries H10 is Capricorn, whose ruler Saturn has this explicit evidence.
    assert len(factors) == 1
    assert factors[0]["fact"]["status"] == status
    assert phrase in factors[0]["traditional_interpretation"]
