"""Independent radius-inverse, angular-cone and rounded-delay certificates.

Imports no radius-clock producer, its parser, interval AD, or Clenshaw evaluator.
The source, scalar rounding tubes and clock hypotheses remain explicit premises.
"""

import argparse
import csv
import hashlib
import json
import math
import re
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_earth_clock import raw_rows, vector_proof, wire
from scripts.verify_astrodice_emission_epoch import cell, enumerate_bits, from_raw
from scripts.verify_astrodice_joint_epoch import exact_state
from scripts.verify_astrodice_observer_clock import (
    Source,
    add,
    cover,
    divide,
    independent_pi,
    mul,
    neg,
    parse,
    root,
    rounded,
    sub,
)
from scripts.verify_astrodice_vector_clock import observed_bounds

K = Q(149597870700, 299792458 * 86400)
MODELS = ("absolute_JD_binary64", "seconds_from_J2000_binary64")
HYPOTHESES = ("one_round_source_norm", "two_round_source_norm")


def scalar_sqrt_compare(square, value):
    if value < 0:
        return 1
    v = square - value * value
    return (v > 0) - (v < 0)


def sqrt_membership(square, low, high, closed=True):
    a, b = scalar_sqrt_compare(square, low), scalar_sqrt_compare(square, high)
    return (a > 0 or a == 0 and closed) and (b < 0 or b == 0 and closed)


def sine_cosine(value):
    x = mul(rounded(value / 180), rounded(*independent_pi()))
    sine, cosine = rounded(0), rounded(0)
    st, ct = x, rounded(1)
    minus_square = neg(mul(x, x))
    for k in range(80):
        if k:
            st = divide(mul(st, minus_square), rounded((2 * k) * (2 * k + 1)))
            ct = divide(mul(ct, minus_square), rounded((2 * k - 1) * (2 * k)))
        sine, cosine = add(sine, st), add(cosine, ct)
    a = Q(7) ** 161 / math.factorial(161)
    b = Q(7) ** 160 / math.factorial(160)
    return add(sine, rounded(-a, a)), add(cosine, rounded(-b, b))


def angular_proof(state, angles, ulps, saved):
    ra = Q(angles[0])
    low, high = observed_bounds(angles[0], ulps)
    shift = 360 if ra >= 180 else 0
    sl, cl = sine_cosine(low - shift)
    su, cu = sine_cosine(high - shift)
    sm, cm = sine_cosine(ra - shift)
    x, y, z = [rounded(v) for v in state[:3]]
    square = sum((v * v for v in state[:3]), Q())
    dl, du = observed_bounds(angles[1], ulps)
    ls, _ = sine_cosine(dl)
    us, _ = sine_cosine(du)
    actual = {
        "RA_lower_cross": sub(mul(cl, y), mul(sl, x)),
        "RA_upper_cross": sub(mul(cu, y), mul(su, x)),
        "RA_front_dot": add(mul(cm, x), mul(sm, y)),
        "DEC_sine": divide(z, root(rounded(square))),
        "DEC_lower_sine": ls,
        "DEC_upper_sine": us,
    }
    if set(saved["bounds"]) != set(actual):
        raise ValueError("Angular certificate component dropped")
    for key, value in actual.items():
        cover(value, saved["bounds"][key])
    lower, upper, front = [
        parse(saved["bounds"][k])
        for k in ["RA_lower_cross", "RA_upper_cross", "RA_front_dot"]
    ]
    dec, lo, hi = [
        parse(saved["bounds"][k])
        for k in ["DEC_sine", "DEC_lower_sine", "DEC_upper_sine"]
    ]
    inside = (
        lower[0] >= 0
        and upper[1] <= 0
        and front[0] > 0
        and dec[0] >= lo[1]
        and dec[1] <= hi[0]
    )
    refuted = (
        lower[1] < 0
        or upper[0] > 0
        or front[1] <= 0
        or dec[1] < lo[0]
        or dec[0] > hi[1]
    )
    if (
        saved["status"]
        != ("proved_inside" if inside else "refuted" if refuted else "boundary_unknown")
        or saved["sufficient_angular_membership_proved"] != inside
    ):
        raise ValueError("Angular inclusion predicate changed")
    return inside


