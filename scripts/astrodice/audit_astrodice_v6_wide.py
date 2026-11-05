"""Audit actual v6 display rates against independently collected TT directions.

The celestial directions are independent. Display reductions explicitly share
the native orientation, reconstructed from geometric vectors without using a
candidate derivative. This does not certify precession/nutation/Lahiri models.
"""

import argparse
import json
import math
import traceback
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from scripts.astrodice.audit_astrodice_horizons_wide_reference import (
    center_tick,
    interpolation_weights,
    validate,
)


def unit(values):
    radius = math.hypot(*values)
    if radius <= 0 or not math.isfinite(radius):
        raise ValueError("Invalid physical vector for frame reduction")
    return [v / radius for v in values]


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def basis(a, b):
    a = unit(a)
    b = unit([x - dot(a, b) * y for x, y in zip(b, a)])
    return [a, b, cross(a, b)]


def rotate(matrix, vector):
    return [dot(row, vector) for row in matrix]


def frame_rotation(epoch, sidereal, expected_model, trace):
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS

    swe = runtime.swe
    common = swe.FLG_SWIEPH | swe.FLG_TRUEPOS | swe.FLG_BARYCTR | swe.FLG_XYZ
    fixed = common | swe.FLG_J2000 | swe.FLG_ICRS | swe.FLG_EQUATORIAL
    display = common | (swe.FLG_SIDEREAL if sidereal else 0)
    if sidereal:
        runtime.ephemeris_call("set_sid_mode", swe.SIDM_LAHIRI, 0, 0)
    pairs = []
    coordinate_mask = 0
    for flag in COORDINATE_FLAGS:
        coordinate_mask |= getattr(swe, flag)
    for body in [swe.EARTH, swe.MERCURY, swe.MARS]:
        vectors = []
        for label, flags in [("fixed", fixed), ("display", display)]:
            value, ret = runtime.ephemeris_call("calc", epoch, body, flags)
            if ret < 0 or runtime.ephemeris_model_from_retflag(ret) != expected_model:
                raise ValueError("Frame reduction source changed")
            required = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL
            if flags & (swe.FLG_J2000 | swe.FLG_SIDEREAL):
                required |= swe.FLG_NONUT
            if ret & coordinate_mask != required & coordinate_mask:
                raise ValueError("Frame reduction coordinate contract changed")
            if len(value) != 6 or not all(math.isfinite(x) for x in value):
                raise ValueError("Invalid native frame vector")
            trace.observe(
                f"frame_bridge_{body}_{label}", expected_model, record_factor=False
            )
            vectors.append(unit(value[:3]))
        pairs.append(vectors)
    # Selection depends on geometry conditioning, never on an oracle residual.
    i, j = max(
        combinations(range(3), 2),
        key=lambda k: math.hypot(*cross(pairs[k[0]][0], pairs[k[1]][0])),
    )
    conditioning = math.hypot(*cross(pairs[i][0], pairs[j][0]))
    if conditioning < 0.001:
        raise ValueError("Ill-conditioned orientation reconstruction")
    first = basis(pairs[i][0], pairs[j][0])
    second = basis(pairs[i][1], pairs[j][1])
    matrix = [
        [math.fsum(second[k][a] * first[k][b] for k in range(3)) for b in range(3)]
        for a in range(3)
    ]
    orthogonal = max(
        abs(dot(matrix[a], matrix[b]) - int(a == b)) for a in range(3) for b in range(3)
    )
    replay = max(math.dist(rotate(matrix, pair[0]), pair[1]) for pair in pairs)
    if orthogonal > 2e-12 or replay > 1e-11:
        raise ValueError("Native orientation does not map all geometric witnesses")
    return matrix, {
        "basis_indices": [i, j],
        "cross_product_conditioning": conditioning,
        "orthogonality_maximum": orthogonal,
        "geometric_witness_replay_maximum": replay,
    }


