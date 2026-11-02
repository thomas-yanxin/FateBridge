"""Original overlap birth and replay evidence on each public local transport."""

import pytest

from fatebridge.core import ephemeris_runtime as e
from tests.test_jyotish_segment_motion import full_files
from tests.test_jyotish_sources import data18, restore_runtime  # noqa: F401
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_chart"])
def test_replayed_center_source_evidence_survives_rest_mcp_cli(
    data18, monkeypatch, capsys, key
):
    directory = full_files(data18)
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    e.configure_ephemeris_path(str(directory))
    payload = dict(
        birth_year=2400,
        birth_month=1,
        birth_day=10,
        birth_hour=20,
        birth_minute=36,
        birth_second=1,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        birth_time_uncertainty_minutes=1,
        divisions=[],
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "person_info.utc_datetime",
            "chart_profile.longitude_motion.complete_position_derivatives",
            "india.profile.clock_context",
        ],
    )
    assert result["person_info"]["utc_datetime"] == "2400-01-10T20:36:01+00:00"
    assert (
        result["india"]["profile"]["clock_context"]["physical_instant_shifted"] is False
    )
    policies = result["chart_profile"]["longitude_motion"][
        "complete_position_derivatives"
    ]
    for label in [
        "Sun:tropical",
        "Mercury:tropical",
        "Venus:tropical",
        "Mars:tropical",
    ]:
        policy = policies[label]
        assert policy["method_id"] == "fatebridge_complete_position_derivative_v8"
        assert policy["status"] == "applied"
        replay = policy["source_branch_motion"]["center_file_replay"]
        assert replay["center_native_state_reproduced_exactly"] is True
        assert replay["displayed_native_position_changed"] is False
        assert {w["slot"] for w in replay["center_windows"]} == {0, 1}
