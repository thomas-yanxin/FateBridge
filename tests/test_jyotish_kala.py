"""Primary time rules, independent coordinate reference, and explicit gaps."""

import hashlib
import json
import math
from datetime import date, datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_balas import PLANETS, moon_nature_readings
from fatebridge.core.jyotish_kala import (
    ahargana_lords,
    ayana_values,
    nathonnatha,
    paksha_scenarios,
    solar_packet,
    solar_parts,
    temporal_balas,
)
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parent / "fixtures"
PRIMARY = json.loads((FIXTURES / "jyotish-kala-classical.json").read_text())
ORACLE = json.loads((FIXTURES / "jyotish-kala-reference.json").read_text())
EQUATORIAL = json.loads((FIXTURES / "jyotish-equatorial-horizons.json").read_text())


def packet(rise=2451544.75, day_length=0.5, full_length=1.0):
    return {
        "events": [
            {"kind": "rise", "julian_day_ut1": rise - 1},
            {"kind": "set", "julian_day_ut1": rise - 0.5},
            {"kind": "rise", "julian_day_ut1": rise},
            {"kind": "set", "julian_day_ut1": rise + day_length},
            {"kind": "rise", "julian_day_ut1": rise + full_length},
            {"kind": "set", "julian_day_ut1": rise + full_length + 0.5},
            {"kind": "rise", "julian_day_ut1": rise + full_length + 1},
        ]
    }


@pytest.mark.parametrize("stamp,count,year,month,weekday", PRIMARY["calendar_cases"])
def test_exact_ahargana_matches_two_primary_worked_examples(
    stamp, count, year, month, weekday
):
    result = ahargana_lords(date.fromisoformat(stamp))
    assert (
        result["ahargana"],
        result["year_lord"],
        result["month_lord"],
        result["civil_weekday_lord"],
    ) == (count, year, month, weekday)
    assert result["year_days"] == 360 and result["month_days"] == 30


@pytest.mark.parametrize("ra,meridian,day_value,night_value", PRIMARY["natha_cases"])
def test_apparent_solar_meridian_natha_not_civil_clock(
    ra, meridian, day_value, night_value
):
    result = nathonnatha(meridian, ra)
    for p in ("Sun", "Jupiter", "Venus"):
        assert result[p] == day_value
    for p in ("Moon", "Mars", "Saturn"):
        assert result[p] == night_value
    assert result["Mercury"] == 60


@pytest.mark.parametrize(
    "declination,key",
    [
        (0, "ayana_zero_declination"),
        (23.45, "ayana_plus_23_45"),
        (-23.45, "ayana_minus_23_45"),
    ],
)
def test_ayana_fixed_constant_and_hemisphere_signs(declination, key):
    result = ayana_values(dict.fromkeys(PLANETS, declination))
    assert result == pytest.approx(PRIMARY[key], abs=1e-12, rel=0)
    assert ayana_values(dict.fromkeys(PLANETS, 28.5))["Moon"] < 0  # no invented clamp


@pytest.mark.parametrize("sun,moon,expected", PRIMARY["paksha_arcs"])
def test_paksha_folds_longitude_wrap_and_keeps_nature_scenarios(sun, moon, expected):
    result = paksha_scenarios({"Sun": sun, "Moon": moon})
    assert result["benefic_value"] == pytest.approx(expected, abs=1e-12)
    assert result["malefic_value"] == pytest.approx(60 - expected, abs=1e-12)
    for key, values in result["scenarios"].items():
        assert values["Jupiter"] == values["Venus"] == result["benefic_value"]
        assert values["Moon"] == 2 * (
            result["benefic_value"]
            if key.startswith("moon_benefic__")
            else result["malefic_value"]
        )


@pytest.mark.parametrize("elongation,expected", PRIMARY["moon_nature_options"])
def test_conflicting_lunar_nature_readings_are_not_silently_collapsed(
    elongation, expected
):
    result = moon_nature_readings(Fraction(elongation))
    assert result["options"] == expected
    assert result["status"] == "author_readings_not_uniquely_adjudicated"


