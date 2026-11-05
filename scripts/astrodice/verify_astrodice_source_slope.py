"""Independent rational-box replay of stored source angular-rate bounds.

No producer, interval implementation, solver, Swiss or FateBridge import.
Stored decimal Clenshaw values cross-check the independently computed source
boxes at every original node. Finite checks do not certify physical models.
"""

import argparse
import json
import math
from datetime import datetime
from fractions import Fraction as Q
from pathlib import Path


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def neg(a):
    return -a[1], -a[0]


def sub(a, b):
    return add(a, neg(b))


def mul(a, b):
    values = [x * y for x in a for y in b]
    return min(values), max(values)


def square(a):
    return (Q() if a[0] <= 0 <= a[1] else min(x * x for x in a), max(x * x for x in a))


def div(a, b):
    if b[0] <= 0 <= b[1]:
        raise ValueError("Independent box denominator contains zero")
    return mul(a, (1 / b[1], 1 / b[0]))


def sqrt(a):
    if a[0] < 0:
        raise ValueError("Independent square root outside domain")
    scale = 10**100
    low = math.isqrt(a[0].numerator * scale * scale // a[0].denominator)
    high = math.isqrt(a[1].numerator * scale * scale // a[1].denominator)
    if Q(high * high, scale * scale) < a[1]:
        high += 1
    return Q(low, scale), Q(high, scale)


def pi():
    def atan(inverse, count):
        terms = [Q(1, (2 * n + 1) * inverse ** (2 * n + 1)) for n in range(count + 1)]
        total = sum((t if i % 2 == 0 else -t for i, t in enumerate(terms[:-1])), Q())
        extra = terms[-1] if count % 2 == 0 else -terms[-1]
        return min(total, total + extra), max(total, total + extra)

    return sub(mul((16, 16), atan(5, 64)), mul((4, 4), atan(239, 32)))


def box(record):
    if record["denominator_power_two"] != 256:
        raise ValueError("Declared source box precision changed")
    result = tuple(
        Q(int(record[key]), 2**256) for key in ["lower_numerator", "upper_numerator"]
    )
    if result[0] > result[1]:
        raise ValueError("Reversed stored source box")
    return result


def rates(position, derivative):
    x, y, z = position
    dx, dy, dz = derivative
    r2 = add(square(x), square(y))
    r = sqrt(r2)
    alpha = div(sub(mul(x, dy), mul(y, dx)), r2)
    dr = div(add(mul(x, dx), mul(y, dy)), r)
    delta = div(sub(mul(r, dz), mul(z, dr)), add(r2, square(z)))
    factor = div((Q(648000), Q(648000)), pi())
    return [max(abs(x) for x in mul(value, factor)) for value in [alpha, delta]]


def verify(folder):
    def load(name):
        return json.loads((folder / name).read_text())

    shape = load("shape-first.json")
    source = load("source-slope-first.json")
    plan = load("source-slope-plan-before-evaluation.json")
    if (
        plan["epoch_error_hypothesis_days"] != "1/1000000000"
        or plan["enlarge_each_segment_each_side_days"] != "1/1000000000"
        or plan["fixed_reference_line_arcsec_per_day"] != 0.002
        or plan["source_epoch_error_hypothesis_physically_certified"]
        or plan["source_Horizons_derivative_equivalence_certified"]
    ):
        raise ValueError("Original epoch or physical premises changed")
    if len(shape["rows"]) != len(source["rows"]) or len(source["rows"]) != 3:
        raise ValueError("Complete three-case source study required")
    checked_rates = checked_components = 0
    caps = []
    for point_row, row, date in zip(shape["rows"], source["rows"], plan["case_dates"]):
        if point_row["date_tt"] != row["date_tt"] or row["date_tt"] != date:
            raise ValueError("Source condition identity changed")
        if len(row["segments"]) != 576 or len(point_row["nodes"]) != 577:
            raise ValueError("Full grid and all segments required")
        if [v["offset_seconds"] for v in point_row["nodes"]] != list(
            range(-1440, 1441, 5)
        ):
            raise ValueError("Original node identity changed")
        instant = datetime.fromisoformat(date)
        center = (
            Q(instant.toordinal())
            + Q(3442849, 2)
            + Q(instant.hour * 3600 + instant.minute * 60 + instant.second, 86400)
        )
        margin = Q(1, 10**9)
        maximum = Q()
        for index, segment in enumerate(row["segments"]):
            if (
                segment["offset_seconds"] != -1440 + 5 * index
                or segment["status"] != "outward_source_slope_enclosure"
            ):
                raise ValueError("Source support was reduced")
            offset = segment["offset_seconds"]
            if (
                Q(segment["exact_lower_nominal_TDB"])
                != center + Q(offset, 86400) - margin
                or Q(segment["exact_upper_nominal_TDB"])
                != center + Q(offset + 5, 86400) + margin
            ):
                raise ValueError("Source interval lost its full declared time support")
            p, d = (
                list(map(box, segment["direction"])),
                list(map(box, segment["derivative"])),
            )
            expected = rates(p, d)
            declared = list(map(Q, segment["absolute_RA_DEC_bounds_arcsec_per_day"]))
            if any(a > b for a, b in zip(expected, declared)):
                raise ValueError(
                    "Independent angular-rate enclosure exceeds declaration"
                )
            checked_rates += 2
            maximum = max(maximum, *declared)
            for point in point_row["nodes"][index : index + 2]:
                if Q(point["exact_nominal_epoch"]) != center + Q(
                    point["offset_seconds"], 86400
                ):
                    raise ValueError("Source point epoch identity changed")
                for key, boxes in [
                    ("source_direction_icrf", p),
                    ("source_derivative_per_TDB_day", d),
                ]:
                    for value, bounds in zip(point[key], boxes):
                        if not bounds[0] <= Q(value) <= bounds[1]:
                            raise ValueError(
                                "Independent decimal source value escaped interval"
                            )
                        checked_components += 1
        cap = -(-maximum.numerator // maximum.denominator)
        if cap != row["scalar_cap_arcsec_per_day"]:
            raise ValueError("Scalar cap was not derived from whole support")
        caps.append(cap)
    if (
        source["actual_Horizons_epoch_error_bound_certified"]
        or source["source_Horizons_derivative_equivalence_certified"]
        or source["physical_ephemeris_slope_bound_certified"]
    ):
        raise ValueError("Source evidence was promoted to physical certification")
    return {
        "method_id": "independent_rational_box_source_slope_replay_v1",
        "angular_rate_boxes_checked": checked_rates,
        "decimal_component_containments_checked": checked_components,
        "derived_scalar_caps": caps,
        "producer_or_candidate_imported": False,
        "actual_epoch_bound_certified": False,
        "production_acceptance_exit_code": 2,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.folder)
    with a.output.open("x") as h:
        json.dump(result, h, indent=2)
        h.write("\n")
    print(json.dumps(result, indent=2))