def rows(raw, query, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("OBSERVER service error")
    prefix, data = payload["result"].split("$$SOE")
    data, _ = data.split("$$EOE")
    for expression in [
        r"Target body name: Earth.*?\(399\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Calendar mode\s*:\s*Gregorian",
        r"Date__\(TT\)",
        r"JDTT",
        r"R\.A\._+\(ICRF\)",
        r"RA_\(ICRF-a-app\)",
        r"1-way_down_LT",
        r"delta,\s*deldot",
    ]:
        if not re.search(expression, prefix):
            raise ValueError("Independent OBSERVER source/origin/time mismatch")
    output = []
    seen = set()
    for row in csv.reader(data.strip().splitlines()):
        c = [v.strip() for v in row]
        if len(c) != 12 or c[-1]:
            raise ValueError("Independent quantity columns mismatch")
        matches = [
            case
            for case in query["cases"]
            if abs(Q(c[1]) - Q(case["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(matches) != 1 or matches[0]["id"] in seen:
            raise ValueError("Observer population identity mismatch")
        case = matches[0]
        seen.add(case["id"])
        output.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD_TT": case["nominal_JD"],
                "printed_JD_TT": c[1],
                "printed_calendar": c[0],
                "astrometric_angles": c[4:6],
                "range_AU": c[6],
                "radial_km_per_second": c[7],
                "light_time_minutes": c[8],
                "apparent_angles": c[9:11],
                "original_label_budget_pass": abs(Q(c[1]) - Q(case["nominal_JD"]))
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in query["cases"]}:
        raise ValueError("Observer cases reduced")
    return output


def radius_derivative(source, window, support):
    left, right = support
    reader = Source(source, window)
    parts = []
    for k in range(16):
        a = left + (right - left) * k / 16
        b = left + (right - left) * (k + 1) / 16
        state = reader.state(rounded(a, b, scale=1 << 256), "Earth")
        value = rounded(0)
        for p, v in zip(state[:3], state[3:]):
            value = add(value, mul(rounded(2), mul(p, v)))
        parts.append(value)
    return min(a for a, b in parts), max(b for a, b in parts)


def radius_square(source, window, t):
    return sum((v * v for v in exact_state(source, window, t, "Earth")[:3]), Q())


def check_candidate(run, case, row, profile, family, te, saved, plan):
    epoch = from_raw(te, family)
    state = exact_state(run / "source-records", case["window_index"], epoch, "Earth")
    square = sum(v * v for v in state[:3])
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    if (
        saved["emission_hex"] != te.hex()
        or Q(saved["emission_JD_TDB"]) != epoch
        or list(map(Q, saved["source_state_AU_and_AU_per_day"])) != state
        or Q(saved["source_radius_squared_AU2"]) != square
    ):
        raise ValueError("Independent emission state differs")
    angle = angular_proof(state, row["astrometric_angles"], ulps, saved["angle_proof"])
    rg = sqrt_membership(square, *observed_bounds(row["range_AU"], ulps))
    lt = sqrt_membership(
        square * (K * 1440) ** 2, *observed_bounds(row["light_time_minutes"], ulps)
    )
    scale = Q(1 if family == "absolute_JD_binary64" else 86400)
    light_square = square * (K * scale) ** 2
    if Q(saved["light_time_coordinate_squared"]) != light_square:
        raise ValueError("Coordinate light-time scale changed")
    a, b, closed = cell(te)
    stored_cell = saved["emission_rounding_cell"]
    if (
        list(map(Q, stored_cell["bounds"])) != [a, b]
        or stored_cell["lower_included"] != closed
        or stored_cell["upper_included"] != closed
    ):
        raise ValueError("Emission rounding cell changed")
    rounded_lt = float.fromhex(saved["rounded_light_time_hex"])
    delay_low, delay_high, even = cell(rounded_lt)
    if not sqrt_membership(light_square, delay_low, delay_high, even):
        raise ValueError("Exact rounded norm witness failed")
    light = root(rounded(light_square))
    support = tuple(map(Q, saved["receiver_support_raw"]))
    if (
        not support[0]
        <= a + min(light[0], Q(rounded_lt))
        <= b + max(light[1], Q(rounded_lt))
        <= support[1]
    ):
        raise ValueError("Receiver grid does not cover both rounding models")
    status, grid = enumerate_bits(*support, plan["maximum_lattice_points_per_model"])
    if (
        saved["receiver_grid_status"] != status
        or saved["receiver_grid_hex"] != [v.hex() for v in grid]
        or [r["reception_hex"] for r in saved["receivers"]] != [v.hex() for v in grid]
    ):
        raise ValueError("Receiver grid population changed")
    for tr, record in zip(grid, saved["receivers"]):
        one = sqrt_membership(light_square, Q(tr) - b, Q(tr) - a, closed)
        q = Q(tr) - Q(rounded_lt)
        two = (q > a or q == a and closed) and (q < b or q == b and closed)
        within = abs(from_raw(tr, family) - Q(case["nominal_JD"])) * 86400 <= Q(
            plan["receiver_search_radius_seconds"]
        )
        if record["within_original_receiver_support"] != within or record[
            "rounding_hypotheses"
        ] != dict(zip(HYPOTHESES, (one, two))):
            raise ValueError("Receiver rounding/support predicate changed")
    qualified = (
        rg
        and lt
        and angle
        and row["original_label_budget_pass"]
        and status == "complete"
    )
    if (
        saved["range_matches"] != rg
        or saved["printed_light_time_matches"] != lt
        or saved["source_observables_qualified"] != qualified
        or saved["radial_rate_used_for_clock_qualification"]
    ):
        raise ValueError("Source observation qualification changed")
    return len(grid)


def check_inference(run, case, row, saved, plan):
    center = Q(case["nominal_JD"]) - Q(row["range_AU"]) * K
    radius = Q(plan["emission_search_radius_seconds"]) / 86400
    support = (center - radius, center + radius)
    if (
        Q(saved["emission_search_center_JD"]) != center
        or tuple(map(Q, saved["emission_search_support_JD"])) != support
    ):
        raise ValueError("Source search support moved")
    actual = radius_derivative(run / "source-records", case["window_index"], support)
    cover(actual, saved["radius_squared_derivative_AU2_per_day"])
    derivative = tuple(map(Q, saved["radius_squared_derivative_AU2_per_day"]))
    condition = derivative[0] * derivative[1] > 0 and min(map(abs, derivative)) >= Q(
        plan["minimum_radius_squared_derivative_AU2_per_day"]
    )
    if not condition:
        if saved["status"] != "conditioning_unknown" or saved["profiles"]:
            raise ValueError("Unconditioned radius promoted")
        return 0, 0, 0
    if saved["status"] != "monotone_source_radius" or set(saved["profiles"]) != set(
        plan["numerical_tube_profiles"]
    ):
        raise ValueError("Profile population changed")
    sign = 1 if derivative[0] > 0 else -1
    endpoints = emissions = receivers = 0

    def evaluate(t):
        return sign * radius_square(run / "source-records", case["window_index"], t)

    for profile, item in saved["profiles"].items():
        low, high = observed_bounds(
            row["range_AU"],
            plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"],
        )
        targets = (low * low, high * high) if sign == 1 else (-high * high, -low * low)
        if item["status"] != "bracketed":
            if (
                item["status"] != "unbracketed"
                or item["families"]
                or not (
                    evaluate(support[0]) > targets[0]
                    or evaluate(support[1]) < targets[1]
                )
            ):
                raise ValueError("Unbracketed radius status unproved")
            continue
        brackets = [tuple(map(Q, p)) for p in item["boundary_brackets_JD"]]
        for (a, b), target in zip(brackets, targets):
            if (
                not support[0] <= a <= b <= support[1]
                or b - a != 2 * radius / 2 ** plan["inverse_iterations"]
                or not evaluate(a) <= target <= evaluate(b)
            ):
                raise ValueError("Exact radius inverse endpoint proof failed")
            endpoints += 2
        lo, hi = brackets[0][0], brackets[1][1]
        if tuple(map(Q, item["effective_JD"])) != (lo, hi) or set(
            item["families"]
        ) != set(MODELS):
            raise ValueError("Inverse interval or coordinate family changed")
        for family, found in item["families"].items():
            a, b = (
                (lo, hi)
                if family == MODELS[0]
                else ((lo - 2451545) * 86400, (hi - 2451545) * 86400)
            )
            status, grid = enumerate_bits(
                a, b, plan["maximum_lattice_points_per_model"]
            )
            if (
                found["grid_status"] != status
                or found["emission_grid_hex"] != [v.hex() for v in grid]
                or [c["emission_hex"] for c in found["candidates"]]
                != ([v.hex() for v in grid] if status == "complete" else [])
            ):
                raise ValueError("Emission grid changed")
            for te, candidate in zip(grid, found["candidates"]):
                receivers += check_candidate(
                    run, case, row, profile, family, te, candidate, plan
                )
                emissions += 1
            clocks = {
                h: sorted(
                    {
                        r["reception_hex"]
                        for c in found["candidates"]
                        if c["source_observables_qualified"]
                        for r in c["receivers"]
                        if r["within_original_receiver_support"]
                        and r["rounding_hypotheses"][h]
                    }
                )
                for h in HYPOTHESES
            }
            if found["qualified_reception_points_by_hypothesis"] != clocks:
                raise ValueError("Qualified clock set changed")
    return endpoints, emissions, receivers


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    for name, h in plan["inputs_sha256"].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != h:
            raise ValueError("Input source seal changed")
    saved = json.loads((run / (cohort + "-first-analysis.json")).read_text())
    if (
        saved["plan_sha256"] != hashlib.sha256(rawplan).hexdigest()
        or saved["cohort"] != cohort
        or saved["physical_time_model_certified"]
        or saved["Earth_view_clock_equivalence_certified"]
        or saved["new_candidate_holdouts"]
        or saved["full_goal_complete"]
        or saved["production_acceptance_exit_code"] != 2
        or saved["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Claim scope or identity changed")
    obs = [
        q for q in plan["queries"] if q["cohort"] == cohort and q["kind"] == "observer"
    ]
    geo = [
        q for q in plan["queries"] if q["cohort"] == cohort and q["kind"] == "geometry"
    ]
    if [q["id"] for q in obs] != [q["id"] for q in saved["observer_queries"]] or [
        q["id"] for q in geo
    ] != [q["id"] for q in saved["geometry_queries"]]:
        raise ValueError("Query coverage changed")
    end = emit = recv = geometric = 0
    for query, group in zip(obs, saved["observer_queries"]):
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Observer response unavailable")
        original = rows(raw, query, plan)
        if [r["case_id"] for r in original] != [
            r["observation"]["case_id"] for r in group["rows"]
        ]:
            raise ValueError("Observer row coverage changed")
        for row, record in zip(original, group["rows"]):
            if row != record["observation"]:
                raise ValueError("Observer values changed")
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            a, b, c = check_inference(run, case, row, record["inference"], plan)
            end += a
            emit += b
            recv += c
    for query, group in zip(geo, saved["geometry_queries"]):
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Geometry comparison unavailable")
        original = raw_rows(raw, query, query["cases"], plan)
        if [r["case_id"] for r in original] != [r["case_id"] for r in group["rows"]]:
            raise ValueError("Geometry population changed")
        for row, record in zip(original, group["rows"]):
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            a, b = vector_proof(run, "Earth", case, row, record, plan)
            geometric += a + b
        observer = next(q for q in obs if q["encoding"] == query["encoding"])
        for key in (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        ):
            if observer["parameters"][key] != query["parameters"][key]:
                raise ValueError("Comparison TT batches differ")
    expected = []
    for group in saved["observer_queries"]:
        geometry = next(
            g for g in saved["geometry_queries"] if g["encoding"] == group["encoding"]
        )
        query = next(q for q in obs if q["id"] == group["id"])
        for record in group["rows"]:
            row = record["observation"]
            inf = record["inference"]
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            g = next(v for v in geometry["rows"] if v["case_id"] == row["case_id"])
            if inf["status"] != "monotone_source_radius":
                continue
            for profile, item in inf["profiles"].items():
                for family, found in item["families"].items():
                    for hypothesis, points in found[
                        "qualified_reception_points_by_hypothesis"
                    ].items():
                        checks = []
                        for point in points:
                            state = exact_state(
                                run / "source-records",
                                case["window_index"],
                                from_raw(float.fromhex(point), family),
                                "Earth",
                            )
                            obsbounds = [
                                observed_bounds(
                                    v,
                                    plan["numerical_tube_profiles"][profile][
                                        "extra_binary64_ULPs"
                                    ],
                                )
                                for v in g["printed_state"]
                            ]
                            flags = [a <= v <= b for v, (a, b) in zip(state, obsbounds)]
                            checks.append(
                                {
                                    "reception_hex": point,
                                    "source_components_match_geometry": flags,
                                    "same_argument_qualified": all(flags)
                                    and g["original_label_budget_pass"],
                                }
                            )
                        expected.append(
                            {
                                "case_id": case["id"],
                                "role": case["role"],
                                "encoding": group["encoding"],
                                "profile": profile,
                                "coordinate_family": family,
                                "rounding_hypothesis": hypothesis,
                                "observer_receiver_points": points,
                                "geometric_label_budget_pass": g[
                                    "original_label_budget_pass"
                                ],
                                "checks": checks,
                                "physical_or_internal_clock_identity_certified": False,
                            }
                        )
    if saved["clock_comparisons"] != expected:
        raise ValueError("Cross-table clock predicate changed")
    return {
        "cohort": cohort,
        "radius_inverse_endpoint_checks": end,
        "emission_grid_points_checked": emit,
        "receiver_grid_points_checked": recv,
        "geometry_endpoint_and_component_checks": geometric,
        "full_observer_population": sum(
            len(g["rows"]) for g in saved["observer_queries"]
        ),
        "physical_time_model_certified": False,
        "Earth_view_clock_equivalence_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    value = verify(args.run, args.cohort)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
