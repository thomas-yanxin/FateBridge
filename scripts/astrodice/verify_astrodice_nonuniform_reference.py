"""Independent source clock, grid, and all-point polynomial certificates.

The producer's Lagrange interpolation and source evaluator are not imported.
The raw observer table is parsed separately; missing premises remain false.
"""

import argparse
import csv
import hashlib
import json
import re
from decimal import Decimal
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path

from scripts.astrodice.verify_astrodice_earth_clock import raw_rows, vector_proof, wire
from scripts.astrodice.verify_astrodice_emission_epoch import enumerate_bits, from_raw
from scripts.astrodice.verify_astrodice_joint_epoch import exact_state
from scripts.astrodice.verify_astrodice_vector_clock import observed_bounds


def linear_solve(a, b):
    n = len(b)
    matrix = [[Q(x) for x in row] + [Q(value)] for row, value in zip(a, b)]
    for col in range(n):
        p = next(k for k in range(col, n) if matrix[k][col])
        matrix[col], matrix[p] = matrix[p], matrix[col]
        divisor = matrix[col][col]
        matrix[col] = [x / divisor for x in matrix[col]]
        for k in range(n):
            if k != col:
                factor = matrix[k][col]
                matrix[k] = [x - factor * y for x, y in zip(matrix[k], matrix[col])]
    return [row[-1] for row in matrix]


