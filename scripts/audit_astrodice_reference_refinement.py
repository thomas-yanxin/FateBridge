"""Replay a frozen multiscale reference and optionally compare unchanged v6.

Run without --model for a candidate-independent reference-quality report.
Display comparisons share the explicitly declared native frame orientation.
"""

import argparse
import json
import math
import traceback
from fractions import Fraction
from pathlib import Path

from scripts.astrodice_reference_refinement import (
    LINE,
    ORDERS,
    STEPS,
    portable_points,
    quality,
)
from scripts.audit_astrodice_horizons_wide_reference import center_tick, validate


def reference_report(protocol_path, reference_path, material, seal):
    baseline = validate(protocol_path, reference_path, material, seal)
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    if (
        protocol["refinement_method_id"] != "reference_multiscale_order_check_v1"
        or protocol["refinement_orders"] != list(ORDERS)
        or any(v != list(STEPS) for v in protocol["steps_seconds"].values())
        or protocol["fixed_reference_convergence_arcsec_per_day"] != LINE
        or protocol["fixed_rate_arcsec_per_day"] != LINE
        or protocol["fixed_position_arcsec"] != 0.02
    ):
        raise ValueError("Frozen refinement contract changed")
    rows = [{"id": r["id"], "role": r["role"], **quality(r)} for r in reference["rows"]]
    unresolved = [r["id"] for r in rows if r["status"] != "qualified"]
    return {
        "status": (
            "reference_quality_unresolved"
            if unresolved
            else "declared_reference_quality_satisfied"
        ),
        "exit_code": 2 if unresolved else 0,
        "raw_replay_with_all_support_disagreements_retained": baseline,
        "rows": rows,
        "unqualified_case_ids": unresolved,
        "candidate_output_used_for_selection": False,
        "scope": protocol["scope"],
        "full_goal_complete": False,
    }


def compare(protocol_path, reference_path, material, seal, output, model):
    reference_result = reference_report(protocol_path, reference_path, material, seal)
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.astro.zodiac import native_lahiri_positions
    from scripts.audit_astrodice_v6_wide import cross, dot, frame_rotation, rotate, unit

    reference = json.loads(reference_path.read_text())
    trace = PhysicalEphemerisTrace()
    results = []
    with output.with_suffix(".journal.jsonl").open("x") as journal:
        for row, independent in zip(reference["rows"], reference_result["rows"]):
            record = {k: row[k] for k in ["id", "body", "date_tt", "role"]}
            record["independent_reference"] = independent
            try:
                metadata = {}
                body, jd = row["body"], row["jd_tt"]
                tropical, actual_model = ephemeris._swisseph_planet_state(
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
                    motion_metadata=metadata,
                    source_trace=trace,
                )[body]
                if actual_model != model:
                    raise ValueError("Declared physical backend was not used")
                flags = (
                    runtime.swe.FLG_SWIEPH
                    | runtime.swe.FLG_J2000
                    | runtime.swe.FLG_ICRS
                    | runtime.swe.FLG_EQUATORIAL
                    | runtime.swe.FLG_XYZ
                )
                raw, ret = runtime.ephemeris_call(
                    "calc", jd, PLANET_SWISSEPH_IDS[body], flags
                )
                if ret < 0 or runtime.ephemeris_model_from_retflag(ret) != model:
                    raise ValueError("ICRF comparison source changed")
                observed = unit(raw[:3])
                points = portable_points(row)
                oracle = points["0"]
                position_error = (
                    math.degrees(
                        math.atan2(
                            math.hypot(*cross(observed, oracle)), dot(observed, oracle)
                        )
                    )
                    * 3600
                )
                frames = {}
                for sidereal, state in [(False, tropical), (True, lahiri)]:
                    name = "lahiri" if sidereal else "tropical"
                    projected = {}
                    geometry = []
                    for offset, point in points.items():
                        epoch = float(
                            Fraction(
                                center_tick(row["date_tt"]) + int(offset) * 1000000,
                                86400000000,
                            )
                            + Fraction(3442849, 2)
                        )
                        matrix, receipt = frame_rotation(epoch, sidereal, model, trace)
                        projected[offset] = rotate(matrix, point)
                        geometry.append(receipt)
                    selected = independent.get("selected_step_seconds")
                    projected_quality = quality(
                        row, projected, selected_step=selected, longitude=True
                    )
                    policy = metadata["complete_position_derivatives"][f"{body}:{name}"]
                    if (
                        policy["status"] != "applied"
                        or policy["method_id"]
                        != "fatebridge_complete_position_derivative_v6"
                    ):
                        raise ValueError("Actual v6 derivative was not applied")
                    result = {
                        "candidate_rate_degrees_per_day": state["longitude_speed"],
                        "reference_quality": projected_quality,
                        "policy": policy,
                        "frame_geometry": geometry,
                    }
                    if projected_quality["status"] == "qualified":
                        rate = math.degrees(
                            projected_quality["selected_derivative_per_day"][0]
                        )
                        result.update(
                            reference_rate_degrees_per_day=rate,
                            error_arcsec_per_day=abs(state["longitude_speed"] - rate)
                            * 3600,
                        )
                    frames[name] = result
                qualified = independent["status"] == "qualified" and all(
                    v["reference_quality"]["status"] == "qualified"
                    and v["reference_quality"]["selected_step_seconds"]
                    == independent["selected_step_seconds"]
                    for v in frames.values()
                )
                excess = position_error > 0.02 or any(
                    v.get("error_arcsec_per_day", 0) > LINE for v in frames.values()
                )
                record.update(
                    status=(
                        "reference_quality_unresolved"
                        if not qualified
                        else "numeric_failure" if excess else "declared_lines_satisfied"
                    ),
                    reference_qualified=qualified,
                    diagnostic_numeric_excess=excess,
                    position_error_arcsec=position_error,
                    frames=frames,
                )
            except Exception as error:
                record.update(
                    status="candidate_error",
                    error_type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                )
            results.append(record)
            journal.write(json.dumps(record, allow_nan=False) + "\n")
            journal.flush()
            print(record["id"], record["status"], flush=True)
    failures = sum(
        r["status"] in {"candidate_error", "numeric_failure"} for r in results
    )
    unresolved = sum(r["status"] == "reference_quality_unresolved" for r in results)
    code = 1 if failures else 2 if unresolved else 0
    return {
        "status": (
            "candidate_or_numeric_failure"
            if failures
            else (
                "reference_quality_unresolved"
                if unresolved
                else "declared_lines_satisfied"
            )
        ),
        "exit_code": code,
        "model": model,
        "rows": results,
        "cases": len(results),
        "qualified_within_lines": sum(
            r["status"] == "declared_lines_satisfied" for r in results
        ),
        "failures": failures,
        "unqualified_not_accepted": unresolved,
        "reference_result": reference_result,
        "physical_sources": trace.finish(),
        "candidate_numerical_formula_changed": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["protocol", "reference", "material", "seal", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model", choices=["swieph", "jpl"])
    args = parser.parse_args()
    if args.model:
        result = compare(
            args.protocol,
            args.reference,
            args.material,
            args.seal,
            args.output,
            args.model,
        )
    else:
        result = reference_report(
            args.protocol, args.reference, args.material, args.seal
        )
    with args.output.open("x") as f:
        f.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"rows", "reference_result", "physical_sources"}
            },
            indent=2,
        )
    )
    raise SystemExit(result["exit_code"])
