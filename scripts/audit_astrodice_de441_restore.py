"""Compare restored DE441 and compressed Moon outputs on a frozen TT cohort.

The reference uses independent Horizons directions. Display orientation is
shared with the native engine and is not independently physically certified.
Full observed 6/12-hour disagreement is included in the conditional radius;
it is an empirical check, not a rigorous truncation or clock-error bound.
"""

import argparse
import hashlib
import json
import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from scripts.astrodice_interval_reference import tangent_geometry
from scripts.audit_astrodice_horizons_wide_reference import (
    interpolation_weights,
    validate,
)
from scripts.audit_astrodice_local_motion import (
    AS_PER_RADIAN,
    FAIL,
    PASS,
    RATE_LINE,
    UNRESOLVED,
    display_reference,
    evaluate_layers,
    orientation_derivative,
    position_comparison,
)
from scripts.audit_astrodice_v6_wide import dot

METHOD = "raw_de441_lunar_frozen_display_comparison_v1"
LUNAR_METHOD = "fatebridge_lunar_fixed_frame_source_derivative_v3"
OBSERVER_METHOD = "lunar_fixed_frame_source_derivative_with_observer_acceleration_v1"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def check_inputs(root, seal, protocol, reference):
    if digest(protocol) != seal["protocol_sha256"]:
        raise ValueError("Frozen protocol changed")
    if digest(reference) != seal["reference_sha256"]:
        raise ValueError("Frozen reference changed")
    for name, expected in seal["candidate_files"].items():
        if digest(root / name) != expected:
            raise ValueError("Frozen candidate/helper source changed: " + name)
    for filename, expected in seal["physical_inputs"].items():
        if digest(Path(filename)) != expected:
            raise ValueError("Frozen physical input changed: " + filename)


def reference_axes(row, protocol):
    """Replay the declared vector derivative and propagate its noise to axes."""
    h = protocol["selected_step_seconds"][row["body"]]
    if h != 43200 or protocol["steps_seconds"][row["body"]] != [21600, 43200]:
        raise ValueError("Unplanned reference step selection")
    weights = interpolation_weights()
    velocity = row["derivatives_per_tt_day"][str(h)]
    printing = 0.0
    for k in range(1, 7):
        noise = 0.0
        for sign in [-1, 1]:
            sample = row["samples"][str(sign * k * h)]
            digits = sum(
                float(Decimal(10) ** Decimal(v).as_tuple().exponent)
                for v in sample["printed_angles"]
            )
            # Full LSB for each printed angle, plus arithmetic allowance.
            noise += math.radians(digits) + 8e-15
        printing += abs(float(weights[k])) * noise * 86400 / h
    printing *= AS_PER_RADIAN
    spread = row["step_difference_arcsec_per_day"]
    _, pa, pd, center_noise = tangent_geometry(row)
    alpha_scale2 = dot(pa, pa)
    if alpha_scale2 < 0.0001:
        raise ValueError("Ill-conditioned reference tangent geometry")
    mids = [
        dot(velocity, pa) * AS_PER_RADIAN / alpha_scale2,
        dot(velocity, pd) * AS_PER_RADIAN,
    ]
    vector_radius = math.nextafter(
        printing + spread + center_noise * math.hypot(*velocity) * AS_PER_RADIAN,
        math.inf,
    )
    radii = [vector_radius / math.sqrt(alpha_scale2), vector_radius]
    axes = [(Fraction(v - r), Fraction(v + r)) for v, r in zip(mids, radii)]
    return axes, {
        "selected_step_seconds": h,
        "printing_and_arithmetic_vector_radius_arcsec_per_day": printing,
        "full_observed_step_difference_arcsec_per_day": spread,
        "vector_radius_arcsec_per_day": vector_radius,
        "physical_truncation_bound_certified": False,
        "physical_epoch_error_bound_certified": False,
    }


def grade_frames(frames):
    if any(
        v["conditional_error_lower_arcsec_per_day"] > RATE_LINE for v in frames.values()
    ):
        return FAIL
    if any(
        not v["reference"]["frame_check_qualified"]
        or v["conditional_error_upper_arcsec_per_day"] > RATE_LINE
        for v in frames.values()
    ):
        return UNRESOLVED
    return PASS


def require_lunar_policy(metadata):
    policy = metadata["lunar_light_time"]
    fixed = policy["fixed_frame_source_derivative"]
    if (
        policy["method_id"] != LUNAR_METHOD
        or policy["status"] != "applied"
        or fixed["method_id"] != OBSERVER_METHOD
        or fixed["status"] != "applied"
    ):
        raise ValueError("Frozen lunar derivative was not fully applied")


def candidate_position(row, model, trace):
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.lunar_source_window import coherent_lunar_native_state
    from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS

    swe = runtime.swe
    flags = (
        swe.FLG_SWIEPH | swe.FLG_J2000 | swe.FLG_ICRS | swe.FLG_EQUATORIAL | swe.FLG_XYZ
    )
    native, returned, policy = coherent_lunar_native_state(
        "calc", row["jd_tt"], flags, row["jd_tt"], model, trace
    )
    mask = 0
    for flag in COORDINATE_FLAGS:
        mask |= getattr(swe, flag)
    if (
        returned < 0
        or runtime.ephemeris_model_from_retflag(returned) != model
        or returned & mask != (flags | swe.FLG_NONUT) & mask
        or len(native) != 6
        or not all(math.isfinite(v) for v in native)
    ):
        raise ValueError("ICRF source/coordinate contract changed")
    trace.observe("Moon_independent_position_layer", model)
    return {
        **position_comparison(row, native[:3]),
        "native_values": list(native),
        "returned_flags": returned,
        "source_window": policy,
    }


