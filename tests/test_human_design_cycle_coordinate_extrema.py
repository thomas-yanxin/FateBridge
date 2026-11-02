"""Biased native-speed controls, zero components and retained live evidence."""

import gzip
import hashlib
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
EVIDENCE = ROOT / "docs/validation/human-design-cycle-solar-stations-v1/evidence"


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
    path = EVIDENCE / "public-after-final-output.json.gz"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "417a27d4c07824474238072f7be25ab6f5294e49065b8221d66d637119c3c91a"
    )
    with gzip.open(path, "rt") as handle:
        return json.load(handle)


def test_public_before_is_retained_and_after_replays_without_native_calls(after):
    before_path = EVIDENCE / "public-before-output.json.gz"
    assert (
        hashlib.sha256(before_path.read_bytes()).hexdigest()
        == "2e47b0adcaa86e0bd1364ab22e5534e16e067f72a872e7c080e08049ef8118e2"
    )
    with gzip.open(before_path, "rt") as handle:
        before = json.load(handle)
    old = next(
        row for row in before["cycle_context"]["bodies"] if row["body"] == "Chiron"
    )
    new = next(
        row for row in after["cycle_context"]["bodies"] if row["body"] == "Chiron"
    )
    assert len(old["contacts"]) == 3
    assert len(new["contacts"]) == 5
    assert not [c for c in old["contacts"] if abs(c["jd_tt"] - 2419723.795) < 1]
    assert len([c for c in new["contacts"] if abs(c["jd_tt"] - 2419723.795) < 1]) == 2
    with patch(
        "fatebridge.core.astro.runtime.ephemeris_call",
        side_effect=AssertionError("Verifier invoked a native producer"),
    ):
        assert (
            verify_human_design_reading(after)["status"]
            == "verified_fixed_template_reading"
        )
        assert verify_human_design_reading(before)["status"] == "rejected"
    assert after["cycle_context"]["continuous_completeness_certified"] is False
    assert after["cycle_context"]["timing_accuracy_certified"] is False


def test_intermediate_receipt_is_preserved_and_does_not_claim_current_probe_policy():
    path = EVIDENCE / "public-after-first-output.json.gz"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "f148a878d3e660a22f396a7b1386e88a8dcfad324a800c35a66edacec6854d7b"
    )
    with gzip.open(path, "rt") as handle:
        intermediate = json.load(handle)
    assert verify_human_design_reading(intermediate)["status"] == "rejected"


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
        summary["contacts"][-1]["motion_evidence"][
            "search_segment_phase_trend"
        ] = "decreasing"
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


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "old_coordinate",
        "old_root",
        "missing_old_row",
        "source_index",
        "unknown_field",
    ],
)
def test_original_prefix_comparison_cannot_hide_changed_old_values(after, fault):
    from scripts.check_human_design_cycle_prefix import original_body_projection

    with gzip.open(EVIDENCE / "public-before-output.json.gz", "rt") as handle:
        before = json.load(handle)
    original = before["cycle_context"]["bodies"][0]
    current = deepcopy(after["cycle_context"]["bodies"][0])
    old_time = original["evaluation_witnesses"][0][0]
    row_index = next(
        i for i, row in enumerate(current["evaluation_witnesses"]) if row[0] == old_time
    )
    if fault == "old_coordinate":
        current["evaluation_witnesses"][row_index][1] += 1e-10
    elif fault == "old_root":
        current["contacts"][0]["longitude"] += 1e-10
    elif fault == "missing_old_row":
        current["evaluation_witnesses"].pop(row_index)
        current["evaluation_source_context_indices"].pop(row_index)
    elif fault == "source_index":
        current["evaluation_source_context_indices"][row_index] += 1
    elif fault == "unknown_field":
        current["unreviewed_addition"] = True
    if fault is None:
        assert original_body_projection(current, original) == original
    else:
        with pytest.raises(ValueError):
            original_body_projection(current, original)


def test_cycle_extension_keeps_original_natal_mechanics_values_and_version(after):
    from fatebridge.core.human_design import RULESET_VERSION

    with gzip.open(EVIDENCE / "public-before-output.json.gz", "rt") as handle:
        before = json.load(handle)
    assert RULESET_VERSION == "1.39.0"
    assert after["source_summary"]["version"] == before["source_summary"]["version"]
    assert after["cycle_context"]["ruleset"]["version"] == "1.6.0"
    for key in (
        "activations",
        "bodygraph",
        "variables",
        "design_solver",
        "time_scales",
        "profile",
    ):
        assert after[key] == before[key]


def test_relabelled_old_cycle_receipt_still_lacks_required_coordinate_witnesses():
    with gzip.open(EVIDENCE / "public-before-output.json.gz", "rt") as handle:
        value = json.load(handle)
    value["cycle_context"]["ruleset"] = cycles.cycle_ruleset()
    value["cycle_summary"] = cycles.cycle_summary(
        value["cycle_context"], value["profile"]
    )
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    proof = verify_human_design_reading(value)
    assert proof["status"] == "rejected"
    assert {"code": "incomplete_or_malformed_cycle_witnesses"} in proof["errors"]


def test_historical_derivation_is_exact_frozen_pre_coordinate_algorithm():
    import ast
    import inspect

    from fatebridge.core.human_design_cycle_history import (
        derive_pre_coordinate_body_contacts,
    )

    path = EVIDENCE.parent / "before-source/src/fatebridge/core/human_design_cycles.py"
    original = ast.parse(path.read_text())
    node = next(
        n
        for n in original.body
        if isinstance(n, ast.FunctionDef) and n.name == "derive_body_contacts"
    )
    restored = ast.parse(inspect.getsource(derive_pre_coordinate_body_contacts)).body[0]
    restored.name = node.name
    assert ast.dump(restored) == ast.dump(node)
