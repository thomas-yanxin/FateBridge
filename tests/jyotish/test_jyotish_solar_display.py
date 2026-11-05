"""Solar display follows the same physical time axis, with recorded data intact.

The 18 external labels reuse three previously exposed NASA/ERFA epochs. State
conditions and repeated routes are not independent astronomical/prediction cases.
"""

import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.source_session import source_session
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_display import normalize_solar_display
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.jyotish import calculate_vimshottari
from tests.jyotish.test_jyotish_sources import data18, restore_runtime  # noqa: F401

FIXTURES = Path(__file__).parents[1] / "fixtures"
REFERENCE = json.loads((FIXTURES / "jyotish-solar-input-reference.json").read_text())
LAT_ROWS = [r for r in REFERENCE["cases"] if r["basis"] == "local_apparent_solar"]
SYNTHETIC = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=34,
    birth_second=56,
    birth_microsecond=123456,
    birth_timezone="UTC",
    birth_longitude=10,
    birth_latitude=0,
)


@pytest.mark.parametrize("mode", ["clean", "manual", "stale"])
def test_prebuilt_and_service_display_preserve_the_frozen_physical_control(
    tmp_path, mode
):
    done = subprocess.run(
        [
            sys.executable,
            str(
                (
                    Path(__file__).parents[2]
                    / "tests/support/jyotish_solar_display_subject.py"
                )
            ),
            mode,
            str(tmp_path / mode),
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert done.returncode == 0, done.stderr
    actual = json.loads(done.stdout.splitlines()[-1])
    # Recorded before production repair, on the already-existing physical
    # solar clock. This is a state/wiring control, not independent sky truth.
    expected = datetime.fromisoformat("2000-01-01T13:11:38.671836")
    for route in ["SDK_display", "service_display"]:
        context = actual[route]
        assert (
            abs(
                (
                    datetime.fromisoformat(context["solar_wall_datetime"]) - expected
                ).total_seconds()
            )
            <= 0.0002
        )
        assert context["calculation_utc_datetime"] == "2000-01-01T12:34:56.123456+00:00"
        assert context["physical_instant_shifted"] is False
        assert (
            context["solar_display_context"]["supplied_derived_display_used"] is False
        )


@pytest.mark.parametrize("row", LAT_ROWS)
def test_forward_display_against_unchanged_frozen_nasa_erfa_labels(row):
    moment = datetime.fromisoformat(row["utc"])
    result = calculate_vimshottari(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_timezone="UTC",
        birth_longitude=row["longitude"],
        birth_latitude=0,
        use_true_solar_time=True,
        divisions=[],
        analysis_year=2026,
    )
    assert "error" not in result, result
    context = result["india"]["profile"]["clock_context"]
    actual = datetime.fromisoformat(context["solar_wall_datetime"])
    expected = datetime.fromisoformat(row["input_wall_datetime"])
    assert abs((actual - expected).total_seconds()) < REFERENCE["utc_tolerance_seconds"]
    assert context["calculation_utc_datetime"] == row["utc"]
    display = context["solar_display_context"]
    assert (
        display["julian_day_tt"]
        == display["sun_julian_day_tt"]
        == result["india"]["profile"]["julian_day_tt"]
    )


@pytest.mark.parametrize(
    "zone,year,month,day,hour,minute,longitude",
    [
        ("UTC", 2000, 1, 1, 23, 59, 180),
        ("UTC", 2000, 1, 1, 0, 1, -180),
        ("Asia/Shanghai", 1990, 6, 15, 0, 5, 121.4667),
        ("America/New_York", 2024, 6, 21, 0, 5, -74),
        ("UTC", 1850, 1, 1, 12, 0, 10),
        ("UTC", 1965, 2, 1, 12, 34, -73.98765),
    ],
)
def test_hour_angle_geometry_and_civil_offset_consistency(
    zone, year, month, day, hour, minute, longitude
):
    options = dict(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_timezone=zone,
        birth_longitude=longitude,
        birth_latitude=0,
    )
    birth = build_astro_birth_info(**options, preserve_instant=True)
    raw = positions(birth)
    result = calculate_core_chart_analysis(
        **options, chart_variant="india_chart", use_true_solar_time=True, divisions=[]
    )
    assert "error" not in result, result
    context = result["india"]["profile"]["clock_context"]
    actual = datetime.fromisoformat(context["solar_wall_datetime"])
    # Independent hour-angle/day-wrap wiring using already-returned native
    # coordinates. Not an independent Sun or Earth-orientation model.
    phase_seconds = (
        (
            raw["local_apparent_sidereal_meridian"]
            - raw["equatorial"]["Sun"]["right_ascension"]
            + 180
        )
        % 360
        * 240
    )
    dut1 = (
        (raw["julian_day_ut"] - raw["julian_day_utc"]) * 86400
        if raw["julian_day_utc"] is not None
        else 0.0
    )
    mean_wall = birth.utc_datetime.replace(tzinfo=None) + timedelta(
        seconds=dut1 + longitude * 240
    )
    expected = mean_wall.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        seconds=phase_seconds
    )
    if expected - mean_wall > timedelta(hours=12):
        expected -= timedelta(days=1)
    elif expected - mean_wall < -timedelta(hours=12):
        expected += timedelta(days=1)
    assert abs((actual - expected).total_seconds()) <= 0.0002
    correction = (
        actual - birth.local_datetime.replace(tzinfo=None)
    ).total_seconds() / 60
    assert abs(correction - context["solar_correction_minutes"]) <= 0.000051
    assert (
        result["person_info"]["true_solar"]["correction_minutes"]
        == context["solar_correction_minutes"]
    )
    assert context["calculation_utc_datetime"] == birth.utc_datetime.isoformat()


def test_untrusted_derived_label_is_replaced_without_mutating_the_recorded_object():
    plain = build_astro_birth_info(**SYNTHETIC, preserve_instant=True)
    supplied = replace(
        plain,
        applied_true_solar=True,
        solar_datetime=plain.local_datetime + timedelta(days=2),
        solar_correction_minutes=999999,
    )
    result = build_india(supplied, divisions=[])
    reference = build_india(plain, divisions=[])
    for key in ["charts", "strengths", "reading_basis", "topic_evidence"]:
        assert result[key] == reference[key]
    assert supplied.solar_correction_minutes == 999999
    assert result["profile"]["clock_context"]["solar_correction_minutes"] != 999999
    assert result["profile"]["clock_context"]["physical_instant_shifted"] is False


def test_unrequested_stale_derived_display_is_not_reported_as_a_label():
    plain = build_astro_birth_info(**SYNTHETIC, preserve_instant=True)
    supplied = replace(
        plain,
        solar_datetime=plain.local_datetime + timedelta(days=2),
        solar_correction_minutes=999999,
    )
    context = build_india(supplied, divisions=[])["profile"]["clock_context"]
    assert context["solar_display_requested"] is False
    assert context["solar_display_status"] == "not_requested"
    assert context["solar_wall_datetime"] is None
    assert context["solar_correction_minutes"] == 0
    assert context["calculation_utc_datetime"] == plain.utc_datetime.isoformat()
    assert supplied.solar_correction_minutes == 999999


@pytest.mark.native_engine_fault
def test_same_instant_different_civil_offsets_do_not_share_a_wall_correction():
    utc = build_astro_birth_info(**SYNTHETIC, preserve_instant=True)
    other = utc.local_datetime.astimezone(timezone(timedelta(hours=-5)))
    shifted = replace(
        utc, timezone="-05:00", local_datetime=other, recorded_datetime=other
    )
    with source_session():
        a, _ = normalize_solar_display(utc, "auto", requested=True)
        b, _ = normalize_solar_display(shifted, "auto", requested=True)
    assert a.solar_datetime == b.solar_datetime
    assert b.solar_correction_minutes - a.solar_correction_minutes == pytest.approx(300)
    assert a.utc_datetime == b.utc_datetime == utc.utc_datetime


def test_strict_file_backend_supplies_the_display_sun(data18):
    birth = build_astro_birth_info(**SYNTHETIC, preserve_instant=True)
    result = build_india(
        replace(birth, applied_true_solar=True),
        divisions=[],
        ephemeris_policy="require_data_files",
    )
    display = result["profile"]["clock_context"]["solar_display_context"]
    assert display["solar_ephemeris_model"] == "swieph"
    assert display["physical_sun_source"]["files"]
    assert (
        display["julian_day_tt"]
        == display["sun_julian_day_tt"]
        == result["profile"]["julian_day_tt"]
    )


@pytest.mark.native_engine_fault
def test_indian_display_does_not_use_the_generic_utc_as_ut1_path(monkeypatch):
    import fatebridge.utils.solar_time as generic

    def forbidden(*args, **kwargs):
        raise RuntimeError("Generic approximation must not supply Indian display")

    monkeypatch.setattr(generic, "calculate_equation_of_time_minutes", forbidden)
    options = {**SYNTHETIC, "use_true_solar_time": True, "divisions": []}
    for result in [
        calculate_vimshottari(**options, analysis_year=2026),
        calculate_core_chart_analysis(**options, chart_variant="india_chart"),
    ]:
        assert "error" not in result, result


def test_conflicting_explicit_solar_input_options_still_reach_validation():
    options = {
        **SYNTHETIC,
        "birth_clock_basis": "local_apparent_solar",
        "birth_timezone": None,
        "use_true_solar_time": True,
        "divisions": [],
    }
    for result in [
        calculate_vimshottari(**options, analysis_year=2026),
        calculate_core_chart_analysis(**options, chart_variant="india_chart"),
    ]:
        assert result["error_code"] == "validation_error"
        assert "use_true_solar_time=false" in result["error"]
