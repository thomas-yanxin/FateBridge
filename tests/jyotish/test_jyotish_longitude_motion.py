"""Independent exposed solar values, source gaps and motion-operand semantics."""

import json
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.jyotish.jyotish import positions
from fatebridge.core.jyotish.jyotish_strength import physical_state
from tests.unit_test.fixtures.jyotish_sources import (  # noqa: F401
    birth,
    data18,
    edge_birth,
    from_tt,
    restore_runtime,
)

REF = json.loads(
    (Path(__file__).parents[2] / "tests/fixtures")
    .joinpath("jyotish-d1-sun-motion-regression.json")
    .read_text()
)


@pytest.mark.parametrize("row", REF["rows"], ids=lambda r: r["date_tt"])
def test_d1_sun_uses_qualified_rate_and_keeps_original_failed_native_value(row) -> None:
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    raw = positions(from_tt(row["jd_tt"]), ephemeris_policy="require_data_files")
    assert raw["julian_day_tt"] == row["jd_tt"]
    state = raw["physical_states"]["Sun"]
    expected = row["erfa_standard_lahiri"]["longitude_speed_degrees_per_day"]
    assert (
        abs(state["longitude_speed_degrees_per_day"] - expected) * 3600
        <= REF["rate_tolerance_arcsec_per_day"]
    )
    assert (
        abs(state["longitude_speed_native_degrees_per_day"] - expected) * 3600
        > REF["rate_tolerance_arcsec_per_day"]
    )
    context = state["longitude_motion_context"]
    assert context["rate_basis"] == "complete_apparent_position_derivative"
    assert context["epoch_jd_tt"] == row["jd_tt"]
    assert context["daily_mean_motion_used"] is False
    assert context["station_time_accuracy_certified"] is False
    assert context["source_files"]
    assert all(len(f["sha256"]) == 64 for f in context["source_files"])


def test_all_nine_rates_have_honest_per_body_coverage_and_antipode() -> None:
    e.configure_ephemeris_path(str(Path(__file__).resolve().parents[2] / "ephe"))
    raw = positions(birth(), ephemeris_policy="require_data_files")
    states = raw["physical_states"]
    for name in ("Sun", "Mercury", "Venus", "Mars"):
        assert (
            states[name]["longitude_motion_context"]["rate_basis"]
            == "complete_apparent_position_derivative"
        )
    assert (
        states["Moon"]["longitude_motion_context"]["rate_basis"]
        == "native_plus_lunar_fixed_frame_source_derivative"
    )
    for name in ("Jupiter", "Saturn"):
        context = states[name]["longitude_motion_context"]
        assert context["rate_basis"] == "native_only"
        assert context["complete_position_derivative"]["status"] == "not_applied"
    assert (
        states["Rahu"]["longitude_motion_context"]["rate_basis"]
        == "native_analytical_node"
    )
    assert (
        states["Ketu"]["longitude_motion_context"]["rate_basis"]
        == "derived_antipode_of_Rahu"
    )
    assert (
        states["Ketu"]["longitude_speed_degrees_per_day"]
        == states["Rahu"]["longitude_speed_degrees_per_day"]
    )


def test_missing_auxiliary_file_retains_only_exactly_reproduced_center(data18) -> None:
    from datetime import timedelta

    subject = edge_birth()
    raw = positions(subject, subject.utc_datetime - timedelta(seconds=60))
    assert raw["ephemeris_by_body"]["Sun"] == "swieph"
    state = raw["physical_states"]["Sun"]
    assert (
        state["longitude_speed_degrees_per_day"]
        == state["longitude_speed_native_degrees_per_day"]
    )
    context = state["longitude_motion_context"]
    assert context["rate_basis"] == "native_only"
    missing = context["complete_position_derivative"]
    assert missing["reason"] == "auxiliary_sample_backend_changed"
    assert missing["actual_sample_model"] == "moshier"
    assert missing["center_native_state_reproduced_exactly"] is True
    assert missing["center_file_context_reproduced_exactly"] is True


@pytest.mark.parametrize("speed", [-1e-20, 0, 1e-20])
def test_combustion_uses_reported_rate_without_native_substitution_or_zero_clamp(
    speed,
) -> None:
    state = physical_state("Mercury", 13, 0, 0, speed, native_speed=-speed)
    assert state["longitude_speed_native_degrees_per_day"] == -speed
    assert state["longitude_speed_degrees_per_day"] == speed
    expected = "retrograde" if speed < 0 else "direct" if speed > 0 else "stationary"
    assert state["motion"] == expected
    assert state["combustion"]["angular_criterion_met"] == (
        False if speed < 0 else True if speed > 0 else None
    )
