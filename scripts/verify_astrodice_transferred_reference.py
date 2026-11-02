"""Independent Vandermonde systems and exact all-point LP/quality replay."""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path

from scripts.verify_astrodice_nonuniform_reference import bound_proof, linear_solve

WINDOWS = [1440, 1080, 810, 600, 450, 330, 240, 180, 130, 90, 60]


def independent_system(intervals, epochs, window, degree, axis):
    offsets = list(range(-window, window + 1, 5))
    x = {o: (epochs[o] - epochs[0]) / window for o in offsets}
    center = sum(intervals[0][axis], Q()) / 2
    values = {}
    for o in offsets:
        a, b = intervals[o][axis]
        if axis == 0:
            while (a + b) / 2 - center >= 648000:
                a, b = a - 1296000, b - 1296000
            while (a + b) / 2 - center < -648000:
                a, b = a + 1296000, b + 1296000
        values[o] = a - center, b - center
    anchors = [offsets[k * (len(offsets) - 1) // degree] for k in range(degree + 1)]
    baseline = linear_solve(
        [[x[o] ** p for p in range(degree + 1)] for o in anchors],
        [sum(values[o], Q()) / 2 for o in anchors],
    )
    scale = max((b - a) / 2 for a, b in values.values())
    matrix, bounds = [], []
    for o in offsets:
        powers = [x[o] ** p for p in range(degree + 1)]
        base = sum((b * p for b, p in zip(baseline, powers)), Q())
        rotated = [powers[1], powers[0], *powers[2:]]
        matrix.extend([rotated, [-v for v in rotated]])
        bounds.extend([(values[o][1] - base) / scale, (base - values[o][0]) / scale])
    return matrix, bounds, baseline, scale


def fit_proof(intervals, epochs, saved, nominal=False):
    if [(r["window_seconds"], r["full_degree"]) for r in saved["all_windows"]] != [
        (w, d) for w in WINDOWS for d in (5, 7)
    ]:
        raise ValueError("Fixed windows/degrees changed")
    count = 0
    key = (
        "derivative_interval_arcsec_per_nominal_TT_day"
        if nominal
        else "derivative_interval_arcsec_per_TDB_day"
    )
    for row in saved["all_windows"]:
        w, d = row["window_seconds"], row["full_degree"]
        if len(row["axes"]) != 2 or row["physical_remainder_certified"]:
            raise ValueError("Polynomial scope changed")
        for axis, record in enumerate(row["axes"]):
            a, b, base, scale = independent_system(intervals, epochs, w, d, axis)
            if (
                record["axis"] != axis
                or record["baseline"] != list(map(str, base))
                or Q(record["scale_arcsec"]) != scale
                or record["points_used"] != len(a) // 2
            ):
                raise ValueError("Interval input or all-point constraints changed")
            certificates = record["certificates"]
            if len(certificates) != 2:
                raise ValueError("Certificate population changed")
            if all(c["status"] == "exact_primal_dual_optimum" for c in certificates):
                if [c["objective_sign"] for c in certificates] != [1, -1]:
                    raise ValueError("Objective changed")
                low = (base[1] + scale * bound_proof(a, b, certificates[0])) * 86400 / w
                high = (
                    (base[1] - scale * bound_proof(a, b, certificates[1])) * 86400 / w
                )
                if record[key] != list(map(str, (low, high))):
                    raise ValueError("Exact derivative interval changed")
                count += 2
            elif key in record:
                raise ValueError("Unresolved result promoted")
        valid = all(key in a for a in row["axes"])
        if row["status"] != (
            "conditional_exact_polynomial_interval"
            if valid
            else "polynomial_reference_unresolved"
        ):
            raise ValueError("Polynomial status changed")
    lookup = {(r["window_seconds"], r["full_degree"]): r for r in saved["all_windows"]}
    checks, selected = [], None
    for i in range(len(WINDOWS) - 2):
        triple = WINDOWS[i : i + 3]
        records = [lookup[w, d] for w in triple for d in (5, 7)]
        complete = all(
            r["status"] == "conditional_exact_polynomial_interval" for r in records
        )
        spread = radius = None
        if complete:
            bounds = [[tuple(map(Q, a[key])) for a in r["axes"]] for r in records]
            mids = [[(a + b) / 2 for a, b in box] for box in bounds]
            spread = max(
                sum(((a - b) ** 2 for a, b in zip(u, v)), Q())
                for u, v in combinations(mids, 2)
            )
            radius = max(
                sum((((b - a) / 2) ** 2 for a, b in box), Q()) for box in bounds
            )
        accepted = complete and spread <= Q(1, 500) ** 2 and radius <= Q(1, 500) ** 2
        checks.append(
            {
                "windows_seconds": triple,
                "complete_exact_certificates": complete,
                "maximum_coordinate_midpoint_distance_squared": (
                    str(spread) if complete else None
                ),
                "maximum_coordinate_radius_squared": str(radius) if complete else None,
                "conditional_quality_met": accepted,
            }
        )
        if accepted and selected is None:
            selected = {"window_seconds": triple[1], "full_degree": 7}
    expected = {
        "status": (
            "conditional_quality_met" if selected else "reference_quality_unresolved"
        ),
        "selected": selected,
        "all_window_checks": checks,
        "fixed_line_arcsec_per_day": "0.002",
        "coordinate_norm_conservative_for_tangent_direction": True,
        "production_reference_qualified": False,
    }
    expected[
        (
            "requested_TT_axis_not_internal_time_certified"
            if nominal
            else "TDB_day_not_certified_TT_day"
        )
    ] = True
    if saved["quality"] != expected:
        raise ValueError("Fixed quality rule changed")
    return count


def verify(path, transfer_path, proof_path):
    data, transferred, proof = [
        json.loads(p.read_text()) for p in (path, transfer_path, proof_path)
    ]
    digest = hashlib.sha256(transfer_path.read_bytes()).hexdigest()
    if (
        data["transfer_sha256"] != digest
        or proof["transfer_sha256"] != digest
        or proof["rows_checked"] != 577
        or data["independent_transfer_proof_sha256"]
        != hashlib.sha256(proof_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Independent transfer proof binding changed")
    if (
        any(
            data[k]
            for k in (
                "physical_service_model_equivalence_certified",
                "physical_TT_time_model_certified",
                "physical_remainder_certified",
                "original_reference_results_regraded",
                "full_goal_complete",
            )
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Conditional evidence promoted")
    rows = transferred["rows"]
    if [r["offset_seconds"] for r in rows] != list(range(-1440, 1441, 5)):
        raise ValueError("All 577 nodes required")
    expected = [
        c + "/" + t
        for c in ("raw", "corrected")
        for t in ("native_source_seconds", "nominal_TT_seconds")
    ]
    if list(data["controls"]) != expected:
        raise ValueError("A matched control was dropped")
    counts = {}
    for name in expected:
        column = (
            "original_printing_interval_arcsec"
            if name.startswith("raw/")
            else "corrected_observation_interval_arcsec"
        )
        intervals = {
            r["offset_seconds"]: [tuple(map(Q, v)) for v in r[column]] for r in rows
        }
        native = name.endswith("native_source_seconds")
        epochs = {
            r["offset_seconds"]: (
                Q(float.fromhex(r["receiver_hex"]))
                if native
                else Q(r["offset_seconds"])
            )
            for r in rows
        }
        counts[name] = fit_proof(
            intervals, epochs, data["controls"][name], nominal=not native
        )
        print(name, "independent exact certificates", counts[name], flush=True)
    return {
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "controls_checked": counts,
        "all_577_nodes_required": True,
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "physical_remainder_certified": False,
        "original_reference_results_regraded": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--transfer", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.input, args.transfer, args.proof)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