def test_hora_all_seven_weekdays_and24_fixed_hours_against_primary_table():
    for weekday in range(7):
        rise = 2451545.75 + weekday  # Sunday2000-01-02 at6UT, then following days
        for hour in range(24):
            result = solar_parts(rise + (hour + 0.25) / 24, 0, packet(rise))
            assert result["hora_number"] == hour + 1
            assert (
                result["hora_lord"]
                == PRIMARY["hora_first_seven_rows_sunday_to_saturday"][hour % 7][
                    weekday
                ]
            )


def test_sunrise_sunset_midnight_and_thirds_are_half_open_without_daily_clock_wrap():
    rise = 2451544.75
    ctx = packet(rise)
    for hours, day, part, ruler in [
        (0, True, 1, "Mercury"),
        (4, True, 2, "Sun"),
        (8, True, 3, "Saturn"),
        (12, False, 1, "Moon"),
        (16, False, 2, "Venus"),
        (20, False, 3, "Mars"),
    ]:
        result = solar_parts(rise + hours / 24, 0, ctx)
        # 4h in JD rounds slightly; exact rational boundaries come from stored
        # event endpoints, so test a point just inside each intended new third.
        if hours in {4, 8, 16, 20}:
            result = solar_parts(math.nextafter(rise + hours / 24, math.inf), 0, ctx)
        assert (result["is_day"], result["third_number"], result["tribhaga_lord"]) == (
            day,
            part,
            ruler,
        )
    assert (
        solar_parts(rise + 18 / 24, 0, ctx)["opening_local_mean_date"] == "2000-01-01"
    )
    assert solar_parts(rise + 1, 0, ctx)["day_lord"] == "Sun"
    shortday = solar_parts(rise + 5 / 24, 0, packet(rise, day_length=9 / 24))
    assert shortday["hora_number"] == 6  # not an unequal day-hour index
    boundary_input = rise + 25 / 24
    assert Fraction(boundary_input) < Fraction(rise) + Fraction(25, 24)
    assert (
        solar_parts(boundary_input, 0, packet(rise, full_length=26 / 24))["hora_number"]
        == 25
    )
    longday = solar_parts(rise + 24.5 / 24, 0, packet(rise, full_length=26 / 24))
    assert longday["hora_number"] == 25
    assert longday["hora_lord"] is None


@pytest.mark.parametrize(
    "reference", EQUATORIAL["references"], ids=lambda ref: ref["body"]
)
def test_equatorial_positions_against_independently_rotated_jpl_iau7680(
    reference, monkeypatch, tmp_path
):
    assert EQUATORIAL["derivation"]["software"] == "pyerfa"
    assert (
        hashlib.sha256((FIXTURES / "jyotish-horizons.json").read_bytes()).hexdigest()
        == EQUATORIAL["derivation"]["source_sha256"]
    )
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    for row in reference["rows"]:
        instant = datetime.fromisoformat(row["utc"])
        birth = build_astro_birth_info(
            birth_year=instant.year,
            birth_month=instant.month,
            birth_day=instant.day,
            birth_hour=instant.hour,
            birth_minute=instant.minute,
            birth_timezone="UTC",
            birth_latitude=0,
            birth_longitude=0,
        )
        raw = positions(birth)
        assert raw["ephemeris_models"] == ["moshier"]
        assert (
            raw["ephemeris_quality"]["equatorial_ephemeris_by_body"][reference["body"]]
            == "moshier"
        )
        actual = raw["equatorial"][reference["body"]]
        ra_error = (
            actual["right_ascension"] - row["right_ascension"] + 180
        ) % 360 - 180
        assert abs(ra_error) * 3600 < EQUATORIAL["tolerance_arcseconds"]
        assert (
            abs(actual["declination"] - row["declination"]) * 3600
            < EQUATORIAL["tolerance_arcseconds"]
        )