def candidate_rate(row, protocol, model, trace):
    from fatebridge.core.astro import ephemeris
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    jd = row["jd_tt"]
    tropical_meta, lahiri_meta = {}, {}
    tropical, returned_model = ephemeris._swisseph_planet_state(
        "Moon", jd, julian_day_tt=jd, source_trace=trace, motion_metadata=tropical_meta
    )
    if returned_model != model:
        raise ValueError("Declared physical source was not used")
    lahiri = native_lahiri_positions(
        ["Moon"],
        julian_day_ut1=jd,
        julian_day_tt=jd,
        source_trace=trace,
        motion_metadata=lahiri_meta,
    )["Moon"]
    axes, reference_policy = reference_axes(row, protocol)
    frames = {}
    for sidereal, state, metadata in [
        (False, tropical, tropical_meta),
        (True, lahiri, lahiri_meta),
    ]:
        require_lunar_policy(metadata)
        matrix, derivatives, geometry = orientation_derivative(
            jd, sidereal, model, trace
        )
        ref = display_reference(row, axes, matrix, derivatives)
        error = abs(state["longitude_speed"] * 3600 - ref["midpoint_arcsec_per_day"])
        radius = ref["rounding_and_frame_check_radius_arcsec_per_day"]
        frames["lahiri" if sidereal else "tropical"] = {
            "candidate_state": state,
            "reference": ref,
            "midpoint_error_arcsec_per_day": error,
            "conditional_error_lower_arcsec_per_day": max(0, error - radius),
            "conditional_error_upper_arcsec_per_day": error + radius,
            "motion_metadata": metadata,
            "frame_geometry": geometry,
        }
    return {
        "status": grade_frames(frames),
        "frames": frames,
        "fixed_line_arcsec_per_day": RATE_LINE,
        "reference_policy": reference_policy,
    }


def audit(args):
    root = Path(__file__).resolve().parents[1]
    seal = json.loads(args.candidate_seal.read_text())
    check_inputs(root, seal, args.protocol, args.reference)
    q = validate(args.protocol, args.reference, args.material, args.seal)
    protocol = json.loads(args.protocol.read_text())
    raw = json.loads(args.reference.read_text())
    if (
        protocol["id"] != "raw_DE441_lunar_full_kernel_recovery_holdout_v1"
        or len(protocol["cases"]) != 14
        or protocol["fixed_position_arcsec"] != 0.02
        or protocol["fixed_rate_arcsec_per_day"] != RATE_LINE
        or protocol["fixed_reference_convergence_arcsec_per_day"] != RATE_LINE
    ):
        raise ValueError("Frozen cohort or fixed numerical lines changed")
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

    trace = PhysicalEphemerisTrace()
    rows = []
    failed_reference = {v["id"] for v in q["failures"]}
    with args.output.with_suffix(".journal.jsonl").open("x") as journal:
        for row in raw["rows"]:
            quality = {
                "status": (
                    UNRESOLVED
                    if row["id"] in failed_reference
                    else "qualified_under_declared_numerical_model"
                )
            }
            record = {k: row[k] for k in ("id", "body", "date_tt", "role")}
            record.update(
                evaluate_layers(
                    row,
                    quality,
                    lambda: candidate_position(row, args.model, trace),
                    lambda: candidate_rate(row, protocol, args.model, trace),
                )
            )
            rows.append(record)
            journal.write(json.dumps(record, allow_nan=False) + "\n")
            journal.flush()
            print(record["id"], record["status"], flush=True)
    check_inputs(root, seal, args.protocol, args.reference)
    counts = {
        layer: {
            status: sum(r["layers"][layer]["status"] == status for r in rows)
            for status in (PASS, FAIL, UNRESOLVED, "candidate_error")
        }
        for layer in ("position", "rate")
    }
    code = (
        1
        if any(r["status"] in (FAIL, "candidate_error") for r in rows)
        else 2 if any(r["status"] != PASS for r in rows) else 0
    )
    result = {
        "method_id": METHOD,
        "model": args.model,
        "exit_code": code,
        "status": (
            "candidate_or_numeric_failure"
            if code == 1
            else (
                "reference_or_comparison_uncertainty_unresolved"
                if code == 2
                else "declared_lines_satisfied_under_reference_model"
            )
        ),
        "all_planned_case_count": len(rows),
        "new_predeclared_conditions": sum(
            r["role"] == "new_predeclared_condition" for r in rows
        ),
        "rows": rows,
        "layer_counts": counts,
        "reference_quality": q,
        "physical_sources": trace.finish(),
        "candidate_numerical_formula_changed": False,
        "old_failure_records_replaced": False,
        "full_objective_complete": False,
        "scope": "Independent printed ICRF directions and empirical derivative reference, shared native display orientation. Not a physical TT/TDB, frame, truncation or real-world prediction certification.",
    }
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return code


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol",
        "reference",
        "material",
        "seal",
        "candidate-seal",
        "output",
    ):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--model", choices=["swieph", "jpl"], required=True)
    raise SystemExit(audit(p.parse_args()))
