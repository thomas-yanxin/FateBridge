"""Audit position and rate independently against local interval references.

Neither an unavailable rate nor a candidate exception can erase a usable
position comparison. Solar-convention receipts explain comparability; they
never exclude a case, change its numerical result or relax a fixed line.
"""

import argparse
import json
import math
import traceback
from pathlib import Path

from scripts.astrodice_interval_reference import replay_interval, tangent_geometry
from scripts.audit_astrodice_horizons_wide_reference import interpolation_weights
from scripts.audit_astrodice_local_reference import parent_from_args, replay
from scripts.audit_astrodice_v6_wide import cross, dot, frame_rotation, rotate, unit

AS_PER_RADIAN = math.degrees(1.0) * 3600
POSITION_LINE = 0.02
RATE_LINE = 0.002
PASS = "declared_lines_satisfied_under_reference_model"
FAIL = "numeric_failure_under_declared_reference_model"
UNRESOLVED = "reference_quality_unresolved"


def require_declared_derivative(source, policy):
    expected = source.get(
        "expected_derivative_method_id", "fatebridge_complete_position_derivative_v6"
    )
    if expected not in {
        "fatebridge_complete_position_derivative_v6",
        "fatebridge_complete_position_derivative_v7",
        "fatebridge_complete_position_derivative_v8",
    }:
        raise ValueError("Unplanned candidate derivative method")
    if policy["status"] != "applied" or policy["method_id"] != expected:
        raise ValueError("Declared candidate derivative was not applied: " + expected)


def position_comparison(row, observed):
    direction, _, _, noise = tangent_geometry(row)
    observed = unit(observed)
    error = math.atan2(
        math.hypot(*cross(observed, direction)), dot(observed, direction)
    )
    radius = math.nextafter(noise * AS_PER_RADIAN + 1e-9, math.inf)
    error *= AS_PER_RADIAN
    lower, upper = max(0.0, error - radius), error + radius
    return {
        "status": (
            FAIL
            if lower > POSITION_LINE
            else PASS if upper <= POSITION_LINE else UNRESOLVED
        ),
        "midpoint_error_arcsec": error,
        "printing_and_arithmetic_radius_arcsec": radius,
        "conditional_error_lower_arcsec": lower,
        "conditional_error_upper_arcsec": upper,
        "fixed_line_arcsec": POSITION_LINE,
        "scope": "Center printed-angle comparison only; independent of rate-reference availability. Printing/arithmetic uncertainty is not a physical ephemeris error bound.",
    }


