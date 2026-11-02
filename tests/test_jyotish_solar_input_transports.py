"""Explicit historical input clocks through actual REST/native MCP/CLI."""

import pytest

from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_explicit_input_label_and_resolved_instant_survive_three_surfaces(
    monkeypatch, capsys, key, basis
):
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_minute=1,
        birth_second=17,
        birth_microsecond=123456,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis=basis,
        divisions=[],
        birth_time_uncertainty_minutes=1,
    )
    if key == "astro_chart":
        data["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        data.update(analysis_year=2026, analysis_timezone="Asia/Shanghai")
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        data,
        [
            "person_info.utc_datetime",
            "person_info.clock_conversion",
            "india.profile.clock_context",
            "india.birth_time_sensitivity",
        ],
    )
    clock = result["india"]["profile"]["clock_context"]
    assert clock["input_clock_basis"] == basis
    assert clock["input_wall_datetime"] == "1879-05-14T23:01:17.123456"
    assert clock["calculation_utc_datetime"] == result["person_info"]["utc_datetime"]
    assert clock["recorded_datetime"] is None
    assert (
        result["person_info"]["clock_conversion"]["input_calendar"]
        == "proleptic_gregorian"
    )
    if basis == "local_mean_solar":
        assert clock["calculation_utc_datetime"] == "1879-05-14T22:21:17.123456+00:00"
    else:
        assert clock["input_clock_conversion"]["solar_ephemeris_models_observed"]
    bounds = result["india"]["birth_time_sensitivity"]["clock_interval"]
    assert bounds["input_clock_basis"] == basis
    assert bounds["input_wall_start"] == "1879-05-14T23:00:17.123456"


def test_target_zone_and_nested_clock_fields_survive_three_surfaces(
    monkeypatch, capsys
):
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis="local_mean_solar",
        analysis_year=2026,
        analysis_hour=8,
        analysis_timezone="Asia/Shanghai",
        divisions=[],
    )
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        data,
        [
            "analysis_context",
            "india.profile.clock_context.input_wall_datetime",
            "india.profile.clock_context.calculation_utc_datetime",
            "india.profile.clock_context.input_clock_conversion.solar_ephemeris_policy",
        ],
    )
    assert (
        result["analysis_context"]["analysis_datetime"] == "2026-01-01T08:00:00+08:00"
    )
    assert result["analysis_context"]["timezone_basis"] == "explicit_analysis_timezone"
    assert (
        result["india"]["profile"]["clock_context"]["input_wall_datetime"]
        == "1879-05-14T23:00:00"
    )
    assert (
        result["india"]["profile"]["clock_context"]["input_clock_conversion"][
            "solar_ephemeris_policy"
        ]
        == "auto"
    )
