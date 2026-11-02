"""Full-population LP references for four fixed emission-transfer controls.

All observation endpoints, including correction uncertainty, remain constraints.
Neither physical model equivalence nor a polynomial remainder is established.
"""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_interval_reference import WINDOWS, verify
from scripts.astrodice_nonuniform_reference import (
    DEGREES,
    certified_derivative,
    interpolate,
    polynomial,
    quality,
)


def system(intervals, epochs, window, degree, axis):
    if window not in WINDOWS or degree not in DEGREES or axis not in (0, 1):
        raise ValueError("Unplanned interval polynomial")
    if sorted(intervals) != list(range(-1440, 1441, 5)) or set(epochs) != set(
        intervals
    ):
        raise ValueError("All 577 original nodes required")
    offsets = [o for o in sorted(intervals) if abs(o) <= window]
    center = sum(intervals[0][axis], Q()) / 2
    nodes = [(epochs[o] - epochs[0]) / window for o in offsets]
    if any(a >= b for a, b in zip(nodes, nodes[1:])):
        raise ValueError("Nonincreasing time axis")
    bounds = []
    for o in offsets:
        low, high = intervals[o][axis]
        if low >= high:
            raise ValueError("Observation interval empty")
        shift = (
            1296000 * (((low + high) / 2 - center + 648000) // 1296000)
            if axis == 0
            else 0
        )
        bounds.append((low - shift - center, high - shift - center))
    anchors = [k * (len(nodes) - 1) // degree for k in range(degree + 1)]
    baseline = interpolate(
        [nodes[k] for k in anchors], [sum(bounds[k], Q()) / 2 for k in anchors]
    )
    scale = max((b - a) / 2 for a, b in bounds)
    matrix, rhs = [], []
    for x, (low, high) in zip(nodes, bounds):
        powers = [x**p for p in range(degree + 1)]
        base = polynomial(baseline, x)
        matrix.extend([powers, [-v for v in powers]])
        rhs.extend([(high - base) / scale, (base - low) / scale])
    return matrix, rhs, baseline, scale


def fit(intervals, epochs, window, degree):
    axes = []
    for axis in (0, 1):
        a, b, baseline, scale = system(intervals, epochs, window, degree, axis)
        certificates = [certified_derivative(a, b, sign) for sign in (1, -1)]
        item = {
            "axis": axis,
            "baseline": list(map(str, baseline)),
            "scale_arcsec": str(scale),
            "certificates": certificates,
            "points_used": len(a) // 2,
        }
        if all(c["status"] == "exact_primal_dual_optimum" for c in certificates):
            permutation = [1, 0, *range(2, degree + 1)]
            matrix = [[row[k] for k in permutation] for row in a]
            low = baseline[1] + scale * verify(matrix, b, certificates[0])
            high = baseline[1] - scale * verify(matrix, b, certificates[1])
            item["derivative_interval_arcsec_per_TDB_day"] = [
                str(low * 86400 / window),
                str(high * 86400 / window),
            ]
        axes.append(item)
    return {
        "window_seconds": window,
        "full_degree": degree,
        "axes": axes,
        "status": (
            "conditional_exact_polynomial_interval"
            if all("derivative_interval_arcsec_per_TDB_day" in a for a in axes)
            else "polynomial_reference_unresolved"
        ),
        "physical_remainder_certified": False,
    }


def controls(data):
    rows = data["rows"]
    if [r["offset_seconds"] for r in rows] != list(range(-1440, 1441, 5)):
        raise ValueError("Complete transfer population required")
    for correction in ("raw", "corrected"):
        column = (
            "original_printing_interval_arcsec"
            if correction == "raw"
            else "corrected_observation_interval_arcsec"
        )
        intervals = {
            r["offset_seconds"]: [tuple(map(Q, v)) for v in r[column]] for r in rows
        }
        for clock in ("native_source_seconds", "nominal_TT_seconds"):
            epochs = {
                r["offset_seconds"]: (
                    Q(float.fromhex(r["receiver_hex"]))
                    if clock == "native_source_seconds"
                    else Q(r["offset_seconds"])
                )
                for r in rows
            }
            yield correction + "/" + clock, intervals, epochs


def analyze(path, proof_path):
    data = json.loads(path.read_text())
    proof = json.loads(proof_path.read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if proof["transfer_sha256"] != digest or proof["rows_checked"] != 577:
        raise ValueError("Independent complete transfer proof required")
    output = {
        "transfer_sha256": digest,
        "independent_transfer_proof_sha256": hashlib.sha256(
            proof_path.read_bytes()
        ).hexdigest(),
        "controls": {},
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "physical_remainder_certified": False,
        "original_reference_results_regraded": False,
        "full_goal_complete": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
    }
    for name, intervals, epochs in controls(data):
        fitted = []
        for window in WINDOWS:
            for degree in DEGREES:
                item = fit(intervals, epochs, window, degree)
                fitted.append(item)
                print(name, window, degree, item["status"], flush=True)
        assessment = quality(fitted)
        if name.endswith("nominal_TT_seconds"):
            # The numeric axis is requested TT offsets, not calibrated TDB.
            del assessment["TDB_day_not_certified_TT_day"]
            assessment["requested_TT_axis_not_internal_time_certified"] = True
            for row in fitted:
                for axis in row["axes"]:
                    old_key = "derivative_interval_arcsec_per_TDB_day"
                    if old_key in axis:
                        axis["derivative_interval_arcsec_per_nominal_TT_day"] = (
                            axis.pop(old_key)
                        )
        output["controls"][name] = {"all_windows": fitted, "quality": assessment}
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = analyze(args.input, args.proof)
    with args.output.open("x") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
