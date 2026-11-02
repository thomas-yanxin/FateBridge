"""Corrected centres and unchanged input epochs survive every local transport."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.compressed_ephemeris import POLICY_ID
from fatebridge.core.output_ephemeris import CompressedEndpointPolicy
from tests.test_jyotish_segment_motion import full_files
from tests.test_jyotish_sources import data18 as data18_fixture
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import call_surfaces

data18 = data18_fixture

REFERENCE = Path(__file__).parent / "fixtures/jyotish-endpoint-reference.json"


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_actual_endpoint_policy_and_corrected_centre_across_transports(
    data18, monkeypatch, capsys, key
):
    directory = full_files(data18)
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    birth = json.loads(REFERENCE.read_text())["birth_inputs"][1]
    instant = datetime.fromisoformat(birth["civil_utc"])
    payload = dict(
        birth_year=instant.year,
        birth_month=instant.month,
        birth_day=instant.day,
        birth_hour=instant.hour,
        birth_minute=instant.minute,
        birth_second=instant.second,
        birth_microsecond=instant.microsecond,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = instant.year + 1
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "person_info.utc_datetime",
            "india.profile.julian_day_tt",
            "india.profile.native_execution_context.compressed_file_endpoint_policy",
            "india.charts.D1.planets",
            "india.profile.native_coordinate_contexts.ecliptic_Sun",
            "india.profile.apparent_position_policy.bodies.Jupiter",
        ],
    )
    profile = result["india"]["profile"]
    assert profile["julian_day_tt"] == birth["epoch_jd_tt"]
    assert result["person_info"]["utc_datetime"] == instant.isoformat()
    policy = profile["native_execution_context"]["compressed_file_endpoint_policy"]
    CompressedEndpointPolicy.model_validate(policy)
    assert policy["policy_id"] == POLICY_ID
    assert policy["input_instant_shifted"] is False
    assert policy["calls_corrected_so_far"] > 0
    assert policy["native_states_changed_so_far"] > 0
    context = profile["native_coordinate_contexts"]["ecliptic_Sun"]
    assert context["policy_id"] == POLICY_ID
    assert context["private_native_cache_reset"]
    assert context["original_native_state"] is None
    assert context["native_state_changed"] is None
    assert context["physical_jd_tt"] == birth["epoch_jd_tt"]
    assert context["physical_instant_shifted"] is False
    jupiter = profile["apparent_position_policy"]["bodies"]["Jupiter"]
    assert jupiter["unbent_ray_domain"] == "behind_solar_disc"
    assert jupiter["position_interpretation"] == "virtual_native_solar_disc_extension"
    assert jupiter["observational_accuracy_certified"] is False
    sun = next(
        p for p in result["india"]["charts"]["D1"]["planets"] if p["id"] == "Sun"
    )
    assert sun["longitude"] == context["selected_native_state"][0] % 360