@pytest.mark.parametrize("case", ORACLE["examples"])
def test_hindu_solar_events_against_isolated_reference_and_preserve_non_aligned_outputs(
    case, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    y, m, d = case["date"]
    h, minute, _ = case["time"]
    birth = build_astro_birth_info(
        birth_year=y,
        birth_month=m,
        birth_day=d,
        birth_hour=h,
        birth_minute=minute,
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        birth_timezone=str(case["timezone_offset"]),
    )
    raw = positions(birth)
    assert raw["ephemeris_models"] == ["moshier"]
    events = solar_packet(raw["julian_day_ut"], birth.longitude, birth.latitude, "auto")
    for kind, expected in case["solar_events_ut1"].items():
        assert (
            min(
                abs(row["julian_day_ut1"] - expected)
                for row in events["events"]
                if row["kind"] == kind
            )
            * 86400
            < 1
        )
    # These functions use different midpoint/declination/clock models. Retain
    # their answers as counterevidence, never force source arithmetic to match.
    assert set(case["outputs"]) == {
        "nathonnatha",
        "paksha",
        "tribhaga",
        "abda",
        "masa",
        "dina",
        "hora",
        "ayana",
    }


def test_polar_missing_rise_does_not_erase_independent_components_or_fill_fake_dawn():
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth)
    result = temporal_balas(raw, {"events": []}, birth.longitude)
    kala = result["kala_bala"]
    assert kala["solar_context"]["status"] == "solar_day_not_bracketed"
    assert kala["components"]["tribhaga_bala"]["summary"]["Jupiter"] == 60
    assert kala["components"]["dina_bala"]["summary"]["Sun"] is None
    assert kala["components"]["nathonnatha_bala"]["summary"]["Mercury"] == 60
    assert kala["components"]["abda_bala"]["ruler"] is not None
    assert all(
        result["cheshta_bala"]["summary"][p] is None
        for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
    )


def test_timezone_labels_for_same_physical_instant_do_not_change_temporal_components():
    data = {
        **astro_payload(),
        "birth_timezone": "UTC",
        "birth_hour": 1,
        "birth_minute": 33,
    }
    utc = build_india(build_astro_birth_info(**data))
    local = build_india(
        build_astro_birth_info(**{**data, "birth_timezone": "+08:00", "birth_hour": 9})
    )
    assert utc["strengths"]["kala_bala"] == local["strengths"]["kala_bala"]
    assert utc["strengths"]["cheshta_bala"] == local["strengths"]["cheshta_bala"]


def test_war_candidates_are_local_and_do_not_fabricate_zero_amounts():
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth)
    raw["longitudes"].update(
        Mars=0.0, Mercury=0.5, Jupiter=120.0, Venus=180.0, Saturn=240.0
    )
    result = temporal_balas(raw, packet(), birth.longitude)
    war = result["kala_bala"]["components"]["yuddha_bala"]
    assert war["candidates"] == [
        {"planets": ["Mars", "Mercury"], "separation_degrees": 0.5}
    ]
    assert war["summary"]["Mars"] is None and war["summary"]["Mercury"] is None
    assert war["summary"]["Sun"] == war["summary"]["Jupiter"] == 0
    raw["longitudes"]["Mercury"] = 1.0
    war = temporal_balas(raw, packet(), birth.longitude)["kala_bala"]["components"][
        "yuddha_bala"
    ]
    assert not war["candidates"]  # literal less-than1 degree, not <=


