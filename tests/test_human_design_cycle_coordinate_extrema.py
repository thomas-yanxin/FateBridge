"""Biased native-speed controls, zero components and retained live evidence."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import pytest

from fatebridge.core import human_design_cycles as cycles
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]


def biased_speed_oracle(t):
    x = Fraction(t) - 1000
    if x < 8:
        phase, speed = Fraction(719, 2) * x / 8, Fraction(719, 16)
    else:
        # Coordinate maximum at10.25; supplied velocity zero at10.0.
        phase = 360 + Fraction(1, 100) - (x - Fraction(41, 4)) ** 2
        speed = -2 * (x - 10)
    return [t, float((17 + phase) % 360), float(speed), 258]


def test_coordinate_probe_recovers_both_roots_without_treating_speed_as_derivative(
    monkeypatch,
):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 12)
    result = cycles.derive_body_contacts("Saturn", 1000.0, biased_speed_oracle)
    assert result["status"] == "sampled_search_completed"
    assert len(result["contacts"]) == 2
    for event, expected in zip(result["contacts"], [1010.15, 1010.35], strict=True):
        assert abs(event["jd_tt"] - expected) * 86400 <= cycles.ROOT_SECONDS
        assert event["bracket_width_seconds"] <= cycles.ROOT_SECONDS
        assert abs(event["residual_degrees"]) <= cycles.RESIDUAL_DEGREES
    first, second = result["contacts"]
    assert first["motion"] == second["motion"] == "retrograde"
    assert first["motion_evidence"]["search_segment_phase_trend"] == "increasing"
    assert first["motion_evidence"]["native_speed_agrees_with_segment_trend"] is False
    assert second["motion_evidence"]["search_segment_phase_trend"] == "decreasing"
    assert second["motion_evidence"]["native_speed_agrees_with_segment_trend"] is True
    probe = result["station_witnesses"][0]["coordinate_probe"]
    assert probe["strictly_extends_speed_station_coordinates"] is True
    assert probe["continuous_extremum_certified"] is False


def test_observed_zero_component_is_not_counted_again_when_it_spans_coarse_intervals(
    monkeypatch,
):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 18)

    def read(t):
        x = Fraction(t) - 1000
        phase = 40 * x if x < 9 else Fraction(360) if x <= 15 else 360 + 20 * (x - 15)
        speed = 40 if x < 9 else 0 if x <= 15 else 20
        return [t, float((17 + phase) % 360), speed, 258]

    result = cycles.derive_body_contacts("Saturn", 1000.0, read)
    assert len(result["contacts"]) == 1
    assert result["contacts"][0]["exact_residual"]["numerator"] == "0"
    assert "不认证连续根数量" in result["numerical_scope"]


def test_velocity_zero_at_search_boundary_still_probes_the_observed_interval(
    monkeypatch,
):
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 12)

    def read(t):
        row = biased_speed_oracle(t)
        if t >= 1008:
            row[2] = float(-2 * (Fraction(t) - 1012))
        return row

    result = cycles.derive_body_contacts("Saturn", 1000.0, read)
    assert len(result["contacts"]) == 2
    assert result["station_witnesses"][0]["jd_tt"] == 1012.0
    assert all(event["jd_tt"] <= 1012 for event in result["contacts"])
    for event, expected in zip(result["contacts"], [1010.15, 1010.35], strict=True):
        assert abs(event["jd_tt"] - expected) * 86400 <= cycles.ROOT_SECONDS


@pytest.fixture(scope="module")
def after():
    from tests.human_design_current import complete_run

    inputs = json.loads(
        (Path(__file__).parent / "data/human_design/regression-inputs.json").read_text()
    )
    return complete_run(**inputs["cycle_coordinate_extrema"])


def test_actual_coordinate_probes_keep_the_two_nearby_chiron_contacts(after):
    row = next(r for r in after["cycle_context"]["bodies"] if r["body"] == "Chiron")
    assert len(row["contacts"]) == 5
    assert len([c for c in row["contacts"] if abs(c["jd_tt"] - 2419723.795) < 1]) == 2
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier invoked a native producer"),
    ):
        assert (
            verify_human_design_reading(after)["status"]
            == "verified_fixed_template_reading"
        )
    assert after["cycle_context"]["continuous_completeness_certified"] is False
    assert after["cycle_context"]["timing_accuracy_certified"] is False


@pytest.mark.parametrize(
    "fault",
    [
        "missing_probe",
        "selected_coordinate",
        "probe_count",
        "certified_extremum",
        "motion_trend",
        "native_agreement",
        "motion_basis",
        "summary_direction",
        "removed_contact",
        "missing_motion_evidence",
    ],
)
def test_rehashed_packet_cannot_forge_extremum_or_direction_evidence(after, fault):
    value = deepcopy(after)
    row = next(r for r in value["cycle_context"]["bodies"] if r["body"] == "Chiron")
    station = min(row["station_witnesses"], key=lambda r: abs(r["jd_tt"] - 2419723.795))
    event = next(
        c
        for c in row["contacts"]
        if not c["motion_evidence"]["native_speed_agrees_with_segment_trend"]
    )
    if fault == "missing_probe":
        station.pop("coordinate_probe")
    elif fault == "selected_coordinate":
        station["coordinate_probe"]["selected_sample"][1] += 0.01
    elif fault == "probe_count":
        station["coordinate_probe"]["observed_sample_count"] += 1
    elif fault == "certified_extremum":
        station["coordinate_probe"]["continuous_extremum_certified"] = True
    elif fault == "motion_trend":
        event["motion_evidence"]["search_segment_phase_trend"] = "decreasing"
    elif fault == "native_agreement":
        event["motion_evidence"]["native_speed_agrees_with_segment_trend"] = True
    elif fault == "motion_basis":
        event["motion_evidence"]["motion_basis"] = "certified_coordinate_derivative"
    elif fault == "summary_direction":
        summary = next(
            r for r in value["cycle_summary"]["bodies"] if r["body"] == "Chiron"
        )
        selected = next(c for c in summary["contacts"] if c["jd_tt"] == event["jd_tt"])
        assert selected["segment_phase_trend"] == "increasing"
        selected["segment_phase_trend"] = "decreasing"
    elif fault == "missing_motion_evidence":
        event.pop("motion_evidence")
        summary = next(
            r for r in value["cycle_summary"]["bodies"] if r["body"] == "Chiron"
        )
        next(c for c in summary["contacts"] if c["jd_tt"] == event["jd_tt"])[
            "motion_evidence"
        ] = None
    else:
        row["contacts"].remove(event)
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier invoked a native producer"),
    ):
        assert verify_human_design_reading(value)["status"] == "rejected"
