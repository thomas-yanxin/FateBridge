"""Corrected model solar label and trace through real REST/MCP/CLI routes."""

from datetime import datetime

import pytest

from fatebridge.core import ephemeris_runtime as e
from tests.test_jyotish_solar_display import SYNTHETIC
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
def test_model_solar_label_and_source_projection_agree_on_all_three_surfaces(
    monkeypatch, capsys, tmp_path, key
):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(empty))
    e.configure_ephemeris_path(str(empty))
    payload = {**SYNTHETIC, "use_true_solar_time": True, "divisions": []}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        ["person_info.utc_datetime", "india.profile.clock_context"],
    )
    context = result["india"]["profile"]["clock_context"]
    expected = datetime.fromisoformat("2000-01-01T13:11:38.671836")
    actual = datetime.fromisoformat(context["solar_wall_datetime"])
    assert abs((actual - expected).total_seconds()) <= 0.0002
    assert result["person_info"]["utc_datetime"] == "2000-01-01T12:34:56.123456+00:00"
    assert context["physical_instant_shifted"] is False
    assert (
        context["display_equation_of_time_method"]
        == "apparent_solar_hour_angle_shared_TT_model_UT1"
    )
    display = context["solar_display_context"]
    assert display["representation_status"] == "available"
    assert display["julian_day_tt"] == display["sun_julian_day_tt"]
    assert display["solar_ephemeris_model"] == "moshier"
