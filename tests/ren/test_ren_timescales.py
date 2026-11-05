"""Independent atomic-time offsets and fractional solar-boundary fidelity."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac
from fatebridge.services.metaphysics import calculate_liureng_gods

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads(
    (ROOT / "tests/fixtures/ren_timescale_v1/reference.json").read_text()
)


def civil_jd(moment):
    # NAOJ's 2000-01-01 JDN 2451545, with JD beginning at noon.
    return (
        2451544.5
        + (moment - datetime(2000, 1, 1, tzinfo=timezone.utc)).total_seconds() / 86400
    )


@pytest.mark.parametrize("case", REFERENCE["synthetic_clock_cases"])
def test_tt_root_reaches_correct_civil_clock_without_treating_ut1_as_utc(
    case, monkeypatch
):
    civil = datetime.fromisoformat(case["utc"])
    jd = civil_jd(civil)
    if "tai_minus_utc_seconds" in case:
        offset = case["tai_minus_utc_seconds"]
    else:
        row = case["tai_minus_utc_formula"]
        offset = (
            row["offset_seconds"]
            + (jd - 2400000.5 - row["reference_mjd"]) * row["rate_seconds_per_day"]
        )
    expected_tt = jd + (offset + 32.184) / 86400
    calls = []

    def simulated_sun(operation, at, body, flags):
        assert operation == "calc"  # TT, rather than calc_ut on a UTC-like JD.
        calls.append(at)
        return ((at - expected_tt) % 360, 0, 1, 0, 0, 0), flags

    monkeypatch.setattr(almanac, "ephemeris_call", simulated_sun)
    actual = almanac._solar_term_utc_via_swe(civil.year, 0, civil)
    assert actual is not None
    assert abs((actual - civil).total_seconds()) < 0.0002
    assert calls and abs(calls[-1] - expected_tt) * 86400 < 0.0002


def test_serialized_term_keeps_the_same_fractional_boundary_as_computation():
    terms = almanac.get_solar_terms_for_year(2026, "Asia/Shanghai")
    term = next(t for t in terms if 0 < t.moment.microsecond < 500000)
    value = term.as_dict()["datetime"]
    assert datetime.fromisoformat(value) == term.moment.replace(tzinfo=None)
    before = term.moment - timedelta(microseconds=1)
    after = term.moment + timedelta(microseconds=1)
    assert (
        almanac.get_adjacent_solar_terms(before, "Asia/Shanghai")[0].name != term.name
    )
    assert almanac.get_adjacent_solar_terms(after, "Asia/Shanghai")[0].name == term.name


@pytest.mark.parametrize(
    "year,month,day,future",
    [(1969, 5, 17, False), (2026, 2, 19, False), (2084, 3, 21, True)],
)
def test_actual_ren_dependencies_disclose_the_time_scale_and_future_assumption(
    year, month, day, future
):
    result = calculate_liureng_gods(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    assert "error" not in result
    dependencies = result["liureng"]["calendar_policy"]["solar_term_dependencies"]
    assert all(row["solver_time_scale"] == "TT" for row in dependencies)
    assert all(
        row["future_leap_seconds_assumed_unchanged"] == future for row in dependencies
    )
    assert all(row["leap_table_expires_at"] for row in dependencies)
    if year == 1969:
        assert all(
            row["civil_time_method"].startswith("IERS_1961_1971")
            for row in dependencies
        )
    assert "小数秒仅为数值分辨率" in result["snapshot_text"]


def test_leap_second_cannot_be_fabricated_as_next_day_by_the_solar_solver(monkeypatch):
    from fatebridge.core.astro import time_scales

    def unavailable_label(value):
        raise ValueError("UTC leap second not representable by datetime")

    monkeypatch.setattr(time_scales, "datetime_from_tt", unavailable_label)
    from fatebridge.core.solar_term_clock import SolarTermClockError

    with pytest.raises(SolarTermClockError) as failure:
        almanac._solar_term_utc_via_swe(
            2026, 0, datetime(2026, 3, 20, tzinfo=timezone.utc)
        )
    assert isinstance(failure.value.__cause__, ValueError)
    assert (
        str(failure.value.__cause__) == "UTC leap second not representable by datetime"
    )