@pytest.mark.native_engine_fault
def test_strict_policy_checks_supporting_sun_events(monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    auto = solar_packet(2451545.0, 0, 0, "auto")
    assert auto["fallback_event_count"] > 0
    with pytest.raises(ValueError, match="require_data_files"):
        solar_packet(2451545.0, 0, 0, "require_data_files")


@pytest.mark.native_engine_fault
def test_equatorial_fallback_is_reported_and_strictly_rejected(monkeypatch, tmp_path):
    from fatebridge.core.astro import runtime

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    original = runtime.swe.calc

    def ecliptic_as_files(jd, body, flags):
        values, returned = original(jd, body, flags)
        if not flags & runtime.swe.FLG_EQUATORIAL:
            returned = (
                returned
                & ~(
                    runtime.swe.FLG_SWIEPH
                    | runtime.swe.FLG_MOSEPH
                    | runtime.swe.FLG_JPLEPH
                )
            ) | runtime.swe.FLG_SWIEPH
        return values, returned

    monkeypatch.setattr(runtime.swe, "calc", ecliptic_as_files)
    # These synthetic flags test the coordinate-frame policy, with no actual
    # file source to reconstruct. Physical reconstruction has separate tests.
    from fatebridge.core import ephemeris_runtime

    endpoint_calls = []

    def synthetic_endpoint(native, operation, args, kwargs, invoke, *, configured_path):
        endpoint_calls.append(operation)
        return invoke(native, operation, args, kwargs)

    monkeypatch.setattr(
        ephemeris_runtime, "compressed_endpoint_call", synthetic_endpoint
    )
    # The flags above are synthetic; no actual .se1 file was opened.
    monkeypatch.setattr(
        runtime.swe, "get_current_file_data", lambda slot: ("", 0, 0, 0)
    )
    # This test deliberately lies about native backend flags. Isolate the
    # new motion dependency: it cannot reconstruct Swiss barycentric states
    # from analytical Moshier vectors. Real motion/source tests stay separate.
    from fatebridge.core import jyotish

    def synthetic_motion(planet, jd, coordinates, model, **kwargs):
        return {
            "longitude_speed_degrees_per_day": float(coordinates[3]),
            "longitude_speed_native_degrees_per_day": float(coordinates[3]),
            "longitude_motion_context": {
                "rate_basis": "synthetic_flag_fixture",
                "epoch_jd_tt": jd,
            },
        }

    monkeypatch.setattr(jyotish, "longitude_motion", synthetic_motion)
    # The additional continuous alternative requires a coherent physical
    # source; this deliberately mixed-frame fixture cannot supply one.
    monkeypatch.setattr(jyotish, "continuous_state_evidence", lambda *a, **k: None)
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth)
    assert "calc" in endpoint_calls
    assert raw["ephemeris_by_body"]["Sun"] == "swieph"
    assert raw["ephemeris_quality"]["equatorial_ephemeris_by_body"]["Sun"] == "moshier"
    assert "Sun" in raw["ephemeris_quality"]["fallback_bodies"]
    scope = raw["apparent_position_policy"]["bodies"]["Jupiter"]
    assert scope["status"] == "not_evaluated"
    assert scope["reason"] == "ecliptic_equatorial_backend_mismatch"
    assert scope["coordinate_backends"] == {
        "ecliptic": "swieph",
        "equatorial": "moshier",
    }
    with pytest.raises(ValueError, match="赤道坐标"):
        positions(birth, ephemeris_policy="require_data_files")


def test_real_polar_solar_day_remains_partial_without_fake_six_oclock():
    birth = build_astro_birth_info(
        birth_year=2026,
        birth_month=6,
        birth_day=21,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=80,
        birth_longitude=0,
    )
    india = build_india(birth, divisions=[])
    kala = india["strengths"]["kala_bala"]
    assert kala["solar_context"]["status"] == "solar_day_not_bracketed"
    assert kala["components"]["nathonnatha_bala"]["summary"]["Mercury"] == 60
    assert kala["components"]["hora_bala"]["ruler"] is None


@pytest.mark.native_engine_fault
def test_time_lord_change_is_detected_even_with_only_d1_exported(monkeypatch):
    from fatebridge.core import jyotish

    birth = build_astro_birth_info(**astro_payload())
    base = positions(birth)
    synthetic = packet(base["julian_day_ut"] - 0.125)
    monkeypatch.setattr(jyotish, "solar_packet", lambda *args: synthetic)
    india = build_india(birth, divisions=[], birth_time_uncertainty_minutes=1)
    sensitivity = india["birth_time_sensitivity"]
    assert len(sensitivity["time_lord_alternatives"]["hora_bala"]) == 2
    assert sensitivity["status"] == "changes_detected"
    assert set(sensitivity["temporal_bala_scenario_sample_ranges"]) == {
        "kala_bala",
        "cheshta_bala",
        "yuddha_bala",
    }
