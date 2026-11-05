"""Frozen source differentiation, held-basis decoding and actual managed inputs."""

import copy
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import continuous_lahiri as frame
from fatebridge.core.astro import jyotish_continuous_state as continuous
from fatebridge.core.astro import jyotish_lunar_source_state as source_state
from fatebridge.core.astro import lunar_motion, lunar_observer, runtime
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.compressed_ephemeris import audit_compressed_endpoints
from fatebridge.core.jyotish import positions
from fatebridge.utils.errors import EphemerisSourceError
from tests.jyotish.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.jyotish.test_jyotish_sources import birth

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = ROOT / "tests/fixtures/jyotish-lunar-source-state-reference-v1.json"
REFERENCE = json.loads(REFERENCE_PATH.read_text())


def policy_pair(row):
    source = copy.deepcopy(row["source_policy"])
    source.update(
        fixed_frame_id=lunar_observer.FIXED_FRAME_ID,
        fixed_frame_epoch_jd_tt=row["epoch_jd_tt"],
        input_frame_held_fixed=True,
        input_velocity_time_variable="native_numeric_argument_day",
        full_fixed_frame_apparent_position_au=list(
            row["expected"]["full_fixed_position"]
        ),
        full_fixed_frame_velocity_au_per_native_argument_day=list(
            row["expected"]["full_fixed_velocity"]
        ),
    )
    original = dict(
        status="partial",
        model_id=frame.METHOD_ID,
        coefficient_sha256=frame.COEFFICIENT_SHA256,
        native_version="2.10.03",
        binding_version="2.10.3.2",
        epoch_jd_tt=row["epoch_jd_tt"],
        ephemeris_model=source["ephemeris_model"],
        native_center_reproduced_exactly=True,
        source_context_reproduced_exactly=True,
        source_context={"scope": "numeric capture comparison only"},
        native_J2000_state=row["native_J2000_state"],
    )
    return original, source


def test_frozen_reference_identity_and_all770_source_projections(record_property):
    assert hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest() == (
        "936847905192123e398711b63a6edf54811a7d21cd669f502a06084084fa6e78"
    )
    assert REFERENCE["summary"]["case_identities"] == 154
    assert REFERENCE["summary"]["unique_numeric_epochs"] == 138
    assert REFERENCE["summary"]["projection_cases"] == 770
    assert REFERENCE["summary"]["precision_crosscheck_failures"] == 0
    assert (
        REFERENCE["summary"]["original_native_J2000_position_failures_retained"] == 14
    )
    assert REFERENCE["summary"]["new_physical_reference_passes"] == 0
    assert not REFERENCE["candidate_or_production_imported"]
    maximum = dict(position=0.0, velocity=0.0, angular_rate_arcsec_per_day=0.0)
    failures = []
    for row in REFERENCE["rows"]:
        inputs = row["inputs"]
        _, details = lunar_observer.fixed_frame_source_remainder(
            *[
                inputs[k]
                for k in [
                    "preaberration",
                    "native_fixed_apparent",
                    "observer_velocity",
                    "observer_beta",
                    "observer_beta_derivative",
                    "light_time_derivative",
                    "prior_light_correction",
                    "prior_spatial_correction",
                ]
            ]
        )
        p = details["full_fixed_frame_apparent_position_au"]
        v = details["full_fixed_frame_velocity_au_per_native_argument_day"]
        assert math.dist(p, row["expected"]["full_fixed_position"]) <= 1e-12
        assert math.dist(v, row["expected"]["full_fixed_velocity"]) <= 1e-12
        decoded = frame.decode_native_fixed_reception_state(row["epoch_jd_tt"], p, v)
        for scale, expected in zip(
            row["clock_factors_rational"], row["expected"]["projections"]
        ):
            actual = frame.project_state(
                row["epoch_jd_tt"],
                decoded["position"],
                decoded["velocity_per_native_argument_day"],
                vector_rate_scale=float(Fraction(scale)),
            )
            errors = {
                "position": max(
                    abs(a - b) for a, b in zip(actual["position"], expected["position"])
                ),
                "velocity": max(
                    abs(a - b)
                    for a, b in zip(
                        actual["velocity_per_TT_day"], expected["velocity_per_TT_day"]
                    )
                ),
                "angular_rate_arcsec_per_day": max(
                    abs(actual["spherical"][k] - expected["spherical"][k]) * 3600
                    for k in [
                        "longitude_rate_degrees_per_day",
                        "latitude_rate_degrees_per_day",
                    ]
                ),
            }
            for k, error in errors.items():
                maximum[k] = max(maximum[k], error)
                line = 1e-6 if k == "angular_rate_arcsec_per_day" else 1e-12
                if error > line:
                    failures.append((row["case_id"], scale, k, error))
            assert (
                abs(actual["spherical"]["radius"] - expected["spherical"]["radius"])
                <= 1e-12
            )
            assert (
                abs(
                    actual["spherical"]["radial_rate_per_day"]
                    - expected["spherical"]["radial_rate_per_day"]
                )
                <= 1e-12
            )
        original, source = policy_pair(row)
        result = source_state.source_derivative_state_evidence(
            row["epoch_jd_tt"], original, {**source, **details}
        )
        assert result["status"] == "partial"
        assert result["primary_D1_factors_changed"] is False
        assert result["complete_apparent_rate_certified"] is False
        assert result["physical_TT_clock_mapping_certified"] is False
    record_property("all770_projection_max_errors", json.dumps(maximum))
    assert not failures, failures


