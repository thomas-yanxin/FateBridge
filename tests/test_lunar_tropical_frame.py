"""Independent matrix reference, model guards and source-faithful decomposition."""

import copy
import json
from fractions import Fraction as Q
from pathlib import Path

import pytest

from fatebridge.core.astro import lunar_tropical_frame as frame
from scripts.astrodice_clock_interval import I
from scripts.astrodice_display_frame import pi_interval

ROOT = Path(__file__).parents[1]
RUN = ROOT / "docs/validation/astrodice-display-rate-run-2026-10-28"


def native(index=0, backend="swieph"):
    data = json.loads(
        (RUN / f"native-development-candidate-first/{backend}-{index}.json").read_text()
    )
    return next(r for r in data["rows"] if r["body"] == "Moon")


def mv(matrix, vector):
    return [sum((a * b for a, b in zip(row, vector)), I()) for row in matrix]


def matrix(rows, kind):
    return [[I(*map(Q, x[kind])) for x in row] for row in rows]


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("backend", ["swieph", "jpl_record_window"])
def test_actual_source_state_with_analytic_frame_matches_independent_expanded_matrix(
    index, backend
):
    row = native(index, backend)
    metadata = row["metadata"]
    fixed = metadata["lunar_light_time"]["fixed_frame_source_derivative"]
    reference = json.loads((RUN / "development-reference-first.json").read_text())[
        "frames"
    ][index]
    mean = matrix(reference["mean"], "value")
    inverse = list(zip(*mean))
    true = matrix(reference["true"], "value")
    derivative = matrix(reference["true"], "derivative")
    p = mv(inverse, [I(Q(v)) for v in fixed["full_fixed_frame_apparent_position_au"]])
    v = mv(
        inverse,
        [
            I(Q(v))
            for v in fixed["full_fixed_frame_velocity_au_per_native_argument_day"]
        ],
    )
    q = mv(true, p)
    dq = [a + b for a, b in zip(mv(true, v), mv(derivative, p))]
    expected = (
        (q[0] * dq[1] - q[1] * dq[0])
        / (q[0].square() + q[1].square())
        * 648000
        / pi_interval()
    )
    coords = [row["state"]["longitude"], row["state"]["latitude"]]
    value, policy = frame.complete_lunar_tropical_rate(
        row["native_numeric_jd"],
        coords,
        row["model"],
        fixed,
        metadata["lunar_tropical_frame"][
            "legacy_display_rate_degrees_per_native_argument_day"
        ],
    )
    assert policy["status"] == "applied" and value is not None
    assert (I(Q(value) * 3600) - expected).absolute_upper() < Q("0.0000001")
    assert policy["physical_TT_equivalence_certified"] is False
    assert policy["native_binary_function_derivative_certified"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "not_applied"),
        ("fixed_frame_epoch_jd_tt", 2451545.0),
        ("fixed_frame_id", "other_basis"),
        ("ephemeris_model", "other_source"),
        ("center_native_states_reproduced_exactly", False),
        ("center_file_context_reproduced_exactly", False),
    ],
)
def test_unverified_source_state_is_never_upgraded(field, value):
    row = native()
    fixed = copy.deepcopy(
        row["metadata"]["lunar_light_time"]["fixed_frame_source_derivative"]
    )
    fixed[field] = value
    result, policy = frame.complete_lunar_tropical_rate(
        row["native_numeric_jd"], [0, 0], "swieph", fixed, 1
    )
    assert (
        result is None
        and policy["reason"] == "checked_fixed_reception_source_state_unavailable"
    )


@pytest.mark.parametrize(
    "epoch,reason",
    [
        (2451545.0, "isolated_native_J2000_precession_identity_shortcut"),
        (1721425.0, "outside_frame_model_domain"),
        (5373486.0, "outside_frame_model_domain"),
    ],
)
def test_no_unique_derivative_claim_at_native_shortcut_or_outside_domain(
    epoch, reason, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("An unavailable frame must not sample native states")

    monkeypatch.setattr(frame.runtime, "ephemeris_call", forbidden)
    result, policy = frame.complete_lunar_tropical_rate(
        epoch, [0, 0], "swieph", None, 1
    )
    assert result is None and policy["reason"] == reason


def test_unverified_binding_never_changes_the_delivered_rate(monkeypatch):
    monkeypatch.setattr(
        frame, "binding_distribution_version", lambda *args: "unavailable"
    )
    result, policy = frame.complete_lunar_tropical_rate(
        2451546, [0, 0], "swieph", None, 1
    )
    assert result is None and policy["reason"] == "unverified_native_version"


@pytest.mark.parametrize("kind", ["nutation_model", "display_position"])
def test_a_different_native_frame_is_not_silently_assumed(kind, monkeypatch):
    row = native()
    fixed = row["metadata"]["lunar_light_time"]["fixed_frame_source_derivative"]
    coords = [row["state"]["longitude"], row["state"]["latitude"]]
    values = list(row["native_ecl_nut_diagnostic"]["coordinates"])
    if kind == "nutation_model":
        values[2] += 0.00001
    else:
        coords[0] += 0.00001
    monkeypatch.setattr(
        frame.runtime, "ephemeris_call", lambda *args, **kwargs: (values, 2)
    )
    result, policy = frame.complete_lunar_tropical_rate(
        row["native_numeric_jd"], coords, "swieph", fixed, 1
    )
    assert result is None and policy["reason"] == "declared_native_frame_not_reproduced"
    assert policy["native_model_component_errors_arcsec"]


def test_same_domain_frame_formula_keeps_known_source_failure():
    data = json.loads((RUN / "development-candidate-audit-first.json").read_text())
    failed = [r for r in data["rows"] if not r["qualified"]]
    assert len(failed) == 1 and failed[0]["label"] == "3000-12-07T04:07:32"
    assert failed[0]["body"] == "Moon" and failed[0]["backend"] == "swieph"
    assert (
        failed[0]["signed_complete_display_rate_error_arcsec_per_source_day"]["lower"]
        > 0.002
    )
    baseline = json.loads((RUN / "development-baseline-audit-first.json").read_text())
    before = next(
        r
        for r in baseline["rows"]
        if r["body"] == "Moon" and r["case_index"] == 0 and r["backend"] == "swieph"
    )
    after = next(
        r
        for r in data["rows"]
        if r["body"] == "Moon" and r["case_index"] == 0 and r["backend"] == "swieph"
    )
    # Removing a frame error can remove an accidental cancellation. Keep the
    # worsened total residual; never filter it out of the population.
    assert abs(
        after["signed_complete_display_rate_error_arcsec_per_source_day"]["lower"]
    ) > abs(before["signed_complete_display_rate_error_arcsec_per_source_day"]["lower"])
