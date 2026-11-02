"""The canonical D1 rate and retained native rate agree across local transports."""

from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from tests.test_jyotish_longitude_motion import REF, from_tt
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_corrected_d1_motion_and_failed_native_value_survive_rest_mcp_cli(
    monkeypatch, capsys, key
):
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[1] / "ephe"))
    row = REF["rows"][0]
    moment = from_tt(row["jd_tt"]).utc_datetime
    payload = dict(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=0,
        divisions=[9, 10],
        ephemeris_policy="require_data_files",
        name="工程合成：D1速度回归",
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 601
    body = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.charts.D1.planets",
            "india.profile.julian_day_tt",
            "india.profile.ruleset_id",
            "india.rule_trace",
        ],
    )
    assert body["india"]["profile"]["ruleset_id"] == "parashari_lahiri_core_v29"
    assert body["india"]["profile"]["julian_day_tt"] == row["jd_tt"]
    sun = next(p for p in body["india"]["charts"]["D1"]["planets"] if p["id"] == "Sun")[
        "physical_state"
    ]
    reference = row["erfa_standard_lahiri"]["longitude_speed_degrees_per_day"]
    assert (
        abs(sun["longitude_speed_degrees_per_day"] - reference) * 3600
        <= REF["rate_tolerance_arcsec_per_day"]
    )
    assert (
        abs(sun["longitude_speed_native_degrees_per_day"] - reference) * 3600
        > REF["rate_tolerance_arcsec_per_day"]
    )
    assert (
        sun["longitude_motion_context"]["rate_basis"]
        == "complete_apparent_position_derivative"
    )
    assert any(
        r["rule_id"] == "jyotish.longitude_motion.v2"
        for r in body["india"]["rule_trace"]
    )
    moon = next(
        p for p in body["india"]["charts"]["D1"]["planets"] if p["id"] == "Moon"
    )["physical_state"]
    motion = moon["longitude_motion_context"]
    assert motion["rate_basis"] == "native_plus_lunar_fixed_frame_source_derivative"
    assert motion["shared_method_id"] == "fatebridge_apparent_longitude_motion_v4"
    assert motion["complete_position_derivative"]["status"] == "not_applied"
    spatial = motion["lunar_light_time"]["spatial_aberration"]
    assert spatial["status"] == "applied" and spatial["positions_unchanged"] is True
    assert (
        motion["corrections_degrees_per_day"]["spatial_aberration_correction"]
        == spatial["longitude_speed_correction"]
    )
    assert moon["longitude_speed_degrees_per_day"] == (
        moon["longitude_speed_native_degrees_per_day"]
        + motion["corrections_degrees_per_day"]["light_time_correction"]
        + motion["corrections_degrees_per_day"]["spatial_aberration_correction"]
        + motion["corrections_degrees_per_day"]["lunar_source_remainder_correction"]
    )
    fixed = motion["lunar_light_time"]["fixed_frame_source_derivative"]
    assert fixed["status"] == "applied"
    assert fixed["center_native_states_reproduced_exactly"] is True
    assert fixed["center_file_context_reproduced_exactly"] is True
    assert fixed["complete_moving_frame_derivative_certified"] is False
    assert fixed["native_binary_arithmetic_identity_certified"] is False
    assert (
        fixed["longitude_speed_correction"]
        == motion["corrections_degrees_per_day"]["lunar_source_remainder_correction"]
    )
