"""Reference selection cannot see candidate residuals or discard bad supports."""

import math
from fractions import Fraction

import pytest

from scripts.astrodice_reference_refinement import (
    ORDERS,
    STEPS,
    estimate,
    quality,
    weights,
)


def synthetic():
    nodes = sorted({k * h for h in STEPS for k in range(-6, 7)})
    row = {
        "samples": {
            str(o): {"printed_angles": ["0.000000000000", "0.000000000000"]}
            for o in nodes
        }
    }
    points = {
        str(o): [math.cos(o / 8640000), math.sin(o / 8640000), 0.0] for o in nodes
    }
    return row, points


@pytest.mark.parametrize("order", ORDERS)
def test_independent_weights_exact_for_every_polynomial_moment(order):
    w = weights(order)
    for power in range(order + 1):
        assert sum(v * Fraction(k) ** power for k, v in w.items()) == int(power == 1)


def test_smooth_function_selects_coarsest_middle_and_keeps_all_checks():
    row, points = synthetic()
    result = quality(row, points)
    assert result["selected_step_seconds"] == 5400
    assert len(result["all_estimates"]) == 15
    assert len(result["all_triplet_checks"]) == 3
    assert result["candidate_output_used_for_selection"] is False
    assert estimate(points, 5400, 12)[1] == pytest.approx(0.01, abs=1e-14)


def test_coarse_discontinuity_forces_refinement_without_removing_failed_checks():
    row, points = synthetic()
    # Three supports intersect an artificial distant jump; the finest triplet
    # remains local. It is selected by reference values alone.
    for o, p in points.items():
        if int(o) >= 27000:
            p[1] += 0.001
    result = quality(row, points)
    assert result["selected_step_seconds"] == 1350
    assert result["all_triplet_checks"][0]["qualified"] is False
    assert result["all_triplet_checks"][1]["qualified"] is False
    assert result["all_triplet_checks"][2]["qualified"] is True


def test_projected_quality_must_use_preselected_icrf_support():
    row, points = synthetic()
    assert quality(row, points, selected_step=1350)["selected_step_seconds"] == 1350
    assert (
        quality(row, points, selected_step=123)["status"]
        == "reference_quality_unresolved"
    )


def test_insufficient_printing_precision_is_not_converted_to_success():
    row, points = synthetic()
    for p in row["samples"].values():
        p["printed_angles"] = ["0.0", "0.0"]
    result = quality(row, points)
    assert result["status"] == "reference_quality_unresolved"
    assert result["selected_step_seconds"] is None


def test_one_missing_planned_probe_keeps_case_unavailable():
    row, points = synthetic()
    row["samples"]["64800"] = None
    result = quality(row, points)
    assert result == {"status": "reference_unavailable", "missing_offsets": ["64800"]}


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_directions_fail_before_selection(bad):
    row, points = synthetic()
    points["0"][0] = bad
    with pytest.raises(ValueError, match="Invalid refinement directions"):
        quality(row, points)


def test_unplanned_removed_node_is_rejected():
    row, points = synthetic()
    row["samples"].pop("64800")
    with pytest.raises(ValueError, match="node plan changed"):
        quality(row, points)