def test_all154_actual_managed_source_inputs_and_no_new_native_projection_queries(
    monkeypatch,
):
    e.configure_ephemeris_path(str(ROOT / "ephe"))
    swe = runtime.swe
    for row in REFERENCE["rows"]:
        tt = row["epoch_jd_tt"]
        swe.set_ephe_path(str(ROOT / "ephe"))
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        with audit_compressed_endpoints():
            trace = PhysicalEphemerisTrace()
            native, flags = runtime.ephemeris_call(
                "calc", tt, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
            )
            original = continuous.continuous_state_evidence(
                "Moon", tt, native, flags, "swieph", source_trace=trace
            )
            _, policy = lunar_motion.lunar_light_time_correction(
                tt, native, "swieph", source_trace=trace
            )
            trace.finish()

        def forbidden(*args, **kwargs):
            raise AssertionError("Pure projection must not query native")

        with monkeypatch.context() as patch:
            patch.setattr(runtime, "ephemeris_call", forbidden)
            result = source_state.source_derivative_state_evidence(
                tt, original, policy["fixed_frame_source_derivative"]
            )
        assert result["status"] == "partial"
        for key in ["longitude_rate_degrees_per_day", "latitude_rate_degrees_per_day"]:
            assert (
                abs(
                    result["state"]["spherical"][key]
                    - row["expected"]["projections"][0]["spherical"][key]
                )
                * 3600
                <= 1e-6
            )


def test_mutation_detection_preserves_cases_below_the_frozen_line(record_property):
    actual_counts = dict(
        omit_observer=0,
        uniform_small=0,
        uniform_stress=0,
        input_basis=0,
        smooth_J2000=0,
    )
    expected_counts = dict(actual_counts)
    for row in REFERENCE["rows"]:
        tt = row["epoch_jd_tt"]
        inputs = row["inputs"]
        p, v = (
            row["expected"]["full_fixed_position"],
            row["expected"]["full_fixed_velocity"],
        )
        decoded = frame.decode_native_fixed_reception_state(tt, p, v)
        pre_d = [
            vr - (vr + ve) * inputs["light_time_derivative"]
            for vr, ve in zip(inputs["preaberration"][3:], inputs["observer_velocity"])
        ]
        _, no_observer_v = lunar_motion.aberration_position_jvp(
            inputs["preaberration"][:3], pre_d, inputs["observer_beta"]
        )
        no_observer = frame.decode_native_fixed_reception_state(tt, p, no_observer_v)
        basis = frame.frame_state(tt)
        basis_term = frame.mv(
            frame.transpose(basis["mean_frame_derivative_per_TT_day"]), p
        )
        bad_v = frame.add(decoded["velocity_per_native_argument_day"], basis_term)
        unit = frame.project_state(
            tt,
            decoded["position"],
            decoded["velocity_per_native_argument_day"],
            vector_rate_scale=1.0,
        )
        for scale, expected, mutants in zip(
            row["clock_factors_rational"],
            row["expected"]["projections"],
            row["expected"]["mutants"],
        ):
            gamma = float(Fraction(scale))
            correct = expected["velocity_per_TT_day"]
            omitted = frame.project_state(
                tt,
                no_observer["position"],
                no_observer["velocity_per_native_argument_day"],
                vector_rate_scale=gamma,
            )["velocity_per_TT_day"]
            uniform = [gamma * x for x in unit["velocity_per_TT_day"]]
            differentiated = frame.project_state(
                tt, decoded["position"], bad_v, vector_rate_scale=gamma
            )["velocity_per_TT_day"]
            error = lambda a: max(abs(x - y) for x, y in zip(a, correct))
            actual_counts["omit_observer"] += error(omitted) > 1e-12
            actual_counts["input_basis"] += error(differentiated) > 1e-12
            expected_counts["omit_observer"] += (
                mutants["omit_observer_velocity_error"] > 1e-12
            )
            expected_counts["input_basis"] += (
                mutants["differentiate_input_basis_velocity_error"] > 1e-12
            )
            if scale != "1":
                key = "uniform_stress" if scale in {"2", "1/2"} else "uniform_small"
                actual_counts[key] += error(uniform) > 1e-12
                expected_counts[key] += mutants["uniform_clock_velocity_error"] > 1e-12
        if tt == 2451545.0:
            smooth = frame.mv(frame.transpose(basis["mean_frame"]), p)
            decoded_p = decoded["position"]
            angle = (
                math.degrees(
                    math.atan2(
                        math.hypot(*frame.cross(decoded_p, smooth)),
                        frame.dot(decoded_p, smooth),
                    )
                )
                * 3600
            )
            actual_counts["smooth_J2000"] += angle > 1e-7
            expected_counts["smooth_J2000"] += (
                row["expected"]["smooth_decoder_position_error_arcsec"] > 1e-7
            )
    record_property("mutation_rejections_at_unchanged_lines", json.dumps(actual_counts))
    assert actual_counts == expected_counts
    assert actual_counts == dict(
        omit_observer=770,
        uniform_small=0,
        uniform_stress=288,
        input_basis=770,
        smooth_J2000=1,
    )


