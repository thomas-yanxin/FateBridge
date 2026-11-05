"""Current producer input binding never replaces the original frame reference."""

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

from fatebridge.core.astro import continuous_lahiri as frame

ROOT = Path(__file__).resolve().parents[2]
BINDING_PATH = ROOT / "tests/fixtures/jyotish-continuous-input-binding-v2.json"
BINDING = json.loads(BINDING_PATH.read_text())
OLD_PATH = ROOT / "tests/fixtures/jyotish-continuous-state-reference-v1.json"
OLD = json.loads(OLD_PATH.read_text())


def test_independent_source_and_math_provenance_preserves_original_fixture():
    assert hashlib.sha256(BINDING_PATH.read_bytes()).hexdigest() == (
        "8fcc67370a57d59d643db624a1f4a76ad49db8bc706d2aa0bdd9f8ade309a3dd"
    )
    assert (
        hashlib.sha256(OLD_PATH.read_bytes()).hexdigest()
        == ("795db1c5613325aa39e3cec48d5b44b9d47fffcc05599bc98bc7e8702d67194d")
        == BINDING["original_reference_sha256"]
    )
    assert BINDING["binding_id"] == "continuous_native_input_binding_v2"
    assert BINDING["coefficient_sha256"] == frame.COEFFICIENT_SHA256
    assert BINDING["candidate_or_production_imported_by_math_reference"] is False
    assert BINDING["raw_reference_imported_FateBridge"] is False
    assert BINDING["reference_precision_digits"] == [80, 120]
    assert BINDING["precision_crosscheck_failures"] == 0
    assert len(BINDING["native_inputs"]) == 518
    assert len({r["native_case_index"] for r in BINDING["native_inputs"]}) == 518
    assert len(BINDING["rows"]) == 2590
    assert BINDING["new_physical_qualifications"] == 0
    assert BINDING["whole_goal_complete"] is False


def test_all2590_bound_frame_projections_keep_original_numeric_lines():
    assert BINDING["frame_position_line_arcsec"] == 1e-7
    assert BINDING["frame_rate_line_arcsec_per_day"] == 1e-6
    assert BINDING["cartesian_state_line"] == 1e-12
    failures = []
    no_frame_rejected = 0
    for row in BINDING["rows"]:
        result = frame.project_state(
            row["epoch_jd_tt"],
            row["inertial_position"],
            row["inertial_velocity"],
            vector_rate_scale=float(Fraction(row["vector_rate_scale_rational"])),
        )
        expected = row["expected"]
        a, b = result["spherical"], expected["spherical"]
        position_error = (
            max(
                abs(
                    math.remainder(a["longitude_degrees"] - b["longitude_degrees"], 360)
                ),
                abs(a["latitude_degrees"] - b["latitude_degrees"]),
            )
            * 3600
        )
        rate_error = (
            max(
                abs(a[key] - b[key])
                for key in [
                    "longitude_rate_degrees_per_day",
                    "latitude_rate_degrees_per_day",
                ]
            )
            * 3600
        )
        if position_error > 1e-7 or rate_error > 1e-6:
            failures.append(
                (
                    row["native_case_index"],
                    row["vector_rate_scale_rational"],
                    position_error,
                    rate_error,
                )
            )
        for key in ["position", "velocity_per_TT_day"]:
            assert max(abs(x - y) for x, y in zip(result[key], expected[key])) <= 1e-12
        for key in ["radius", "radial_rate_per_day"]:
            assert abs(a[key] - b[key]) <= 1e-12
        no_frame = frame.spherical_state(
            expected["position"],
            [
                v - spin
                for v, spin in zip(
                    expected["velocity_per_TT_day"], expected["frame_motion_per_TT_day"]
                )
            ],
        )
        no_frame_rejected += (
            max(
                abs(no_frame[key] - b[key])
                for key in [
                    "longitude_rate_degrees_per_day",
                    "latitude_rate_degrees_per_day",
                ]
            )
            * 3600
            > 1e-6
        )
    assert not failures, failures
    assert no_frame_rejected == 2590


def test_old49_compatibility_failures_and_seven_position_failures_are_retained():
    old = {
        r["native_case_index"]: r
        for r in OLD["rows"]
        if r["mode"] == "apparent" and r["vector_rate_scale_rational"] == "1"
    }
    failures = []
    current = [r for r in BINDING["rows"] if r["vector_rate_scale_rational"] == "1"]
    assert len(old) == len(current) == 518
    for row in current:
        expected_old = old[row["native_case_index"]]["expected"]["spherical"]
        if (
            max(
                abs(row["expected"]["spherical"][key] - expected_old[key])
                for key in [
                    "longitude_rate_degrees_per_day",
                    "latitude_rate_degrees_per_day",
                ]
            )
            * 3600
            > 1e-6
        ):
            failures.append([row["native_case_index"], row["epoch_jd_tt"], row["body"]])
    legacy = BINDING["legacy_original_rate_gate"]
    assert legacy["passed"] is False and legacy["status"] == "failed_retained"
    assert len(failures) == 49 and failures == legacy["failed_case_ids"]
    assert len(BINDING["original_apparent_position_failures"]) == 7
    assert all(
        r[1] == 2451545.0 for r in BINDING["original_apparent_position_failures"]
    )
    assert BINDING["original_native_position_failures_all_modes"] == 14
