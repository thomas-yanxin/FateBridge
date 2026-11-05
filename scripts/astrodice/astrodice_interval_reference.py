"""Local printed-angle intervals with independently replayable LP witnesses.

SciPy is only an optional maintenance solver. Acceptance replays exact rational
primal/dual certificates. Polynomial suitability remains an empirical check;
these certificates do not prove that a physical ephemeris is polynomial.
"""

import math
from fractions import Fraction as F
from itertools import combinations

GRID_METHODS = {
    "local_printed_angle_interval_lp_v1": 10,
    "local_printed_angle_interval_lp_grid5_v2": 5,
}


def checked_grid(step_seconds):
    if type(step_seconds) is not int or step_seconds not in (5, 10):
        raise ValueError("Unplanned local reference grid")
    return step_seconds


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), F(0))


def solve(matrix, values):
    n = len(values)
    a = [[F(x) for x in row] + [F(v)] for row, v in zip(matrix, values)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if a[i][col]), None)
        if pivot is None:
            raise ValueError("singular")
        a[col], a[pivot] = a[pivot], a[col]
        factor = a[col][col]
        a[col] = [v / factor for v in a[col]]
        for i in range(n):
            if i != col:
                f = a[i][col]
                a[i] = [v - f * u for v, u in zip(a[i], a[col])]
    return [row[-1] for row in a]


