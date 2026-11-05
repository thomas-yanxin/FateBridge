"""Conditional full-polynomial reference on independently calibrated nodes.

Every point in a window remains a constraint. Nominal TT symmetry is never
assumed. This does not establish an OBSERVER/vector clock identity or physical
TT/TDB conversion; those missing premises prohibit production acceptance.
"""

import argparse
import csv
import json
import re
from decimal import Decimal
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path

from scripts.astrodice.astrodice_clock_interval import Reader
from scripts.astrodice.astrodice_earth_clock import diagnose, pair, parse
from scripts.astrodice.astrodice_emission_epoch import (
    epoch_from_coordinate,
    lattice_points,
)
from scripts.astrodice.astrodice_interval_reference import WINDOWS, solve, verify
from scripts.astrodice.astrodice_joint_epoch import exact_state
from scripts.astrodice.astrodice_vector_clock import check_inputs, save, sha, tube

DEGREES = (5, 7)


def observer_angles(raw, query, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Observer service error")
    pre, data = payload["result"].split("$$SOE")
    data, _ = data.split("$$EOE")
    for expression in [
        r"Target body name: Venus.*?\(299\).*?DE441",
        r"Center body name: Earth \(399\).*?DE441",
        r"Calendar mode\s*:\s*Gregorian",
        r"Date__\(TT\)",
        r"JDTT",
        r"RA_\(ICRF-a-app\)",
    ]:
        if not re.search(expression, pre):
            raise ValueError("Observer quantity/frame/time mismatch")
    output = {}
    for cells in csv.reader(data.strip().splitlines()):
        c = [x.strip() for x in cells]
        if len(c) != 7 or c[-1]:
            raise ValueError("Observer columns changed")
        epoch = Q(c[1])
        matches = [
            case
            for case in query["cases"]
            if abs(epoch - Q(case["nominal_JD"]))
            <= Q(plan["returned_label_match_budget_days"])
        ]
        if len(matches) != 1 or matches[0]["id"] in output:
            raise ValueError("Observer row outside original unique label budget")
        if not all(Decimal(v).is_finite() for v in c[4:6]):
            raise ValueError("Nonfinite observer angle")
        case = matches[0]
        output[case["id"]] = c[4:6]
    if set(output) != {c["id"] for c in query["cases"]}:
        raise ValueError("Observer population incomplete")
    return {
        str(c["offset_seconds"]): output[c["id"]]
        for c in query["cases"]
        if c["role"] != "auxiliary_not_primary"
    }


def interpolate(nodes, values):
    """Exact Lagrange coefficients in ascending powers, distinct rational nodes."""
    if len(nodes) != len(set(nodes)) or len(nodes) != len(values):
        raise ValueError("Missing or duplicate interpolation nodes")
    coefficients = [Q()] * len(nodes)
    for i, (x, value) in enumerate(zip(nodes, values)):
        polynomial, denominator = [Q(1)], Q(1)
        for j, y in enumerate(nodes):
            if i == j:
                continue
            denominator *= x - y
            new = [Q()] * (len(polynomial) + 1)
            for k, c in enumerate(polynomial):
                new[k] -= y * c
                new[k + 1] += c
            polynomial = new
        for k, c in enumerate(polynomial):
            coefficients[k] += value * c / denominator
    return coefficients


def polynomial(coefficients, x):
    value = Q()
    for c in reversed(coefficients):
        value = value * x + c
    return value


def system(angles, epochs, window, degree, axis):
    if degree not in DEGREES or window not in WINDOWS or axis not in (0, 1):
        raise ValueError("Unplanned nonuniform polynomial")
    offsets = sorted(o for o in angles if abs(o) <= window)
    if offsets != list(range(-window, window + 1, 5)) or set(epochs) != set(angles):
        raise ValueError("Full original five-second population required")
    center = Q(angles[0][axis])
    nodes = [(epochs[o] - epochs[0]) / window for o in offsets]
    if any(a >= b for a, b in zip(nodes, nodes[1:])):
        raise ValueError("Nonincreasing calibrated nodes")
    values, noise = [], []
    for o in offsets:
        value = Q(angles[o][axis])
        if axis == 0:
            value -= 360 * ((value - center + 180) // 360)
        values.append((value - center) * 3600)
        noise.append(Q(10) ** Decimal(angles[o][axis]).as_tuple().exponent * 3600)
    # Geometry-only equally ranked anchors, never selected using residuals.
    anchors = [k * (len(nodes) - 1) // degree for k in range(degree + 1)]
    baseline = interpolate([nodes[k] for k in anchors], [values[k] for k in anchors])
    scale = max(noise)
    matrix, bounds = [], []
    for x, y, error in zip(nodes, values, noise):
        powers = [x**p for p in range(degree + 1)]
        residual = (y - polynomial(baseline, x)) / scale
        matrix.extend([powers, [-v for v in powers]])
        bounds.extend([residual + error / scale, -residual + error / scale])
    return matrix, bounds, baseline, scale


def certified_derivative(a, b, sign):
    """Numerical proposal, exact rational primal/dual acceptance; bounded search."""
    from scipy.optimize import linprog

    n = len(a[0])
    # Rotate the linear coefficient to the old verifier's objective column 0.
    permutation = [1, 0, *range(2, n)]
    matrix = [[row[k] for k in permutation] for row in a]
    result = linprog(
        [sign] + [0] * (n - 1),
        A_ub=[[float(v) for v in row] for row in matrix],
        b_ub=[float(v) for v in b],
        bounds=[(None, None)] * n,
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        },
    )
    if not result.success:
        return {
            "status": "solver_unresolved",
            "solver_status": result.status,
            "message": result.message,
        }
    marginal = sorted(
        range(len(a)), key=lambda i: abs(result.ineqlin.marginals[i]), reverse=True
    )
    residual = sorted(range(len(a)), key=lambda i: abs(result.ineqlin.residual[i]))
    proposed = [tuple(marginal[:n]), tuple(residual[:n])]
    proposed += list(combinations(marginal[: n + 1], n))
    proposed += list(combinations(residual[: n + 1], n))
    objective = [Q(sign)] + [Q()] * (n - 1)
    for active in dict.fromkeys(proposed):
        selected = [matrix[i] for i in active]
        try:
            primal = solve(selected, [b[i] for i in active])
            dual = solve(list(map(list, zip(*selected))), objective)
        except ValueError:
            continue
        certificate = {
            "status": "exact_primal_dual_optimum",
            "objective_sign": sign,
            "active": list(active),
            "primal": list(map(str, primal)),
            "dual": list(map(str, dual)),
            "optimum": str(sign * primal[0]),
        }
        try:
            verify(matrix, b, certificate)
        except ValueError:
            continue
        return certificate
    return {
        "status": "exact_certificate_not_found",
        "solver_status": result.status,
        "candidate_bases": len(dict.fromkeys(proposed)),
    }


def fit(angles, epochs, window, degree):
    axes = []
    for axis in (0, 1):
        a, b, baseline, scale = system(angles, epochs, window, degree, axis)
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


def quality(fits):
    lookup = {(v["window_seconds"], v["full_degree"]): v for v in fits}
    if set(lookup) != {(w, d) for w in WINDOWS for d in DEGREES} or len(fits) != len(
        lookup
    ):
        raise ValueError("All fixed windows and degrees are required")
    checks = []
    selected = None
    for i in range(len(WINDOWS) - 2):
        triple = WINDOWS[i : i + 3]
        rows = [lookup[w, d] for w in triple for d in DEGREES]
        complete = all(
            r["status"] == "conditional_exact_polynomial_interval" for r in rows
        )
        spread = radius = None
        if complete:
            boxes = [
                [
                    tuple(map(Q, a["derivative_interval_arcsec_per_TDB_day"]))
                    for a in r["axes"]
                ]
                for r in rows
            ]
            midpoints = [[(a + b) / 2 for a, b in box] for box in boxes]
            spread = max(
                sum(((a - b) ** 2 for a, b in zip(u, v)), Q())
                for u, v in combinations(midpoints, 2)
            )
            radius = max(
                sum((((b - a) / 2) ** 2 for a, b in box), Q()) for box in boxes
            )
        accepted = complete and spread <= Q("0.002") ** 2 and radius <= Q("0.002") ** 2
        checks.append(
            {
                "windows_seconds": list(triple),
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
    return {
        "status": (
            "conditional_quality_met" if selected else "reference_quality_unresolved"
        ),
        "selected": selected,
        "all_window_checks": checks,
        "fixed_line_arcsec_per_day": "0.002",
        "coordinate_norm_conservative_for_tangent_direction": True,
        "TDB_day_not_certified_TT_day": True,
        "production_reference_qualified": False,
    }


def qualify_grid(source, case, row, body, inverse, profile, plan):
    if inverse["status"] != "bracketed":
        return {
            "status": "inverse_unknown",
            "grid_hex": [],
            "six_component_matches": [],
        }
    a, b = map(Q, inverse["effective_JD"])
    grid = lattice_points((a - 2451545) * 86400, (b - 2451545) * 86400, 4096)
    matches = []
    if grid["status"] == "complete":
        for value in grid["points"]:
            epoch = epoch_from_coordinate(value, "seconds_from_J2000_binary64")
            state = exact_state(source, case["window_index"], epoch, body)
            bounds = [
                tube(v, plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"])
                for v in row["printed_state"]
            ]
            if all(a <= v <= b for v, (a, b) in zip(state, bounds)):
                matches.append(value.hex())
    return {
        "status": grid["status"],
        "grid_hex": [p.hex() for p in grid["points"]],
        "six_component_matches": matches,
    }


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    result = {
        "cohort": cohort,
        "plan_sha256": digest,
        "queries": [],
        "clock_population": {},
        "fits": {},
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "OBSERVER_vector_clock_identity_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    indexed = {}
    for q in plan["queries"]:
        if q["cohort"] != cohort or q["kind"] != "geometry":
            continue
        raw = (run / "responses" / (q["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (q["id"] + ".receipt.json")).read_text()
        )
        if receipt["status"] != 200 or sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Unavailable or changed source calibration")
        records = []
        for row in parse(raw, q, q["cases"], plan):
            if row["role"] == "auxiliary_not_primary":
                continue
            case = next(c for c in q["cases"] if c["id"] == row["case_id"])
            saved = diagnose(run / "source-records", case, row, q["body"], plan)
            saved["grid"] = {
                p: qualify_grid(
                    run / "source-records", case, row, q["body"], inv, p, plan
                )
                for p, inv in saved["profiles"].items()
            }
            records.append(saved)
            indexed[q["body"], case["offset_seconds"]] = (case, saved)
        result["queries"].append({"id": q["id"], "body": q["body"], "rows": records})
        print("analyzed", q["id"], len(records), flush=True)
    angles = json.loads((run / (cohort + "-angles.json")).read_text())
    angles = {int(k): v for k, v in angles.items()}
    for profile in plan["numerical_tube_profiles"]:
        epochs, statuses = {}, []
        for offset in range(-1440, 1441, 5):
            case, earth = indexed["Earth", offset]
            _, venus = indexed["Venus", offset]
            eg, vg = earth["grid"][profile], venus["grid"][profile]
            common = sorted(
                set(eg["six_component_matches"]) & set(vg["six_component_matches"])
            )
            joint = pair(
                Reader(run / "source-records", case["window_index"]),
                earth,
                venus,
                profile,
                plan,
            )
            qualified = (
                len(common) == 1
                and earth["original_label_budget_pass"]
                and venus["original_label_budget_pass"]
                and joint.get("joint_necessary_not_refuted", False)
            )
            statuses.append(
                {
                    "offset_seconds": offset,
                    "common_ET_hex": common,
                    "qualified": qualified,
                }
            )
            if qualified:
                epochs[offset] = Q(float.fromhex(common[0]))
        result["clock_population"][profile] = statuses
        if len(epochs) != 577:
            result["fits"][profile] = {
                "status": "full_clock_population_unqualified",
                "qualified_nodes": len(epochs),
                "required_nodes": 577,
            }
            continue
        fitted = [
            fit(angles, epochs, window, degree)
            for window in WINDOWS
            for degree in DEGREES
        ]
        result["fits"][profile] = {
            "status": "conditional_diagnostic_only",
            "all_windows": fitted,
            "quality": quality(fitted),
            "original_odd_polynomial_acceptance_replaced": False,
            "TT_derivative_certified": False,
            "OBSERVER_clock_certified": False,
        }
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    save(args.output, analyze(args.run, args.cohort))


if __name__ == "__main__":
    main()
