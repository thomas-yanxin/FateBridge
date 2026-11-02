"""Independent OBSERVER geocentric range/rounding replay, no producer imports."""

import argparse
import csv
import hashlib
import json
import re
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_emission_epoch import (
    cell,
    enumerate_bits,
    from_raw,
    neighbor,
)
from scripts.verify_astrodice_joint_epoch import exact_state
from scripts.verify_astrodice_observer_clock import (
    Source,
    add,
    cover,
    mul,
    parse,
    rounded,
    sub,
)
from scripts.verify_astrodice_observer_radius_clock import (
    angular_proof,
    sqrt_membership,
)
from scripts.verify_astrodice_vector_clock import observed_bounds

FAMILIES = ("absolute_JD_binary64", "seconds_from_J2000_binary64")
HYPOTHESES = ("one_round_source_norm", "two_round_source_norm")
K = Q(149597870700, 299792458 * 86400)


def raw_rows(raw, query, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Observer service error")
    prefix, rest = payload["result"].split("$$SOE")
    text, _ = rest.split("$$EOE")
    for expression in [
        r"Target body name: Venus.*?\(299\).*?DE441",
        r"Center body name: Earth \(399\).*?DE441",
        r"Date__\(TT\)",
        r"Calendar mode\s*:\s*Gregorian",
        r"R\.A\._+\(ICRF\)",
        r"RA_\(ICRF-a-app\)",
        r"1-way_down_LT",
        r"delta,\s*deldot",
    ]:
        if not re.search(expression, prefix):
            raise ValueError("Source/observer/time/quantities changed")
    output = []
    seen = set()
    for cells in csv.reader(text.strip().splitlines()):
        c = [v.strip() for v in cells]
        if len(c) != 12 or c[-1]:
            raise ValueError("Quantity population changed")
        epoch = Q(c[1])
        matches = [
            v
            for v in query["cases"]
            if abs(epoch - Q(v["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(matches) != 1 or matches[0]["id"] in seen:
            raise ValueError("Observer cases changed")
        case = matches[0]
        seen.add(case["id"])
        error = epoch - Q(case["nominal_JD"])
        output.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "printed_JD": c[1],
                "printed_calendar": c[0],
                "astrometric_angles": c[4:6],
                "range_AU": c[6],
                "deldot_km_per_second": c[7],
                "light_time_minutes": c[8],
                "apparent_angles": c[9:11],
                "label_error_seconds": str(error * 86400),
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {v["id"] for v in query["cases"]}:
        raise ValueError("Observer population reduced")
    return output


def delay_proof(row, ulps, family, nominal, stored):
    lo, hi = [v / 1440 for v in observed_bounds(row["light_time_minutes"], ulps)]
    if not 0 < lo <= hi < 1:
        raise ValueError("Delay domain changed")
    scale = Q(1 if family == FAMILIES[0] else 86400)

    def ulp_at(q):
        value = float(q)
        return max(abs(Q(neighbor(value, up)) - Q(value)) for up in (False, True))

    e = max(
        ulp_at(
            nominal + d if family == FAMILIES[0] else (nominal + d - 2451545) * 86400
        )
        for d in (-2, 2)
    )
    delay_ulp = max(ulp_at(v * scale) for v in (lo, hi))
    padding = (e + delay_ulp) / (2 * scale)
    expected = {
        "printed_delay_days": list(map(str, (lo, hi))),
        "emission_raw_ULP_bound": str(e),
        "delay_raw_ULP_bound": str(delay_ulp),
        "both_rounding_models_padding_days": str(padding),
        "elapsed_delay_support_days": list(map(str, (lo - padding, hi + padding))),
    }
    if stored != expected:
        raise ValueError("Rounding/delay support changed")
    return lo - padding, hi + padding


def source_range(source, tr, delay):
    a, b = tr
    dl, dh = delay
    earth = source.state(rounded(a, b, scale=1 << 256), "Earth")
    venus = source.state(rounded(a - dh, b - dl, scale=1 << 256), "Venus")
    ray = [sub(v, e) for e, v in zip(earth, venus)]
    square = rounded(0)
    derivative = rounded(0)
    for p, v in zip(ray[:3], ray[3:]):
        square = add(square, mul(p, p))
        derivative = add(derivative, mul(rounded(2), mul(p, v)))
    return square, derivative


def check_candidate(run, case, row, ulps, family, tr, te, stored):
    epochs = [from_raw(v, family) for v in (tr, te)]
    e = exact_state(run / "source-records", case["window_index"], epochs[0], "Earth")
    v = exact_state(run / "source-records", case["window_index"], epochs[1], "Venus")
    ray = [a - b for a, b in zip(v, e)]
    square = sum(v * v for v in ray[:3])
    if (
        stored["receiver_hex"] != tr.hex()
        or stored["emitter_hex"] != te.hex()
        or list(map(Q, stored["epochs_JD_TDB"])) != epochs
        or list(map(Q, stored["source_ray_AU_and_velocity_difference"])) != ray
        or Q(stored["range_squared_AU2"]) != square
    ):
        raise ValueError("Exact source pair changed")
    angle = angular_proof(ray, row["astrometric_angles"], ulps, stored["angle_proof"])
    rg = sqrt_membership(square, *observed_bounds(row["range_AU"], ulps))
    lt = sqrt_membership(
        square * (K * 1440) ** 2, *observed_bounds(row["light_time_minutes"], ulps)
    )
    scale = Q(1 if family == FAMILIES[0] else 86400)
    delay_square = square * (K * scale) ** 2
    a, b, closed = cell(te)
    sc = stored["emission_rounding_cell"]
    if (
        list(map(Q, sc["bounds"])) != [a, b]
        or sc["lower_included"] != closed
        or sc["upper_included"] != closed
        or Q(stored["delay_raw_squared"]) != delay_square
    ):
        raise ValueError("Rounding cell or delay scale changed")
    delay = float.fromhex(stored["rounded_delay_hex"])
    if not sqrt_membership(delay_square, *cell(delay)):
        raise ValueError("Exact nearest-even delay witness invalid")
    one = sqrt_membership(delay_square, Q(tr) - b, Q(tr) - a, closed)
    diff = Q(tr) - Q(delay)
    two = (diff > a or diff == a and closed) and (diff < b or diff == b and closed)
    qualified = rg and lt and angle and row["original_label_budget_pass"]
    if (
        stored["range_matches"] != rg
        or stored["printed_light_time_matches"] != lt
        or stored["source_observables_qualified"] != qualified
        or stored["rounding_hypotheses"] != dict(zip(HYPOTHESES, (one, two)))
        or stored["radial_rate_used_for_clock_qualification"]
    ):
        raise ValueError("Source qualification or discrete rounding changed")


def check_inference(run, case, row, stored, plan):
    nominal = Q(case["nominal_JD"])
    radius = Q(plan["receiver_search_radius_seconds"]) / 86400
    support = (nominal - radius, nominal + radius)
    if tuple(map(Q, stored["receiver_support_JD"])) != support or set(
        stored["profiles"]
    ) != set(plan["numerical_tube_profiles"]):
        raise ValueError("Source support or profile population changed")
    reader = Source(run / "source-records", case["window_index"])
    endpoints = pairs_checked = 0
    for profile, models in stored["profiles"].items():
        if set(models) != set(FAMILIES):
            raise ValueError("Coordinate family dropped")
        ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
        low, high = observed_bounds(row["range_AU"], ulps)
        for family, found in models.items():
            elapsed = delay_proof(row, ulps, family, nominal, found["delay"])
            derivatives = []
            for k in range(plan["independent_derivative_subintervals"]):
                n = plan["independent_derivative_subintervals"]
                a, b = (
                    support[0] + 2 * radius * k / n,
                    support[0] + 2 * radius * (k + 1) / n,
                )
                derivatives.append(source_range(reader, (a, b), elapsed)[1])
            actual = min(v[0] for v in derivatives), max(v[1] for v in derivatives)
            cover(actual, found["range_squared_derivative_AU2_per_day"])
            derivative = parse(found["range_squared_derivative_AU2_per_day"])
            conditioned = derivative[0] * derivative[1] > 0 and min(
                map(abs, derivative)
            ) >= Q(plan["minimum_squared_range_derivative_AU2_per_day"])
            if not conditioned:
                if (
                    found["status"] != "conditioning_unknown"
                    or found["candidates"]
                    or any(found["qualified_pairs_by_hypothesis"].values())
                ):
                    raise ValueError("Unconditioned model promoted")
                continue
            sign = 1 if derivative[0] > 0 else -1
            target = (low**2, high**2) if sign == 1 else (-(high**2), -(low**2))

            def bounds(t):
                a, b = source_range(reader, (t, t), elapsed)[0]
                return (a, b) if sign == 1 else (-b, -a)

            enclosure = found["enclosure"]
            if enclosure["status"] == "excluded_over_original_support":
                if (
                    found["status"] != enclosure["status"]
                    or not (
                        bounds(support[1])[1] < target[0]
                        or bounds(support[0])[0] > target[1]
                    )
                    or found["candidates"]
                ):
                    raise ValueError("Support exclusion unproved")
                continue
            if (
                enclosure["status"] != "necessary_enclosure"
                or enclosure["root_existence_or_uniqueness_proved"]
            ):
                raise ValueError("Necessary enclosure promoted")
            brackets = [tuple(map(Q, p)) for p in enclosure["boundary_brackets_JD"]]
            if len(brackets) != 2:
                raise ValueError("Boundary population changed")
            for pair, witnesses in zip(
                brackets, enclosure["endpoint_range_squared_bounds"]
            ):
                a, b = pair
                if (
                    not support[0] <= a <= b <= support[1]
                    or b - a != 2 * radius / 2 ** plan["inverse_iterations"]
                ):
                    raise ValueError("Frozen bisection width/support changed")
                for t, witness in zip(pair, witnesses):
                    cover(source_range(reader, (t, t), elapsed)[0], witness)
                    endpoints += 1
            a, b = brackets[0][0], brackets[1][1]
            wa = tuple(map(Q, enclosure["endpoint_range_squared_bounds"][0][0]))
            wb = tuple(map(Q, enclosure["endpoint_range_squared_bounds"][1][1]))
            upper_a = wa[1] if sign == 1 else -wa[0]
            lower_b = wb[0] if sign == 1 else -wb[1]
            if (
                a != support[0]
                and not upper_a < target[0]
                or b != support[1]
                and not lower_b > target[1]
            ):
                raise ValueError("Necessary root-set exclusion failed")
            if tuple(map(Q, enclosure["effective_reception_JD"])) != (a, b) or a > b:
                raise ValueError("Receiver enclosure changed")
            raw_support = (
                (a, b)
                if family == FAMILIES[0]
                else ((a - 2451545) * 86400, (b - 2451545) * 86400)
            )
            status, receivers = enumerate_bits(
                *raw_support, plan["maximum_lattice_points_per_model"]
            )
            if found["receiver_grid_status"] != status or found[
                "receiver_grid_hex"
            ] != [v.hex() for v in receivers]:
                raise ValueError("Receiver grid population changed")
            grid_records = []
            all_pairs = []
            complete = status == "complete"
            scale = Q(1 if family == FAMILIES[0] else 86400)
            for tr in receivers if complete else []:
                status, emitters = enumerate_bits(
                    Q(tr) - elapsed[1] * scale,
                    Q(tr) - elapsed[0] * scale,
                    plan["maximum_lattice_points_per_model"],
                )
                grid_records.append(
                    {
                        "receiver_hex": tr.hex(),
                        "status": status,
                        "points_hex": [v.hex() for v in emitters],
                    }
                )
                complete &= status == "complete"
                all_pairs.extend((tr, te) for te in emitters)
            complete &= len(all_pairs) <= plan["maximum_pairs_per_model"]
            if (
                found["emitter_grids"] != grid_records
                or found["enumerated_pair_count"] != len(all_pairs)
                or found["status"] != ("complete" if complete else "enumeration_limit")
                or len(found["candidates"]) != (len(all_pairs) if complete else 0)
            ):
                raise ValueError("Emission pairs incomplete or cap bypassed")
            for (tr, te), candidate in zip(all_pairs, found["candidates"]):
                check_candidate(run, case, row, ulps, family, tr, te, candidate)
                pairs_checked += 1
            expected = {
                h: [
                    [c["receiver_hex"], c["emitter_hex"]]
                    for c in found["candidates"]
                    if c["source_observables_qualified"] and c["rounding_hypotheses"][h]
                ]
                for h in HYPOTHESES
            }
            if found["qualified_pairs_by_hypothesis"] != expected:
                raise ValueError("Qualified pair set changed")
    return endpoints, pairs_checked


def verify(run, cohort):
    raw = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(raw)
    for name, digest in plan["inputs_sha256"].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Source seal changed")
    data = json.loads((run / (cohort + "-first-analysis.json")).read_text())
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != hashlib.sha256(raw).hexdigest()
        or data["candidate_calls"]
        or data["new_candidate_holdouts"]
        or any(
            data[k]
            for k in (
                "numerical_tubes_certified",
                "physical_time_model_certified",
                "internal_algorithm_certified",
                "full_goal_complete",
            )
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Unsupported claim promotion")
    queries = [q for q in plan["queries"] if q["cohort"] == cohort]
    if [q["id"] for q in queries] != [q["id"] for q in data["queries"]]:
        raise ValueError("Query population changed")
    endpoints = pairs = rows_checked = 0
    for query, saved in zip(queries, data["queries"]):
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Unavailable observer response")
        rows = raw_rows(raw, query, plan)
        if len(saved["rows"]) != len(rows):
            raise ValueError("Observer row dropped")
        for row, record in zip(rows, saved["rows"]):
            if row != record["observation"]:
                raise ValueError("Printed source values changed")
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            e, p = check_inference(run, case, row, record["inference"], plan)
            endpoints += e
            pairs += p
            rows_checked += 1
    return {
        "cohort": cohort,
        "observer_rows_checked": rows_checked,
        "source_endpoint_checks": endpoints,
        "source_pairs_checked": pairs,
        "physical_time_model_certified": False,
        "internal_algorithm_certified": False,
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
