"""External astronomy and explicitly scoped primary-text regressions."""

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.horizon import horizon_altitude
from fatebridge.core.astro.time_scales import ephemeris_time, leap_table
from fatebridge.core.classical_western import compute_lot
from fatebridge.core.predictive._common import build_natal_subject, determine_sect
from fatebridge.core.ptolemy import build_ptolemy_layer
from fatebridge.services.astrology import calculate_core_chart_analysis

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_lot_just_before_zero_stays_on_the_previous_side_of_the_circle():
    result = compute_lot(
        ["asc", "moon", "sun"],
        {"asc": 0.0, "moon": 0.0, "sun": math.nextafter(0.0, 1.0)},
    )
    assert result == math.nextafter(360.0, 0.0)


BIRTH = dict(
    birth_year=2024,
    birth_month=3,
    birth_day=20,
    birth_hour=6,
    birth_minute=30,
    birth_timezone="UTC",
    birth_longitude=0.0,
    birth_latitude=51.5,
)


@pytest.mark.parametrize("hsys", [0, 2, 3, 5, 8])
def test_sun_above_horizon_in_whole_sign_first_house_is_day(hsys):
    result = calculate_core_chart_analysis(
        **BIRTH, chart_variant="hellen_chart", hsys=hsys
    )
    assert "error" not in result
    assert result["hellenistic"]["sect"] == result["classical"]["sect"] == "day"
    sun = next(p for p in result["planets"] if p["id"] == "Sun")
    if hsys == 0:
        assert sun["house"] == 1  # Original bug: called this night.
    assert result["classical"]["planets"]["Sun"]["above_horizon"] is True
    assert (
        result["hellenistic"]["lot_of_fortune"]["longitude"]
        == result["classical"]["lots"]["fortune"]["longitude"]
    )
    assert result["classical_patterns"]["sect_benefic"] == "Jupiter"
    assert result["classical"]["ptolemy"]["planets"]["Sun"]["natural_sect"] == "day"


@pytest.mark.parametrize("house_system", ["P", "W", "V", "D"])
def test_predictive_sect_agrees_with_natal_independent_of_houses(house_system):
    birth = build_astro_birth_info(**BIRTH)
    assert (
        determine_sect(build_natal_subject(birth, house_system=house_system)) == "day"
    )


@pytest.mark.parametrize("month,expected", [(6, "day"), (12, "night")])
def test_polar_sect_uses_sun_not_arbitrary_house(month, expected):
    result = calculate_core_chart_analysis(
        **{
            **BIRTH,
            "birth_month": month,
            "birth_day": 21,
            "birth_hour": 12,
            "birth_latitude": 80.0,
        },
        chart_variant="hellen_chart",
    )
    assert result["classical"]["sect"] == expected


@pytest.mark.parametrize("year,month,day,hour", [(2024, 3, 10, 2), (2024, 11, 3, 1)])
def test_gap_or_fold_cannot_silently_select_birth_instant(year, month, day, hour):
    result = calculate_core_chart_analysis(
        **{
            **BIRTH,
            "birth_year": year,
            "birth_month": month,
            "birth_day": day,
            "birth_hour": hour,
            "birth_timezone": "America/New_York",
        },
        chart_variant="chart",
    )
    assert result["error_code"] == "validation_error"
    assert "planets" not in result


def test_fold_resolves_to_two_distinct_instants_with_explicit_offsets():
    base = {**BIRTH, "birth_month": 11, "birth_day": 3, "birth_hour": 1}
    a = build_astro_birth_info(**{**base, "birth_timezone": "-04:00"})
    b = build_astro_birth_info(**{**base, "birth_timezone": "-05:00"})
    assert b.utc_datetime - a.utc_datetime == timedelta(hours=1)


def test_gregorian_jd_is_continuous_and_offset_and_subsecond_aware():
    # USNO/J2000 epoch and continuity, not a copy of our conversion algorithm.
    utc = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    assert _julian_day(utc) == 2451545.0
    assert _julian_day(utc.astimezone(timezone(timedelta(hours=5.5)))) == 2451545.0
    assert (
        _julian_day(utc + timedelta(microseconds=500000)) - _julian_day(utc)
    ) * 86400 == pytest.approx(0.5, abs=0.00004)
    assert _julian_day(datetime(1500, 1, 1, 12)) == 2268924.0
    assert (
        _julian_day(datetime(1582, 10, 15)) - _julian_day(datetime(1582, 10, 14)) == 1
    )


def test_geometric_horizon_fallback_matches_coordinate_rotation(monkeypatch):
    swe = pytest.importorskip("swisseph")
    jd = 2460389.7708333335
    probes = [
        (lon, lat, lam, beta)
        for lon in (-120, 0, 120)
        for lat in (-80, -40, 0, 40, 80)
        for lam, beta in [(0, 0), (90, 5), (180, -5), (270, 0)]
    ]
    expected = [
        swe.azalt(jd, swe.ECL2HOR, (lon, lat, 0), 0, 0, (lam, beta, 1))[1]
        for lon, lat, lam, beta in probes
    ]
    monkeypatch.setattr(runtime, "swe", None)
    for probe, truth in zip(probes, expected):
        actual, method = horizon_altitude(jd, *probe)
        assert abs(actual - truth) < 0.02
        assert method == "approximate_geometric_altitude"


