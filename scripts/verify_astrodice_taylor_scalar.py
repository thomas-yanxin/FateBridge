"""Scalar 120-digit, exact-weight checks of source coefficients 5 and 7.

No high-order jet or candidate import. Agreement of two finite steps is an
empirical implementation check, not a rigorous physical remainder bound.
"""

import argparse
import json
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_apparent_source_reference import Reader, sample
from scripts.astrodice_de441_records import calendar_jd_tdb


def number(value):
    value = Q(value)
    return N(value.numerator) / N(value.denominator)


def weights(order):
    nodes = list(range(-7, 8))
    result = []
    for node in nodes:
        polynomial = [Q(1)]
        denominator = Q(1)
        for other in nodes:
            if other == node:
                continue
            product = [Q()] * (len(polynomial) + 1)
            for power, value in enumerate(polynomial):
                product[power] -= other * value
                product[power + 1] += value
            polynomial = product
            denominator *= node - other
        result.append(polynomial[order] / denominator)
    if any(
        sum((w * Q(x) ** power for x, w in zip(nodes, result)), Q())
        != int(power == order)
        for power in range(15)
    ):
        raise ValueError("Independent coefficient moment identity failed")
    return result


def atan(value):
    if abs(value) >= N(1) / 4:
        raise ValueError("Scalar relative angle outside fixed small domain")
    total = N(0)
    power = value
    for k in range(200):
        total += power / (2 * k + 1)
        power *= -value * value
    return total


def relative_angles(vector, center):
    x, y, z = vector
    a, b, c = center
    r = (x * x + y * y).sqrt()
    r0 = (a * a + b * b).sqrt()
    return [
        atan((a * y - b * x) / (a * x + b * y)),
        atan((z * r0 - c * r) / (z * c + r * r0)),
    ]


def verify(run, enclosures):
    plan = json.loads((run / "plan-before-high-order-evaluation.json").read_text())
    reference = json.loads(enclosures.read_text())
    if (
        plan["finite_difference_steps_days"] != ["1/4096", "1/8192"]
        or plan["finite_difference_nodes"] != list(range(-7, 8))
        or plan["independent_scalar_precision"] != 120
    ):
        raise ValueError("Fixed scalar validation plan changed")
    profile = json.loads((run / "source-solar-profile.json").read_text())[
        "radius_mass_pairs"
    ]
    rows = []
    with localcontext() as context:
        context.prec = 120
        pi = 16 * atan(N(1) / 5) - 4 * atan(N(1) / 239)
        factor = 648000 / pi
        for date, declared in zip(plan["cases"], reference["rows"]):
            if date != declared["date_tt"]:
                raise ValueError("Scalar condition identity changed")
            center = calendar_jd_tdb(date)
            reader = Reader(run / "source-records", 2)
            cache = {}

            def direction(offset):
                if offset not in cache:
                    value = sample(
                        reader, "Venus", center + offset, profile, precision=120, seed=0
                    )
                    cache[offset] = list(map(N, value["direction_icrf"]))
                return cache[offset]

            central = direction(Q())
            checks = []
            for axis in (0, 1):
                for order in (5, 7):
                    w = weights(order)
                    estimates = []
                    for step in plan["finite_difference_steps_days"]:
                        h = Q(step)
                        angles = [
                            relative_angles(direction(node * h), central)[axis]
                            for node in range(-7, 8)
                        ]
                        estimates.append(
                            sum(
                                (
                                    number(weight) * value
                                    for weight, value in zip(w, angles)
                                ),
                                N(),
                            )
                            * factor
                            / number(h**order)
                        )
                    record = declared["center_angular_coefficients_arcsec"][axis][
                        order - 1
                    ]
                    low, high = [
                        number(Q(int(record[key]), 2**256))
                        for key in ["lower_numerator", "upper_numerator"]
                    ]
                    spread = abs(estimates[0] - estimates[1])
                    floor = number(
                        plan[
                            "finite_difference_comparison_absolute_floor_arcsec_coefficient"
                        ]
                    )
                    limit = number(
                        plan["finite_difference_comparison_relative_step_line"]
                    ) * max(N(1), abs(estimates[1]))
                    radius = 2 * spread + floor
                    qualified = (
                        spread <= limit
                        and low <= estimates[1] + radius
                        and high >= estimates[1] - radius
                    )
                    checks.append(
                        {
                            "axis": axis,
                            "normalized_coefficient_order": order,
                            "scalar_step_estimates_arcsec": list(map(str, estimates)),
                            "step_difference": str(spread),
                            "fixed_relative_step_limit": str(limit),
                            "empirical_comparison_radius": str(radius),
                            "jet_center_lower": str(low),
                            "jet_center_upper": str(high),
                            "status": (
                                "independent_scalar_check_satisfied"
                                if qualified
                                else "independent_scalar_check_unresolved"
                            ),
                            "finite_difference_truncation_bound_certified": False,
                        }
                    )
            rows.append(
                {
                    "date_tt": date,
                    "checks": checks,
                    "distinct_source_position_probes": len(cache),
                }
            )
    if len(rows) != 3:
        raise ValueError("Complete scalar cohort required")
    code = (
        0
        if all(
            c["status"] == "independent_scalar_check_satisfied"
            for row in rows
            for c in row["checks"]
        )
        else 2
    )
    return {
        "method_id": "independent_scalar_high_order_source_coefficient_check_v1",
        "exit_code": code,
        "rows": rows,
        "high_order_jet_imported": False,
        "candidate_imported": False,
        "production_acceptance_exit_code": 2,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--enclosures", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.run, a.enclosures)
    with a.output.open("x") as h:
        json.dump(result, h, indent=2)
        h.write("\n")
    print("independent scalar check exit", result["exit_code"])
    raise SystemExit(result["exit_code"])