@pytest.mark.parametrize(
    "fault",
    [
        "epoch",
        "frame_epoch",
        "frame_id",
        "velocity_unit",
        "moving_input_frame",
        "version",
        "model",
        "restore",
        "shape",
        "nan",
        "position",
        "source_position_line",
        "missing_context",
    ],
)
def test_applied_corruption_fails_closed_without_touching_native(monkeypatch, fault):
    row = REFERENCE["rows"][0]
    original, source = policy_pair(row)
    if fault == "epoch":
        source["epoch_jd_tt"] += 1
    elif fault == "frame_epoch":
        source["fixed_frame_epoch_jd_tt"] += 1
    elif fault == "frame_id":
        source["fixed_frame_id"] = "different"
    elif fault == "velocity_unit":
        source["input_velocity_time_variable"] = "physical_TT"
    elif fault == "moving_input_frame":
        source["input_frame_held_fixed"] = False
    elif fault == "version":
        original["native_version"] = "unverified"
    elif fault == "model":
        source["ephemeris_model"] = "jpl"
    elif fault == "restore":
        source["center_native_states_reproduced_exactly"] = False
    elif fault == "shape":
        source["full_fixed_frame_velocity_au_per_native_argument_day"] = [0, 0]
    elif fault == "nan":
        source["full_fixed_frame_velocity_au_per_native_argument_day"][0] = math.nan
    elif fault == "position":
        source["full_fixed_frame_apparent_position_au"][0] += 0.001
    elif fault == "source_position_line":
        source["source_position_reproduction_arcsec"] = 1e-6
    elif fault == "missing_context":
        del original["source_context"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Pure evidence projection must not call native")

    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    with pytest.raises(EphemerisSourceError):
        source_state.source_derivative_state_evidence(
            row["epoch_jd_tt"], original, source
        )


@pytest.mark.parametrize(
    "reason",
    [
        "observer_acceleration_not_converged",
        "unsupported_physical_model",
        "no_exact_source_window_stencil",
    ],
)
def test_unavailable_source_has_no_fabricated_state(reason):
    row = REFERENCE["rows"][0]
    original, _ = policy_pair(row)
    result = source_state.source_derivative_state_evidence(
        row["epoch_jd_tt"], original, {"status": "not_applied", "reason": reason}
    )
    assert result["status"] == "not_applied" and result["input_reason"] == reason
    assert "state" not in result and "decoded_J2000_source_state" not in result


def test_actual_moshier_preserves_outer_inapplicability_reason(tmp_path):
    e.configure_ephemeris_path(str(tmp_path))
    result = positions(birth(), ephemeris_policy="auto")
    context = result["physical_states"]["Moon"]["longitude_motion_context"]
    outer = context["lunar_light_time"]
    source = context["continuous_frame_state"]["source_derivative_state"]
    assert outer["status"] == "not_applied"
    assert outer["reason"] == "unsupported_physical_model"
    assert source["status"] == "not_applied"
    assert source["input_status"] == outer["status"]
    assert source["input_reason"] == outer["reason"]
    assert "state" not in source