def evaluate_layers(row, reference_quality, position_provider, rate_provider):
    """Keep all planned layers, including independent exceptions/unavailability."""
    layers = {}
    for name, available, provider in [
        ("position", row["samples"].get("0") is not None, position_provider),
        (
            "rate",
            reference_quality["status"] == "qualified_under_declared_numerical_model",
            rate_provider,
        ),
    ]:
        if not available:
            layers[name] = {
                "status": UNRESOLVED,
                "reason": (
                    "center_missing"
                    if name == "position"
                    else "rate_reference_unqualified"
                ),
            }
            continue
        try:
            layers[name] = provider()
            if layers[name].get("status") not in {PASS, FAIL, UNRESOLVED}:
                raise ValueError("Unknown evidence-layer outcome")
        except Exception as error:
            layers[name] = {
                "status": "candidate_error",
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
    statuses = [v["status"] for v in layers.values()]
    status = next(
        (s for s in ["candidate_error", FAIL, UNRESOLVED] if s in statuses), PASS
    )
    return {"status": status, "layers": layers}


def orientation_derivative(epoch, sidereal, model, trace):
    weights = interpolation_weights()
    center, geometry = frame_rotation(epoch, sidereal, model, trace)
    derivatives = []
    for h in [0.125, 0.0625]:
        samples = {
            k: frame_rotation(epoch + k * h, sidereal, model, trace)[0]
            for k in range(-6, 7)
            if k
        }
        derivatives.append(
            [
                [
                    math.fsum(
                        float(weights[k]) * (samples[k][i][j] - samples[-k][i][j])
                        for k in range(1, 7)
                    )
                    / h
                    for j in range(3)
                ]
                for i in range(3)
            ]
        )
    return center, derivatives, geometry


def display_reference(row, angular_axes, matrix, derivatives):
    direction, pa, pd, center_noise = tangent_geometry(row)
    position = rotate(matrix, direction)
    a = rotate(matrix, pa)
    b = rotate(matrix, pd)
    rho2 = position[0] ** 2 + position[1] ** 2
    if rho2 < 0.0001:
        raise ValueError("Ill-conditioned local display longitude")

    def longitude_rate(v):
        return (position[0] * v[1] - position[1] * v[0]) / rho2

    coefficients = [longitude_rate(a), longitude_rate(b)]
    mids = [float((lo + hi) / 2) for lo, hi in angular_axes]
    radii = [float((hi - lo) / 2) for lo, hi in angular_axes]
    frame_rates = [
        longitude_rate(rotate(d, direction)) * AS_PER_RADIAN for d in derivatives
    ]
    spread = abs(frame_rates[0] - frame_rates[1])
    frame_rate = frame_rates[-1]
    mid = math.fsum(c * v for c, v in zip(coefficients, mids)) + frame_rate
    radius = (
        math.fsum(abs(c) * v for c, v in zip(coefficients, radii))
        + spread
        + 4 * center_noise / rho2 * (sum(abs(v) for v in mids) + abs(frame_rate))
        + 1e-7
    )
    return {
        "midpoint_arcsec_per_day": mid,
        "rounding_and_frame_check_radius_arcsec_per_day": math.nextafter(
            radius, math.inf
        ),
        "angular_coefficients": coefficients,
        "frame_rate_arcsec_per_day": frame_rate,
        "frame_step_difference_arcsec_per_day": spread,
        "frame_check_qualified": spread <= 0.00002,
        "scope": "Exact angular printing constraints projected with a shared native orientation;frame step agreement is empirical,not an independent frame-model accuracy bound.",
    }


def audit(args):
    certs = json.loads(args.certificates.read_text())
    reference = replay(
        args.protocol,
        args.reference,
        args.material,
        args.seal,
        certs,
        parent_bundle=parent_from_args(args),
    )
    source = {
        "expected_derivative_method_id": "fatebridge_complete_position_derivative_v8"
    }
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    raw = json.loads(args.reference.read_text())
    trace = PhysicalEphemerisTrace()
    rows = []
    with args.output.with_suffix(".journal.jsonl").open("x") as journal:
        for row, certificate, q in zip(raw["rows"], certs["rows"], reference["rows"]):
            record = {k: row[k] for k in ["id", "body", "date_tt", "role"]}
            record["reference_quality"] = q
            body, jd = row["body"], row["jd_tt"]

            def position_provider():
                flags = (
                    runtime.swe.FLG_SWIEPH
                    | runtime.swe.FLG_J2000
                    | runtime.swe.FLG_ICRS
                    | runtime.swe.FLG_EQUATORIAL
                    | runtime.swe.FLG_XYZ
                )
                native, returned = runtime.ephemeris_call(
                    "calc", jd, PLANET_SWISSEPH_IDS[body], flags
                )
                mask = 0
                for name in COORDINATE_FLAGS:
                    mask |= getattr(runtime.swe, name)
                if (
                    returned < 0
                    or runtime.ephemeris_model_from_retflag(returned) != args.model
                    or returned & mask != (flags | runtime.swe.FLG_NONUT) & mask
                    or len(native) != 6
                    or not all(math.isfinite(v) for v in native)
                ):
                    raise ValueError("ICRF source/coordinate contract changed")
                trace.observe(f"{body}_independent_position_layer", args.model)
                result = position_comparison(row, native[:3])
                # Provenance is supplemental. Its failure cannot suppress an
                # already computed position result or convert a failure to pass.
                from fatebridge.core.astro.solar_position import (
                    apparent_position_policy,
                )

                try:
                    result["apparent_position_policy"] = apparent_position_policy(
                        jd, {body: args.model}, trace
                    )
                except Exception as error:
                    result["convention_receipt_error"] = {
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                result["reference_convention_equivalence_certified"] = False
                result["convention_receipt_changes_numerical_grade"] = False
                return result

            def rate_provider():
                metadata = {}
                tropical, model = ephemeris._swisseph_planet_state(
                    body,
                    jd,
                    julian_day_tt=jd,
                    source_trace=trace,
                    motion_metadata=metadata,
                )
                lahiri = native_lahiri_positions(
                    [body],
                    julian_day_ut1=jd,
                    julian_day_tt=jd,
                    source_trace=trace,
                    motion_metadata=metadata,
                )[body]
                if model != args.model:
                    raise ValueError("Declared physical source was not used")
                chosen = next(
                    f
                    for f in certificate["fits"]
                    if f["window_seconds"] == q["selected_window_seconds"]
                    and f["odd_order"] == q["selected_order"]
                )
                angular_axes = replay_interval(
                    row, chosen, step_seconds=reference.get("grid_step_seconds", 10)
                )
                frames = {}
                for sidereal, state in [(False, tropical), (True, lahiri)]:
                    name = "lahiri" if sidereal else "tropical"
                    matrix, derivatives, geometry = orientation_derivative(
                        jd, sidereal, model, trace
                    )
                    ref = display_reference(row, angular_axes, matrix, derivatives)
                    policy = metadata["complete_position_derivatives"][f"{body}:{name}"]
                    require_declared_derivative(source, policy)
                    error = abs(
                        state["longitude_speed"] * 3600 - ref["midpoint_arcsec_per_day"]
                    )
                    radius = ref["rounding_and_frame_check_radius_arcsec_per_day"]
                    frames[name] = {
                        "candidate_rate_degrees_per_day": state["longitude_speed"],
                        "reference": ref,
                        "midpoint_error_arcsec_per_day": error,
                        "conditional_error_upper_arcsec_per_day": error + radius,
                        "conditional_error_lower_arcsec_per_day": max(
                            0, error - radius
                        ),
                        "policy": policy,
                        "frame_geometry": geometry,
                    }
                bad = any(
                    v["conditional_error_lower_arcsec_per_day"] > RATE_LINE
                    for v in frames.values()
                )
                unresolved = any(
                    not v["reference"]["frame_check_qualified"]
                    or v["conditional_error_upper_arcsec_per_day"] > RATE_LINE
                    for v in frames.values()
                )
                return {
                    "status": FAIL if bad else UNRESOLVED if unresolved else PASS,
                    "fixed_line_arcsec_per_day": RATE_LINE,
                    "frames": frames,
                }

            record.update(evaluate_layers(row, q, position_provider, rate_provider))
            rows.append(record)
            journal.write(json.dumps(record, allow_nan=False) + "\n")
            journal.flush()
            print(record["id"], record["status"], flush=True)
    failures = sum(
        r["status"]
        in {"candidate_error", "numeric_failure_under_declared_reference_model"}
        for r in rows
    )
    unresolved = sum(
        r["status"]
        in {"reference_quality_unresolved", "comparison_uncertainty_unresolved"}
        for r in rows
    )
    code = 1 if failures else 2 if unresolved else 0
    result = {
        "audit_method_id": "independent_position_and_rate_layers_v2",
        "status": (
            "candidate_or_numeric_failure"
            if failures
            else (
                "reference_or_comparison_uncertainty_unresolved"
                if unresolved
                else "declared_numerical_lines_satisfied_under_reference_model"
            )
        ),
        "exit_code": code,
        "model": args.model,
        "rows": rows,
        "layer_counts": {
            layer: {
                status: sum(r["layers"][layer]["status"] == status for r in rows)
                for status in [PASS, FAIL, UNRESOLVED, "candidate_error"]
            }
            for layer in ["position", "rate"]
        },
        "all_planned_case_count": len(rows),
        "fixed_position_arcsec": POSITION_LINE,
        "fixed_rate_arcsec_per_day": RATE_LINE,
        "reference": reference,
        "physical_sources": trace.finish(),
        "candidate_numerical_formula_changed": False,
        "full_objective_complete": False,
        "scope": "Conditional printed-angle polynomial reference,shared native frame;not full physical/truncation accuracy or prediction certification.",
    }
    with args.output.open("x") as f:
        f.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return code


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in [
        "protocol",
        "reference",
        "material",
        "seal",
        "certificates",
        "output",
    ]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--model", choices=["swieph", "jpl"], required=True)
    for name in ["protocol", "reference", "material", "seal"]:
        p.add_argument("--parent-" + name, type=Path)
    raise SystemExit(audit(p.parse_args()))