def derivative(points, h, weights):
    center = points["0"]
    differences = {
        k: math.remainder(
            math.degrees(math.atan2(v[1], v[0]))
            - math.degrees(math.atan2(center[1], center[0])),
            360,
        )
        for k, v in points.items()
    }
    if any(abs(v) >= 90 for v in differences.values()):
        raise ValueError("Reference longitude branch is not local")
    return (
        math.fsum(
            float(weights[k]) * (differences[str(k * h)] - differences[str(-k * h)])
            for k in range(1, 7)
        )
        * 86400
        / h
    )


def audit(
    protocol_path,
    reference_path,
    material,
    seal,
    output,
    expected_model,
):
    validation = validate(protocol_path, reference_path, material, seal)
    from fatebridge.core.astro import ephemeris, runtime
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS
    from fatebridge.core.astro.zodiac import native_lahiri_positions

    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    weights = interpolation_weights()
    trace = PhysicalEphemerisTrace()
    rows = []
    with output.with_suffix(".journal.jsonl").open("x") as journal:
        for row in reference["rows"]:
            if row["body"] == "Moon":
                continue
            record = {k: row[k] for k in ["id", "body", "date_tt", "role", "jd_tt"]}
            try:
                if row["missing_offsets_seconds"]:
                    record.update(
                        status="reference_unavailable",
                        missing_offsets_seconds=row["missing_offsets_seconds"],
                    )
                else:
                    metadata = {}
                    jd = row["jd_tt"]
                    body = row["body"]
                    tropical, model = ephemeris._swisseph_planet_state(
                        body,
                        jd,
                        julian_day_tt=jd,
                        source_trace=trace,
                        motion_metadata=metadata,
                    )
                    if model != expected_model:
                        raise ValueError("Requested physical backend was not used")
                    lahiri = native_lahiri_positions(
                        [body],
                        julian_day_ut1=jd,
                        julian_day_tt=jd,
                        motion_metadata=metadata,
                        source_trace=trace,
                    )[body]
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
                        raise ValueError("ICRF source changed")
                    observed = unit(raw[:3])
                    oracle = row["samples"]["0"]["unit_direction"]
                    position_error = (
                        math.degrees(
                            math.atan2(
                                math.hypot(*cross(observed, oracle)),
                                dot(observed, oracle),
                            )
                        )
                        * 3600
                    )
                    frame_results = {}
                    for sidereal, state in [(False, tropical), (True, lahiri)]:
                        name = "lahiri" if sidereal else "tropical"
                        projected = {}
                        geometry = []
                        for offset, point in row["samples"].items():
                            # Exact requested TT is rounded once at the public native API.
                            epoch = float(
                                Fraction(
                                    center_tick(row["date_tt"]) + int(offset) * 1000000,
                                    86400000000,
                                )
                                + Fraction(3442849, 2)
                            )
                            matrix, receipt = frame_rotation(
                                epoch, sidereal, model, trace
                            )
                            projected[offset] = rotate(matrix, point["unit_direction"])
                            geometry.append(receipt)
                        estimates = {
                            str(h): derivative(projected, h, weights)
                            for h in protocol["steps_seconds"][body]
                        }
                        selected = estimates[
                            str(protocol["selected_step_seconds"][body])
                        ]
                        policy = metadata["complete_position_derivatives"][
                            f"{body}:{name}"
                        ]
                        if (
                            policy["status"] != "applied"
                            or policy["method_id"]
                            != "fatebridge_complete_position_derivative_v6"
                        ):
                            raise ValueError("Actual v6 derivative was not applied")
                        frame_results[name] = {
                            "source_function_rate": state["longitude_speed"],
                            "native_uncorrected_rate": state.get(
                                "longitude_speed_native"
                            ),
                            "reference_rates": estimates,
                            "error_arcsec_per_day": abs(
                                state["longitude_speed"] - selected
                            )
                            * 3600,
                            "reference_step_difference_arcsec_per_day": abs(
                                estimates[str(protocol["steps_seconds"][body][0])]
                                - estimates[str(protocol["steps_seconds"][body][1])]
                            )
                            * 3600,
                            "selected_stencil": policy["selected_stencil"],
                            "actual_method_id": policy["method_id"],
                            "policy": policy,
                            "frame_geometry": geometry,
                        }
                    bad = position_error > protocol["fixed_position_arcsec"] or any(
                        v["error_arcsec_per_day"]
                        > protocol["fixed_rate_arcsec_per_day"]
                        for v in frame_results.values()
                    )
                    unresolved = row["step_difference_arcsec_per_day"] > protocol[
                        "fixed_reference_convergence_arcsec_per_day"
                    ] or any(
                        v["reference_step_difference_arcsec_per_day"]
                        > protocol["fixed_reference_convergence_arcsec_per_day"]
                        for v in frame_results.values()
                    )
                    record.update(
                        status=(
                            "numeric_failure"
                            if bad
                            else (
                                "reference_quality_unresolved"
                                if unresolved
                                else "declared_lines_satisfied"
                            )
                        ),
                        position_error_arcsec=position_error,
                        reference_icrf_step_difference_arcsec_per_day=row[
                            "step_difference_arcsec_per_day"
                        ],
                        frames=frame_results,
                    )
            except Exception as error:
                record.update(
                    status="candidate_error",
                    exception_type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                )
            rows.append(record)
            journal.write(json.dumps(record, allow_nan=False) + "\n")
            journal.flush()
            print(row["id"], record["status"], flush=True)
    # Moon direction-rate comparison preserves the previously frozen source
    # algorithm and request order; no inner-planet stencil is applied to Moon.
    from scripts.astrodice.audit_astrodice_lunar_precision import audit as audit_moon

    adapted = {
        "rows": [
            {
                "date_tt": r["date_tt"],
                "cohort": "holdout" if r["role"] == "fresh_holdout" else "development",
                "status": "incomplete" if r["missing_offsets_seconds"] else "available",
                "missing_probes": r["missing_offsets_seconds"],
                "jd_tt": r["jd_tt"],
                "icrf_unit_direction": (
                    r["samples"]["0"]["unit_direction"]
                    if r["samples"].get("0")
                    else None
                ),
                "icrf_direction_derivative_per_day": r["derivatives_per_tt_day"].get(
                    str(protocol["selected_step_seconds"]["Moon"])
                ),
                "step_difference_arcsec_per_day": r["step_difference_arcsec_per_day"],
            }
            for r in reference["rows"]
            if r["body"] == "Moon"
        ]
    }
    moon = audit_moon(protocol, adapted, production_order=True)
    if moon["model"] != expected_model:
        raise ValueError("Moon physical backend mismatch")
    numeric = sum(r["status"] in {"numeric_failure", "candidate_error"} for r in rows)
    unresolved = (
        any(
            r["status"] in {"reference_unavailable", "reference_quality_unresolved"}
            for r in rows
        )
        or validation["exit_code"] != 0
    )
    code = (
        1
        if numeric or moon["exit_code"] == 1
        else 2 if unresolved or moon["exit_code"] == 2 else 0
    )
    result = {
        "status": (
            "numerical_or_candidate_failure"
            if code == 1
            else (
                "reference_evidence_unresolved"
                if code == 2
                else "declared_lines_satisfied"
            )
        ),
        "exit_code": code,
        "expected_model": expected_model,
        "inner_cases": rows,
        "inner_numerical_failures": numeric,
        "reference_validation": validation,
        "moon_comparison": moon,
        "physical_sources": trace.finish(),
        "scope": protocol["scope"],
        "display_frame_reduction_scope": protocol["frame_bridge_policy"],
        "full_goal_complete": False,
    }
    with output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"inner_cases", "moon_comparison", "physical_sources"}
            },
            indent=2,
        )
    )
    raise SystemExit(code)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in [
        "protocol",
        "reference",
        "material",
        "seal",
        "output",
    ]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model", required=True, choices=["swieph", "jpl"])
    a = parser.parse_args()
    audit(a.protocol, a.reference, a.material, a.seal, a.output, a.model)