def system(row, points, window, order, axis, *, step_seconds=10):
    step = checked_grid(step_seconds)
    if window not in WINDOWS or order not in ORDERS or axis not in (0, 1):
        raise ValueError("Unplanned local reference geometry")
    offsets = list(range(step, window + 1, step))
    center = F(row["samples"]["0"]["printed_angles"][axis])

    def angle(t):
        value = F(row["samples"][str(t)]["printed_angles"][axis])
        if axis == 0:
            value -= 360 * ((value - center + 180) // 360)
        return value

    from decimal import Decimal

    def noise(t):
        value = Decimal(row["samples"][str(t)]["printed_angles"][axis])
        return F(Decimal(10) ** value.as_tuple().exponent) * 3600

    # One full last digit: conservative across nearest/truncation conventions.
    values = {t: (angle(t) - angle(-t)) * 1800 for t in offsets}
    baseline = values[window]
    scale = max((noise(t) + noise(-t)) / 2 for t in offsets)
    rows = []
    bounds = []
    for t in offsets:
        x = F(t, window)
        coeff = [x**p for p in range(1, order + 1, 2)]
        y = (values[t] - baseline * x) / scale
        e = (noise(t) + noise(-t)) / 2 / scale
        rows.extend([coeff, [-v for v in coeff]])
        bounds.extend([y + e, -y + e])
    return rows, bounds, baseline, scale


def certified_bound(a, b, sign):
    from scipy.optimize import linprog

    n = len(a[0])
    objective = [F(sign)] + [F(0)] * (n - 1)
    result = linprog(
        [float(v) for v in objective],
        A_ub=[[float(v) for v in row] for row in a],
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
    indices = sorted(range(len(a)), key=lambda i: abs(result.ineqlin.residual[i]))[
        : min(12, len(a))
    ]
    for active in combinations(indices, n):
        selected = [a[i] for i in active]
        rhs = [b[i] for i in active]
        try:
            primal = solve(selected, rhs)
            dual = solve(list(map(list, zip(*selected))), objective)
        except ValueError:
            continue
        if any(v > 0 for v in dual) or any(
            dot(row, primal) > bound for row, bound in zip(a, b)
        ):
            continue
        optimum = dot(objective, primal)
        if optimum != dot(dual, rhs):
            continue
        return {
            "status": "exact_primal_dual_optimum",
            "objective_sign": sign,
            "active": list(active),
            "primal": list(map(str, primal)),
            "dual": list(map(str, dual)),
            "optimum": str(optimum),
        }
    return {"status": "exact_certificate_not_found", "solver_status": result.status}


def verify(a, b, certificate):
    n = len(a[0])
    sign = certificate["objective_sign"]
    if sign not in [-1, 1] or certificate["status"] != "exact_primal_dual_optimum":
        raise ValueError("Invalid certificate objective/status")
    active = certificate["active"]
    primal = list(map(F, certificate["primal"]))
    dual = list(map(F, certificate["dual"]))
    if (
        not (len(active) == len(primal) == len(dual) == n)
        or len(set(active)) != n
        or any(type(i) is not int or not 0 <= i < len(a) for i in active)
    ):
        raise ValueError("Invalid certificate dimensions or basis")
    if any(v > 0 for v in dual) or any(
        dot(row, primal) > bound for row, bound in zip(a, b)
    ):
        raise ValueError("Certificate is not primal/dual feasible")
    if not all(
        sum((dual[k] * a[i][j] for k, i in enumerate(active)), F(0))
        == int(j == 0) * sign
        for j in range(n)
    ):
        raise ValueError("Certificate dual identity failed")
    optimum = dot([F(sign)] + [F(0)] * (n - 1), primal)
    if not (
        optimum
        == F(certificate["optimum"])
        == sum((v * b[i] for v, i in zip(dual, active)), F(0))
    ):
        raise ValueError("Certificate exact objective equality failed")
    return optimum


def interval(row, points, window, order, *, step_seconds=10):
    checked_grid(step_seconds)
    grid = {"grid_step_seconds": step_seconds} if step_seconds != 10 else {}
    axes = []
    for axis in range(2):
        a, b, baseline, scale = system(
            row, points, window, order, axis, step_seconds=step_seconds
        )
        certs = [certified_bound(a, b, sign) for sign in [1, -1]]
        if any(v["status"] != "exact_primal_dual_optimum" for v in certs):
            return {"status": "unresolved", "axis": axis, "results": certs, **grid}
        lower = (baseline + scale * verify(a, b, certs[0])) * F(86400, window)
        upper = (baseline - scale * verify(a, b, certs[1])) * F(86400, window)
        axes.append(
            {
                "lower_arcsec_per_day": str(lower),
                "upper_arcsec_per_day": str(upper),
                "certificates": certs,
            }
        )
    radius = math.nextafter(
        math.hypot(
            *[
                float((F(v["upper_arcsec_per_day"]) - F(v["lower_arcsec_per_day"])) / 2)
                for v in axes
            ]
        ),
        math.inf,
    )
    return {
        **grid,
        "status": "exact_angular_interval_under_odd_polynomial_assumption",
        "window_seconds": window,
        "odd_order": order,
        "axes": axes,
        "midpoint_arcsec_per_day": [
            float((F(v["upper_arcsec_per_day"]) + F(v["lower_arcsec_per_day"])) / 2)
            for v in axes
        ],
        "angular_box_radius_arcsec_per_day": radius,
        "scope": "Bounds are exact for the declared localoddpolynomial androundingintervalconstraints;theactualJPLfunctionisnotprovedpolynomial.",
    }


def windows():
    result = []
    value = 1440
    while value >= 60:
        result.append(value)
        value = (3 * value // 4) // 10 * 10
    return tuple(result)


WINDOWS = windows()
ORDERS = (3, 5)
LINE = 0.002


def replay_interval(row, record, *, step_seconds=10):
    checked_grid(step_seconds)
    if record.get("grid_step_seconds", 10) != step_seconds:
        raise ValueError("Certificate reference grid changed")
    window, order = record["window_seconds"], record["odd_order"]
    if window not in WINDOWS or order not in ORDERS:
        raise ValueError("Unplanned local reference geometry")
    axes = []
    for axis, declared in enumerate(record["axes"]):
        a, b, baseline, scale = system(
            row, None, window, order, axis, step_seconds=step_seconds
        )
        certificates = declared["certificates"]
        if [v["objective_sign"] for v in certificates] != [1, -1]:
            raise ValueError("Certificate objective changed")
        low = (baseline + scale * verify(a, b, certificates[0])) * F(86400, window)
        high = (baseline - scale * verify(a, b, certificates[1])) * F(86400, window)
        if (
            low > high
            or str(low) != declared["lower_arcsec_per_day"]
            or str(high) != declared["upper_arcsec_per_day"]
        ):
            raise ValueError(
                "Declared derivative interval differs from exact witnesses"
            )
        axes.append((low, high))
    if len(axes) != 2:
        raise ValueError("Incomplete angular derivative")
    return axes


def tangent_geometry(row):
    from scripts.astrodice.astrodice_reference_math import sine_cosine

    center = row["samples"]["0"]
    alpha, delta = [math.radians(float(v)) for v in center["printed_angles"]]
    sa, ca = map(float, sine_cosine(alpha))
    sd, cd = map(float, sine_cosine(delta))
    direction = [cd * ca, cd * sa, sd]
    alpha_axis = [-cd * sa, cd * ca, 0.0]
    delta_axis = [-sd * ca, -sd * sa, cd]
    from decimal import Decimal

    center_noise = (
        math.radians(
            sum(
                float(Decimal(10) ** Decimal(v).as_tuple().exponent)
                for v in center["printed_angles"]
            )
        )
        + 8e-15
    )
    return direction, alpha_axis, delta_axis, center_noise


def vector_summary(row, axes):
    center, pa, pd, center_noise = tangent_geometry(row)
    mid = [float((low + high) / 2) for low, high in axes]
    radius = [float((high - low) / 2) for low, high in axes]
    derivative = [a * mid[0] + b * mid[1] for a, b in zip(pa, pd)]
    rounding = math.nextafter(
        math.hypot(math.hypot(*pa) * radius[0], radius[1])
        + center_noise * sum(abs(v) for v in mid)
        + 1e-9,
        math.inf,
    )
    return {
        "derivative_arcsec_per_day": derivative,
        "radius_arcsec_per_day": rounding,
        "angular_midpoint_arcsec_per_day": mid,
        "angular_half_widths_arcsec_per_day": radius,
    }


def quality(row, fits, *, step_seconds=10):
    # The solver may fail, but a numerical solver status is never a proof of
    # infeasibility. Such records are retained and make that support unusable.
    checked_grid(step_seconds)
    grid = {"grid_step_seconds": step_seconds} if step_seconds != 10 else {}
    if set(row["samples"]) != set(map(str, range(-1440, 1441, step_seconds))):
        raise ValueError("Local reference probe plan changed")
    missing = [s for s, v in row["samples"].items() if v is None]
    if missing:
        if fits:
            raise ValueError("Unavailable reference must not invent local fits")
        return {
            **grid,
            "status": "reference_unavailable",
            "missing_offsets_seconds": missing,
            "fixed_line_arcsec_per_day": LINE,
            "candidate_output_used_for_selection": False,
        }
    expected = {(w, o) for w in WINDOWS for o in ORDERS}
    actual = {(r.get("window_seconds"), r.get("odd_order")) for r in fits}
    if actual != expected or len(fits) != len(expected):
        raise ValueError("Local reference fit plan changed")
    summaries = {}
    for record in fits:
        if record.get("grid_step_seconds", 10) != step_seconds:
            raise ValueError("Certificate reference grid changed")
        key = (record["window_seconds"], record["odd_order"])
        if record["status"] == "exact_angular_interval_under_odd_polynomial_assumption":
            summaries[key] = vector_summary(
                row, replay_interval(row, record, step_seconds=step_seconds)
            )
    checks = []
    selected = None
    for i in range(len(WINDOWS) - 2):
        triple = WINDOWS[i : i + 3]
        keys = [(w, o) for w in triple for o in ORDERS]
        available = all(k in summaries for k in keys)
        spread = (
            max(
                (
                    math.dist(
                        summaries[a]["derivative_arcsec_per_day"],
                        summaries[b]["derivative_arcsec_per_day"],
                    )
                    for a, b in combinations(keys, 2)
                ),
                default=0,
            )
            if available
            else None
        )
        radius = (
            max(summaries[k]["radius_arcsec_per_day"] for k in keys)
            if available
            else None
        )
        accepted = available and spread <= LINE and radius <= LINE
        checks.append(
            {
                "windows_seconds": list(triple),
                "complete_exact_certificates": available,
                "maximum_midpoint_difference_arcsec_per_day": spread,
                "maximum_rounding_radius_arcsec_per_day": radius,
                "qualified": accepted,
            }
        )
        if accepted and selected is None:
            selected = (triple[1], 5)
    return {
        **grid,
        "status": (
            "qualified_under_declared_numerical_model"
            if selected
            else "reference_quality_unresolved"
        ),
        "selected_window_seconds": selected[0] if selected else None,
        "selected_order": 5 if selected else None,
        "selected": summaries[selected] if selected else None,
        "all_window_checks": checks,
        "fixed_line_arcsec_per_day": LINE,
        "candidate_output_used_for_selection": False,
        "scope": "Exact printing-interval LP witnesses plus empirical cross-window/order agreement;not a proof of physical/model truncation error.",
    }


def solve_row(row, *, step_seconds=10):
    checked_grid(step_seconds)
    fits = []
    if any(v is None for v in row["samples"].values()):
        return {
            "id": row["id"],
            "fits": fits,
            "quality": quality(row, fits, step_seconds=step_seconds),
        }
    for window in WINDOWS:
        for order in ORDERS:
            record = interval(row, None, window, order, step_seconds=step_seconds)
            record.update(window_seconds=window, odd_order=order)
            fits.append(record)
    return {
        "id": row["id"],
        "fits": fits,
        "quality": quality(row, fits, step_seconds=step_seconds),
    }
