"""Actual REST, native MCP and CLI carry the same physical/solar clock split."""

import pytest

from tests.test_jyotish_civil_instant import BIRTH
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
@pytest.mark.parametrize("solar", [False, True])
def test_recorded_instant_and_solar_label_survive_three_surfaces(
    monkeypatch, capsys, key, solar
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        {**BIRTH, "divisions": [], "use_true_solar_time": solar},
        ["person_info.utc_datetime", "india.profile.clock_context", "india.charts.D1"],
    )
    assert result["person_info"]["utc_datetime"] == "1990-04-06T01:33:00+00:00"
    context = result["india"]["profile"]["clock_context"]
    assert context["calculation_utc_datetime"] == "1990-04-06T01:33:00+00:00"
    assert context["physical_instant_shifted"] is False
    assert context["solar_display_requested"] is solar
    if solar:
        assert context["solar_wall_datetime"].startswith("1990-04-06T09:36:")
        assert "+" not in context["solar_wall_datetime"]
    else:
        assert context["solar_wall_datetime"] is None


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari"])
def test_nested_clock_projection_preserves_model_window_independence(
    monkeypatch, capsys, key
):
    payload = {
        **BIRTH,
        "birth_year": 2051,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 0,
        "birth_minute": 0,
        "birth_timezone": "UTC",
        "birth_longitude": -180,
        "birth_latitude": 0,
        "divisions": [],
        "use_true_solar_time": True,
        "cheshta_model": "simon1994_j2000",
    }
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2052
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile.clock_context.solar_wall_datetime",
            "india.profile.clock_context.calculation_utc_datetime",
            "india.profile.clock_context.physical_instant_shifted",
            "india.strengths.cheshta_bala.model_context.status",
        ],
    )
    context = result["india"]["profile"]["clock_context"]
    assert context["solar_wall_datetime"].startswith("2050-12-31T")
    assert context["calculation_utc_datetime"] == "2051-01-01T00:00:00+00:00"
    assert context["physical_instant_shifted"] is False
    assert (
        result["india"]["strengths"]["cheshta_bala"]["model_context"]["status"]
        == "outside_validated_model_window"
    )