@pytest.mark.parametrize(
    "reference",
    json.loads((FIXTURES / "western-horizons.json").read_text())["references"],
)
def test_public_western_planets_against_frozen_jpl(reference, monkeypatch):
    fixture = json.loads((FIXTURES / "western-horizons.json").read_text())
    assert (
        hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
        == reference["response_sha256"]
    )
    # Exercise the package's guaranteed file-free Moshier baseline explicitly.
    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", "/tmp/fatebridge-western-empty-ephemeris"
    )
    with ephemeris_runtime.preserve_ephemeris_path():
        runtime.swe.set_ephe_path("/tmp/fatebridge-western-empty-ephemeris")
        for row in reference["rows"]:
            moment = datetime.fromisoformat(row["utc"])
            result = calculate_core_chart_analysis(
                **{
                    **BIRTH,
                    "birth_year": moment.year,
                    "birth_month": moment.month,
                    "birth_day": moment.day,
                    "birth_hour": moment.hour,
                    "birth_minute": moment.minute,
                },
                chart_variant="chart",
            )
            assert "error" not in result
            point = next(p for p in result["planets"] if p["id"] == reference["body"])
            delta = (
                abs(
                    (point["longitude"] - row["apparent_ecliptic_longitude"] + 180)
                    % 360
                    - 180
                )
                * 3600
            )
            assert delta <= fixture["tolerance_arcseconds"], (
                reference["body"],
                row["utc"],
                delta,
            )
            assert (
                abs(point["latitude"] - row["apparent_ecliptic_latitude"]) * 3600
                <= fixture["tolerance_arcseconds"]
            )


def test_primary_text_triangles_are_not_a_dorothean_substitution():
    ref = json.loads((FIXTURES / "western-ptolemy-robbins-1940.json").read_text())
    for row in ref["signs"]:
        for sect in ("day", "night"):
            layer = build_ptolemy_layer(
                {"Sun": row["longitude"], "Mars": row["longitude"]}, sect, tropical=True
            )
            fact = layer["planets"]["Sun"]
            assert fact["domicile_lord"] == row["domicile_lord"]
            assert fact["triplicity_primary"] == row[sect]["primary"]
            assert fact["triplicity_co_ruler"] == row[sect]["co_ruler"]
            assert "score" not in fact
    assert (
        build_ptolemy_layer({"Sun": 0}, "day", tropical=False)["status"]
        == "unsupported_zodiac"
    )


def test_primary_text_exaltations_and_mercury_sect():
    ref = json.loads((FIXTURES / "western-ptolemy-robbins-1940.json").read_text())
    signs = [row["sign"] for row in ref["signs"]]
    for planet, exaltation in ref["exaltations"].items():
        longitude = signs.index(exaltation) * 30 + 15
        result = build_ptolemy_layer({planet: longitude}, "day", tropical=True)
        assert result["planets"][planet]["in_exaltation"] is True
        result = build_ptolemy_layer(
            {planet: (longitude + 180) % 360}, "day", tropical=True
        )
        assert result["planets"][planet]["in_depression"] is True
    for mercury, expected in [(5.0, "day"), (15.0, "night"), (10.0, None)]:
        fact = build_ptolemy_layer(
            {"Sun": 10.0, "Mercury": mercury}, "day", tropical=True
        )
        assert fact["planets"]["Mercury"]["natural_sect"] == expected


def test_iers_leap_second_transition_and_future_assumption_are_explicit():
    before = ephemeris_time(datetime(2016, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
    after = ephemeris_time(datetime(2017, 1, 1, tzinfo=timezone.utc))
    assert (after.jd_tt - before.jd_tt) * 86400 == pytest.approx(2.0, abs=0.00004)
    assert (after.jd_tt - after.jd_utc) * 86400 == pytest.approx(69.184, abs=0.00004)
    future = ephemeris_time(datetime(2099, 12, 31, tzinfo=timezone.utc))
    assert future.future_leap_seconds_assumed_unchanged is True
    assert (future.jd_tt - future.jd_utc) * 86400 == pytest.approx(69.184, abs=0.00004)
    assert "IERS" in future.method
    assert leap_table()["entries"][-1]["tai_minus_utc_seconds"] == 37


def test_unknown_altitude_never_fabricates_above_horizon_from_house():
    from fatebridge.core.classical_western import build_planet_classical

    result = build_planet_classical(
        planet="Sun",
        sign="Aries",
        degree_in_sign=1,
        longitude=1,
        house=1,
        sun_longitude=1,
        chart_sect="day",
    )
    assert result["above_horizon"] is None
    assert result["in_halb"] is None


def test_out_of_bounds_uses_epoch_obliquity_instead_of_modern_constant():
    from fatebridge.core.classical_western import out_of_bounds

    assert out_of_bounds(23.5, 23.7) is False
    assert out_of_bounds(23.5, 23.3) is True
    assert out_of_bounds(23.5, None) is None
    result = calculate_core_chart_analysis(**{**BIRTH, "birth_year": 1500})
    assert 23.49 < result["classical"]["obliquity"] < 23.52


def test_partial_native_geometry_failure_is_not_labeled_full_runtime_precision(
    monkeypatch,
):
    swe = pytest.importorskip("swisseph")

    def fail(*args, **kwargs):
        raise RuntimeError("injected horizon failure")

    monkeypatch.setattr(swe, "azalt", fail)
    result = calculate_core_chart_analysis(**BIRTH, hsys=0)
    assert "error" not in result
    assert result["chart_profile"]["horizon_method"] == "approximate_geometric_altitude"
    assert (
        result["chart_profile"]["engine_precision"] == "mixed_precision_runtime_model"
    )
