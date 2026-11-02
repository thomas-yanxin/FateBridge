"""Candidate-independent, bounded multiscale quality checks for TT directions.

All five supports and three orders are planned before collection. Agreement
is an empirical reference-quality check, not a proof of truncation error or
physical truth. Every rejected support remains in the returned evidence.
"""

import math
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from itertools import combinations

from scripts.astrodice_reference_math import precise_direction

STEPS = (10800, 5400, 2700, 1350, 675)
ORDERS = (8, 10, 12)
LINE = 0.002
ARITHMETIC_ALLOWANCE_RADIANS = 8e-15


@lru_cache(None)
def weights(order):
    if order not in ORDERS:
        raise ValueError("Unplanned reference order")
    n = order // 2
    nodes = list(range(-n, n + 1))
    a = [[Fraction(x**p) for x in nodes] + [Fraction(p == 1)] for p in range(order + 1)]
    for col in range(order + 1):
        pivot = next(i for i in range(col, order + 1) if a[i][col])
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        a[col] = [v / divisor for v in a[col]]
        for row in range(order + 1):
            if row != col:
                factor = a[row][col]
                a[row] = [v - factor * u for v, u in zip(a[row], a[col])]
    answer = dict(zip(nodes, (row[-1] for row in a)))
    if any(
        sum(answer[k] * k**p for k in nodes) != int(p == 1) for p in range(order + 1)
    ):
        raise ValueError("Reference moment proof failed")
    return answer


def printed_direction_noise(point):
    # RA and DEC angular perturbations each bound their unit-vector change.
    half_units = []
    for value in point["printed_angles"]:
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("Nonfinite printed reference angle")
        half_units.append(float(Decimal(10) ** number.as_tuple().exponent) / 2)
    if len(half_units) != 2:
        raise ValueError("Invalid printed-angle shape")
    return math.radians(sum(half_units)) + ARITHMETIC_ALLOWANCE_RADIANS


def portable_points(row):
    return {
        offset: [float(x) for x in precise_direction(p["ra_degrees"], p["dec_degrees"])]
        for offset, p in row["samples"].items()
        if p is not None
    }


def estimate(points, h, order):
    w = weights(order)
    return [
        math.fsum(
            float(w[k]) * (points[str(k * h)][axis] - points[str(-k * h)][axis])
            for k in range(1, order // 2 + 1)
        )
        * 86400
        / h
        for axis in range(len(points["0"]))
    ]


def quality(row, points=None, selected_step=None, longitude=False):
    expected = {str(k * h) for h in STEPS for k in range(-6, 7)}
    if set(row["samples"]) != expected:
        raise ValueError("Reference refinement node plan changed")
    missing = [o for o in sorted(expected, key=int) if row["samples"][o] is None]
    if missing:
        return {"status": "reference_unavailable", "missing_offsets": missing}
    points = portable_points(row) if points is None else points
    if set(points) != expected or any(
        len(p) != 3 or not all(math.isfinite(x) for x in p) for p in points.values()
    ):
        raise ValueError("Invalid refinement directions")
    node_noise = {o: printed_direction_noise(p) for o, p in row["samples"].items()}
    if longitude:
        center = math.atan2(points["0"][1], points["0"][0])
        local = {}
        for o, p in points.items():
            rho = math.hypot(p[0], p[1])
            if rho < 0.01:
                raise ValueError("Ill-conditioned reference longitude")
            value = math.remainder(math.atan2(p[1], p[0]) - center, 2 * math.pi)
            if abs(value) >= math.pi / 2:
                raise ValueError("Reference longitude branch is not local")
            local[o] = [value]
            node_noise[o] /= rho
        points = local
    estimates = {}
    for h in STEPS:
        for order in ORDERS:
            w = weights(order)
            noise = (
                math.fsum(
                    abs(float(weight)) * node_noise[str(k * h)]
                    for k, weight in w.items()
                )
                * 86400
                / h
            )
            estimates[f"{h}:{order}"] = {
                "derivative_per_day": estimate(points, h, order),
                "printing_noise_bound_arcsec_per_day": math.degrees(noise) * 3600,
            }
    checks = []
    chosen = None
    for i in range(len(STEPS) - 2):
        triple = STEPS[i : i + 3]
        values = [estimates[f"{h}:{order}"] for h in triple for order in ORDERS]
        spread = max(
            math.degrees(math.dist(a["derivative_per_day"], b["derivative_per_day"]))
            * 3600
            for a, b in combinations(values, 2)
        )
        noise = max(v["printing_noise_bound_arcsec_per_day"] for v in values)
        accepted = spread <= LINE and noise <= LINE
        checks.append(
            {
                "steps_seconds": list(triple),
                "maximum_pairwise_difference_arcsec_per_day": spread,
                "maximum_printing_noise_bound_arcsec_per_day": noise,
                "qualified": accepted,
            }
        )
        if (
            accepted
            and chosen is None
            and (selected_step is None or selected_step == triple[1])
        ):
            chosen = triple[1]
    result = {
        "status": "qualified" if chosen is not None else "reference_quality_unresolved",
        "selected_step_seconds": chosen,
        "selected_order": 12 if chosen is not None else None,
        "all_estimates": estimates,
        "all_triplet_checks": checks,
        "fixed_convergence_line_arcsec_per_day": LINE,
        "candidate_output_used_for_selection": False,
    }
    if chosen is not None:
        result["selected_derivative_per_day"] = estimates[f"{chosen}:12"][
            "derivative_per_day"
        ]
    return result