def independent_system(angles, epochs, window, degree, axis):
    offsets = list(range(-window, window + 1, 5))
    x = {o: (epochs[o] - epochs[0]) / window for o in offsets}
    center = Q(angles[0][axis])
    values = {}
    for o in offsets:
        angle = Q(angles[o][axis])
        if axis == 0:
            while angle - center >= 180:
                angle -= 360
            while angle - center < -180:
                angle += 360
        values[o] = (angle - center) * 3600
    anchors = [offsets[k * (len(offsets) - 1) // degree] for k in range(degree + 1)]
    baseline = linear_solve(
        [[x[o] ** p for p in range(degree + 1)] for o in anchors],
        [values[o] for o in anchors],
    )
    noise = {
        o: Q(10) ** Decimal(angles[o][axis]).as_tuple().exponent * 3600 for o in offsets
    }
    scale = max(noise.values())
    matrix, bounds = [], []
    for o in offsets:
        powers = [x[o] ** p for p in range(degree + 1)]
        y = (values[o] - sum((b * p for b, p in zip(baseline, powers)), Q())) / scale
        rotated = [powers[1], powers[0], *powers[2:]]
        matrix.extend([rotated, [-v for v in rotated]])
        bounds.extend([y + noise[o] / scale, -y + noise[o] / scale])
    return matrix, bounds, baseline, scale


def bound_proof(a, b, cert):
    n = len(a[0])
    primal = list(map(Q, cert["primal"]))
    dual = list(map(Q, cert["dual"]))
    active = cert["active"]
    sign = cert["objective_sign"]
    if (
        len(primal) != n
        or len(dual) != n
        or len(active) != n
        or len(set(active)) != n
        or sign not in {-1, 1}
    ):
        raise ValueError("Invalid independent certificate dimensions")
    if any(v > 0 for v in dual) or any(
        sum((x * y for x, y in zip(row, primal)), Q()) > rhs for row, rhs in zip(a, b)
    ):
        raise ValueError("All-point primal or dual inequality failed")
    for j in range(n):
        if sum((w * a[i][j] for i, w in zip(active, dual)), Q()) != (
            sign if j == 0 else 0
        ):
            raise ValueError("Independent exact dual identity failed")
    value = sum((w * b[i] for i, w in zip(active, dual)), Q())
    if value != sign * primal[0] or value != Q(cert["optimum"]):
        raise ValueError("Independent exact optimum failed")
    return value


def inspect_angles(run, cohort, plan):
    output = {}
    for query in plan["queries"] + plan["adopted_A_observer_queries"]:
        if query["cohort"] != cohort or query["kind"] != "observer":
            continue
        folder = run / ("adopted-A" if cohort == "A" else "responses")
        raw = (folder / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads((folder / (query["id"] + ".receipt.json")).read_text())
        if (
            receipt["status"] != 200
            or hashlib.sha256(raw).hexdigest() != receipt["raw_sha256"]
        ):
            raise ValueError("Observer transport changed")
        payload = json.loads(raw)
        text = payload["result"]
        pre, data = text.split("$$SOE")
        data, _ = data.split("$$EOE")
        for expr in [
            r"Target body name: Venus.*?\(299\).*?DE441",
            r"Center body name: Earth \(399\).*?DE441",
            r"Calendar mode\s*:\s*Gregorian",
            r"Date__\(TT\)",
            r"JDTT",
            r"RA_\(ICRF-a-app\)",
        ]:
            if not re.search(expr, pre):
                raise ValueError("Independent observer contract mismatch")
        seen = set()
        for row in csv.reader(data.strip().splitlines()):
            row = [v.strip() for v in row]
            if len(row) != 7 or row[-1]:
                raise ValueError("Independent observer column mismatch")
            near = [
                c
                for c in query["cases"]
                if abs(Q(row[1]) - Q(c["nominal_JD"])) <= Q("1e-9")
            ]
            if len(near) != 1 or near[0]["id"] in seen:
                raise ValueError("Observer identity ambiguous")
            c = near[0]
            seen.add(c["id"])
            if c["role"] != "auxiliary_not_primary":
                if str(c["offset_seconds"]) in output:
                    raise ValueError("Repeated observer node")
                output[str(c["offset_seconds"])] = row[4:6]
        if seen != {c["id"] for c in query["cases"]}:
            raise ValueError("Missing observer node")
    if set(map(int, output)) != set(range(-1440, 1441, 5)):
        raise ValueError("Full 577 nodes missing")
    if output != json.loads((run / (cohort + "-angles.json")).read_text()):
        raise ValueError("Observed angles changed")
    return {int(k): v for k, v in output.items()}


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    for name, h in plan["inputs_sha256"].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != h:
            raise ValueError("Frozen input drift: " + name)
    saved = json.loads((run / (cohort + "-first-analysis.json")).read_text())
    if (
        saved["plan_sha256"] != hashlib.sha256(rawplan).hexdigest()
        or saved["cohort"] != cohort
    ):
        raise ValueError("Analysis identity changed")
    if (
        saved["full_goal_complete"]
        or saved["physical_time_model_certified"]
        or saved["OBSERVER_vector_clock_identity_certified"]
        or saved["new_candidate_holdouts"]
        or saved["production_acceptance_exit_code"] != 2
        or saved["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Unproved acceptance promoted")
    angles = inspect_angles(run, cohort, plan)
    queries = [
        q for q in plan["queries"] if q["cohort"] == cohort and q["kind"] == "geometry"
    ]
    if [q["id"] for q in queries] != [q["id"] for q in saved["queries"]]:
        raise ValueError("Source query population changed")
    index = {}
    endpoints = boxes = points = 0
    for query, group in zip(queries, saved["queries"]):
        if group["body"] != query["body"]:
            raise ValueError("Source body metadata changed")
        observers = plan["queries"] + plan["adopted_A_observer_queries"]
        observer = next(q for q in observers if q["id"] == query["source_observer_id"])
        for key in (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        ):
            if query["parameters"][key] != observer["parameters"][key]:
                raise ValueError("Exact observer/geometry TT input batches differ")
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Unavailable source row")
        original = [
            r
            for r in raw_rows(raw, query, query["cases"], plan)
            if r["role"] != "auxiliary_not_primary"
        ]
        if [r["case_id"] for r in original] != [r["case_id"] for r in group["rows"]]:
            raise ValueError("Source row population changed")
        for row, record in zip(original, group["rows"]):
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            e, b = vector_proof(run, query["body"], case, row, record, plan)
            endpoints += e
            boxes += b
            for profile, inv in record["profiles"].items():
                item = record["grid"][profile]
                if inv["status"] != "bracketed":
                    expected = {
                        "status": "inverse_unknown",
                        "grid_hex": [],
                        "six_component_matches": [],
                    }
                else:
                    a, b = map(Q, inv["effective_JD"])
                    status, grid = enumerate_bits(
                        (a - 2451545) * 86400, (b - 2451545) * 86400, 4096
                    )
                    matches = []
                    for value in grid:
                        state = exact_state(
                            run / "source-records",
                            case["window_index"],
                            from_raw(value, "seconds_from_J2000_binary64"),
                            query["body"],
                        )
                        obs = [
                            observed_bounds(
                                v,
                                plan["numerical_tube_profiles"][profile][
                                    "extra_binary64_ULPs"
                                ],
                            )
                            for v in row["printed_state"]
                        ]
                        if all(a <= v <= b for v, (a, b) in zip(state, obs)):
                            matches.append(value.hex())
                        points += 1
                    expected = {
                        "status": status,
                        "grid_hex": [v.hex() for v in grid],
                        "six_component_matches": matches,
                    }
                if item != expected:
                    raise ValueError("Independent grid candidate mismatch")
            index[query["body"], case["offset_seconds"]] = record
    certified = 0
    full_populations = {}
    for profile in plan["numerical_tube_profiles"]:
        epochs = {}
        statuses = saved["clock_population"][profile]
        if [r["offset_seconds"] for r in statuses] != list(range(-1440, 1441, 5)):
            raise ValueError("Clock population reduced")
        for entry in statuses:
            o = entry["offset_seconds"]
            earth = index["Earth", o]
            venus = index["Venus", o]
            common = sorted(
                set(earth["grid"][profile]["six_component_matches"])
                & set(venus["grid"][profile]["six_component_matches"])
            )
            e_inv, v_inv = earth["profiles"][profile], venus["profiles"][profile]
            bracketed = e_inv["status"] == v_inv["status"] == "bracketed"
            ea, eb = map(Q, e_inv["effective_JD"]) if bracketed else (Q(1), Q(0))
            va, vb = map(Q, v_inv["effective_JD"]) if bracketed else (Q(1), Q(0))
            # Common exact source point has already passed both full states.
            qualified = (
                bracketed
                and len(common) == 1
                and max(ea, va) <= min(eb, vb)
                and all(
                    r["profiles"][profile]["all_six_compatible"]
                    and r["original_label_budget_pass"]
                    for r in (earth, venus)
                )
            )
            if entry != {
                "offset_seconds": o,
                "common_ET_hex": common,
                "qualified": qualified,
            }:
                raise ValueError("Clock qualification changed")
            if qualified:
                epochs[o] = Q(float.fromhex(common[0]))
        full_populations[profile] = len(epochs)
        fits = saved["fits"][profile]
        if len(epochs) != 577:
            if fits != {
                "status": "full_clock_population_unqualified",
                "qualified_nodes": len(epochs),
                "required_nodes": 577,
            }:
                raise ValueError("Incomplete population promoted")
            continue
        if (
            fits["status"] != "conditional_diagnostic_only"
            or fits["original_odd_polynomial_acceptance_replaced"]
            or fits["TT_derivative_certified"]
            or fits["OBSERVER_clock_certified"]
        ):
            raise ValueError("Conditional fit promoted")
        expected_windows = [(w, d) for w in plan["windows_seconds"] for d in (5, 7)]
        if [
            (w["window_seconds"], w["full_degree"]) for w in fits["all_windows"]
        ] != expected_windows:
            raise ValueError("Window or degree dropped")
        for window in fits["all_windows"]:
            w, d = window["window_seconds"], window["full_degree"]
            for axis, record in enumerate(window["axes"]):
                a, b, base, scale = independent_system(angles, epochs, w, d, axis)
                if (
                    record["axis"] != axis
                    or record["baseline"] != list(map(str, base))
                    or Q(record["scale_arcsec"]) != scale
                    or record["points_used"] != len(a) // 2
                ):
                    raise ValueError("Polynomial population or baseline changed")
                certs = record["certificates"]
                if all(c["status"] == "exact_primal_dual_optimum" for c in certs):
                    if [c["objective_sign"] for c in certs] != [1, -1]:
                        raise ValueError("LP objective directions changed")
                    low = (base[1] + scale * bound_proof(a, b, certs[0])) * 86400 / w
                    high = (base[1] - scale * bound_proof(a, b, certs[1])) * 86400 / w
                    if record["derivative_interval_arcsec_per_TDB_day"] != list(
                        map(str, (low, high))
                    ):
                        raise ValueError("Derived interval changed")
                    certified += 2
                elif "derivative_interval_arcsec_per_TDB_day" in record:
                    raise ValueError("Unresolved interval promoted")
            valid = all(
                "derivative_interval_arcsec_per_TDB_day" in a for a in window["axes"]
            )
            if (
                window["status"]
                != (
                    "conditional_exact_polynomial_interval"
                    if valid
                    else "polynomial_reference_unresolved"
                )
                or window["physical_remainder_certified"]
            ):
                raise ValueError("Polynomial status or physical remainder promoted")
        checks = []
        selected = None
        for i in range(len(plan["windows_seconds"]) - 2):
            triple = plan["windows_seconds"][i : i + 3]
            rows = [
                next(
                    r
                    for r in fits["all_windows"]
                    if r["window_seconds"] == w and r["full_degree"] == d
                )
                for w in triple
                for d in (5, 7)
            ]
            complete = all(
                r["status"] == "conditional_exact_polynomial_interval" for r in rows
            )
            spread = radius = None
            if complete:
                bounds = [
                    [
                        tuple(map(Q, a["derivative_interval_arcsec_per_TDB_day"]))
                        for a in r["axes"]
                    ]
                    for r in rows
                ]
                mids = [[(a + b) / 2 for a, b in box] for box in bounds]
                spread = max(
                    sum(((a - b) ** 2 for a, b in zip(u, v)), Q())
                    for u, v in combinations(mids, 2)
                )
                radius = max(
                    sum((((b - a) / 2) ** 2 for a, b in box), Q()) for box in bounds
                )
            accepted = (
                complete and spread <= Q(1, 500) ** 2 and radius <= Q(1, 500) ** 2
            )
            checks.append(
                {
                    "windows_seconds": triple,
                    "complete_exact_certificates": complete,
                    "maximum_coordinate_midpoint_distance_squared": (
                        str(spread) if complete else None
                    ),
                    "maximum_coordinate_radius_squared": (
                        str(radius) if complete else None
                    ),
                    "conditional_quality_met": accepted,
                }
            )
            if accepted and selected is None:
                selected = {"window_seconds": triple[1], "full_degree": 7}
        expected_quality = {
            "status": (
                "conditional_quality_met"
                if selected
                else "reference_quality_unresolved"
            ),
            "selected": selected,
            "all_window_checks": checks,
            "fixed_line_arcsec_per_day": "0.002",
            "coordinate_norm_conservative_for_tangent_direction": True,
            "TDB_day_not_certified_TT_day": True,
            "production_reference_qualified": False,
        }
        if fits["quality"] != expected_quality:
            raise ValueError("Independent fixed-line quality check changed")
    return {
        "cohort": cohort,
        "primary_nodes": 577,
        "source_endpoint_checks": endpoints,
        "source_component_boxes": boxes,
        "exact_grid_points_checked": points,
        "qualified_clock_nodes": full_populations,
        "exact_LP_certificates_checked": certified,
        "OBSERVER_clock_certified": False,
        "physical_remainder_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", choices=("A", "B"), required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    value = verify(args.run, args.cohort)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
