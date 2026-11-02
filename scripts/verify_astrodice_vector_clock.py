"""Independent direct-power/Bernstein replay of geometric clock evidence.

No collector, Clenshaw, interval/AD library, candidate or ephemeris backend is
imported. Exact rational Bernstein bounds independently certify monotonicity
and bracket endpoints; component overlaps remain necessary conditions only.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import urllib.parse
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def evaluate(coeff, x):
    value = Q(0)
    for c in reversed(coeff):
        value = value * x + c
    return value


def derivative(coeff):
    return [k * c for k, c in enumerate(coeff)][1:] or [Q(0)]


def bernstein_bounds(coeff, low, high):
    if low > high:
        raise ValueError("Reversed polynomial support")
    n = len(coeff) - 1
    shifted = [
        sum(
            (coeff[j] * math.comb(j, k) * low ** (j - k) for j in range(k, n + 1)), Q(0)
        )
        * (high - low) ** k
        for k in range(n + 1)
    ]
    b = [
        sum(
            (shifted[j] * Q(math.comb(k, j), math.comb(n, j)) for j in range(k + 1)),
            Q(0),
        )
        for k in range(n + 1)
    ]
    return min(b), max(b)


def polynomials(source, window, nominal):
    h = (source / "header.bin").read_bytes()
    if len(h) != 8144 or struct.unpack_from("<i", h, 2840)[0] != 441:
        raise ValueError("Unplanned DE441 source header")
    au = Q(struct.unpack_from("<d", h, 2680)[0])
    offset, n, parts = struct.unpack_from("<3i", h, 2708)
    if (offset, n, parts) != (171, 10, 2):
        raise ValueError("Unplanned Venus source layout")
    raw = (source / f"record-responses/case-{window:02}.bin").read_bytes()
    records = [raw[i : i + 8144] for i in range(0, len(raw), 8144)]
    raw = next(
        v
        for v in records
        if Q(struct.unpack_from("<d", v)[0])
        <= nominal
        < Q(struct.unpack_from("<d", v, 8)[0])
    )
    start, end = map(Q, struct.unpack_from("<2d", raw))
    width = (end - start) / parts
    part = (nominal - start) // width
    start += part * width
    basis = [[Q(1)], [Q(0), Q(1)]]
    for _ in range(2, n):
        c = [Q(0)] + [2 * v for v in basis[-1]]
        for i, v in enumerate(basis[-2]):
            c[i] -= v
        basis.append(c)
    positions = []
    for axis in range(3):
        index = offset - 1 + (part * 3 + axis) * n
        coeff = list(map(Q, struct.unpack_from("<" + str(n) + "d", raw, index * 8)))
        p = [Q(0)] * n
        for c, b in zip(coeff, basis):
            for i, v in enumerate(b):
                p[i] += c * v / au
        positions.append(p)
    velocities = [[v * 2 / width for v in derivative(p)] for p in positions]
    return start, width, positions + velocities


def observed_bounds(text, ulps):
    d = Decimal(text)
    exponent = d.as_tuple().exponent
    unit = Q(10**exponent) if exponent >= 0 else Q(1, 10**-exponent)
    half_width = unit + ulps * Q(math.ulp(float(text)))
    return Q(text) - half_width, Q(text) + half_width


def verify(run, cohort):
    plan_bytes = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(plan_bytes)
    for name, expected in plan["inputs_sha256"].items():
        if digest((run / name).read_bytes()) != expected:
            raise ValueError("Frozen input changed: " + name)
    seal = json.loads((run / "implementation-before-queries.json").read_text())
    for name, expected in seal.items():
        if digest((run / name).read_bytes()) != expected:
            raise ValueError("Before-query implementation seal changed: " + name)
    before = json.loads((run / ("before-" + cohort + "-queries.json")).read_text())
    if (
        before["cohort"] != cohort
        or before["plan_sha256"] != digest(plan_bytes)
        or before["collector_sha256"]
        != seal["frozen-source/scripts/astrodice_vector_clock.py"]
    ):
        raise ValueError("Actual collection does not match the pre-query seal")
    if cohort == "B" and before["prior_A_analysis_sha256"] != digest(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B was not bound to the retained A analysis")
    analysis_bytes = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(analysis_bytes)
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != digest(plan_bytes)
        or any(
            data[k]
            for k in [
                "candidate_calls",
                "TT_observer_clock_equivalence_certified",
                "numerical_tube_certified",
                "physical_time_model_certified",
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
    ):
        raise ValueError("Scope or original gate was promoted")
    expected_queries = [q for q in plan["queries"] if q["cohort"] == cohort]
    if [q["id"] for q in data["queries"]] != [q["id"] for q in expected_queries]:
        raise ValueError("Frozen query population changed")
    cases = {c["id"]: c for c in plan["cohorts"][cohort]}
    checks = []
    endpoint_checks = bound_checks = 0
    for query, output in zip(expected_queries, data["queries"]):
        name = query["id"]
        raw = (run / "responses" / (name + ".raw")).read_bytes()
        receipt = json.loads((run / "responses" / (name + ".receipt.json")).read_text())
        expected_url = (
            "https://ssd.jpl.nasa.gov/api/horizons.api?"
            + urllib.parse.urlencode(query["parameters"])
        )
        if (
            receipt["raw_sha256"] != digest(raw)
            or output["raw_sha256"] != digest(raw)
            or receipt["url"] != expected_url
            or receipt["attempt"] != 1
            or receipt["verification_disabled"]
        ):
            raise ValueError("Raw response or actual query contract changed")
        if output["status"] != "diagnosed":
            checks.append(
                {
                    "id": name,
                    "status": "unavailable_or_invalid",
                    "error": output.get("error"),
                }
            )
            continue
        result = json.loads(raw)
        if receipt["status"] != 200 or result.get("error"):
            raise ValueError("Unsuccessful response promoted")
        text = result["result"]
        prefix, body = text.split("$$SOE")
        body, _ = body.split("$$EOE")
        if not all(
            re.search(pattern, prefix)
            for pattern in [
                r"Target body name: Venus.*?\((299|2)\).*?DE441",
                r"Center body name: Solar System Barycenter \(0\).*?DE441",
                r"Output units\s*:\s*AU-D",
                r"Reference frame\s*:\s*ICRF",
                r"Output type\s*:\s*GEOMETRIC cartesian states",
                r"Calendar mode\s*:\s*Gregorian",
                "JD" + query["time_type"],
            ]
        ):
            raise ValueError("Raw source/frame/timescale contract failed")
        rows = [
            [v.strip() for v in row] for row in csv.reader(body.strip().splitlines())
        ]
        if len(rows) != len(cases) or len(output["rows"]) != len(cases):
            raise ValueError("Row population changed")
        used = set()
        summary = {
            "id": name,
            "primary": 0,
            "label_pass": 0,
            "profiles": {
                p: {
                    "six_not_refuted": 0,
                    "hypotheses": {
                        h: 0 for h in plan["clock_representation_hypotheses"]
                    },
                }
                for p in plan["numerical_tube_profiles"]
            },
        }
        for row, stored in zip(rows, output["rows"]):
            near = [
                c
                for c in cases.values()
                if abs(Q(row[0]) - Q(c["nominal_JD"])) * 86400
                <= Q(plan["row_assignment_radius_seconds"])
            ]
            if len(near) != 1:
                raise ValueError("Ambiguous raw case assignment")
            case = near[0]
            if (
                case["id"] in used
                or stored["case_id"] != case["id"]
                or stored["printed_state"] != row[2:8]
                or stored["printed_JD"] != row[0]
                or stored["role"] != case["role"]
            ):
                raise ValueError("Raw/stored row identity changed")
            used.add(case["id"])
            nominal = Q(case["nominal_JD"])
            label_error = (Q(row[0]) - nominal) * 86400
            label_pass = (
                abs(label_error) <= Q(plan["returned_label_match_budget_days"]) * 86400
            )
            if (
                label_error != Q(stored["label_error_seconds"])
                or label_pass != stored["original_label_budget_pass"]
            ):
                raise ValueError("Original label budget changed")
            start, width, polys = polynomials(
                run / "source-records", case["window_index"], nominal
            )

            def x(t):
                if not start <= t < start + width:
                    raise ValueError("Support crosses polynomial cell")
                return 2 * (t - start) / width - 1

            radius = Q(plan["source_inverse_search_radius_seconds"]) / 86400
            broad_low, broad_high = x(nominal - radius), x(nominal + radius)
            claimed_d = [tuple(map(Q, v)) for v in stored["derivative_bounds"]]
            for poly, claimed in zip(polys[3:], claimed_d):
                actual = bernstein_bounds(poly, broad_low, broad_high)
                if not claimed[0] <= actual[0] <= actual[1] <= claimed[1]:
                    raise ValueError("Independent derivative bound not contained")
                bound_checks += 1
            conditions = [
                min(abs(a), abs(b)) if a * b > 0 else Q(0) for a, b in claimed_d
            ]
            axis = max(range(3), key=lambda i: conditions[i])
            if axis != stored["axis"] or conditions[axis] < Q(
                plan["minimum_monotone_position_derivative_AU_per_day"]
            ):
                raise ValueError("Axis rule or minimum conditioning changed")
            sign = 1 if claimed_d[axis][0] > 0 else -1
            primary = case["role"] != "auxiliary_not_primary"
            summary["primary"] += primary
            summary["label_pass"] += primary and label_pass
            for profile, settings in plan["numerical_tube_profiles"].items():
                item = stored["profiles"][profile]
                obs = [
                    observed_bounds(v, settings["extra_binary64_ULPs"])
                    for v in row[2:8]
                ]
                if item["status"] != "bracketed":
                    raise ValueError(
                        "Unexpected unbracketed row requires explicit replay"
                    )
                targets = obs[axis] if sign == 1 else (-obs[axis][1], -obs[axis][0])
                brackets = [tuple(map(Q, b)) for b in item["boundary_brackets_JD"]]
                for (a, b), target in zip(brackets, targets):
                    if (
                        not nominal - radius <= a <= b <= nominal + radius
                        or b - a
                        != 2 * radius / 2 ** plan["source_inverse_bisection_iterations"]
                        or not sign * evaluate(polys[axis], x(a))
                        <= target
                        <= sign * evaluate(polys[axis], x(b))
                    ):
                        raise ValueError(
                            "Independent exact inverse boundary witness failed"
                        )
                    endpoint_checks += 2
                low, high = brackets[0][0], brackets[1][1]
                if list(map(Q, item["effective_JD"])) != [low, high] or list(
                    map(Q, item["effective_offset_seconds"])
                ) != [(low - nominal) * 86400, (high - nominal) * 86400]:
                    raise ValueError("Effective interval differs from its brackets")
                actual_boxes = [bernstein_bounds(p, x(low), x(high)) for p in polys]
                claimed_boxes = [tuple(map(Q, b)) for b in item["source_state_bounds"]]
                for (a, b), (c, d) in zip(actual_boxes, claimed_boxes):
                    if not c <= a <= b <= d:
                        raise ValueError(
                            "Independent state bounds not inside declared enclosure"
                        )
                    bound_checks += 1
                overlaps = [
                    a <= d and c <= b for (a, b), (c, d) in zip(claimed_boxes, obs)
                ]
                if (
                    item["component_compatible"] != overlaps
                    or item["position_compatible"] != all(overlaps[:3])
                    or item["velocity_compatible"] != all(overlaps[3:])
                    or item["all_six_compatible"] != all(overlaps)
                ):
                    raise ValueError("State contradiction was dropped")
                hypotheses = {
                    "exact_nominal_TDB": nominal,
                    "binary64_absolute_JD": Q(float(nominal)),
                    "binary64_seconds_from_J2000": Q(2451545)
                    + Q(float((nominal - 2451545) * 86400)) / 86400,
                }
                membership = {h: low <= v <= high for h, v in hypotheses.items()}
                if item["hypothesis_in_inverse_interval"] != membership:
                    raise ValueError("Predeclared clock hypothesis score changed")
                summary["profiles"][profile]["six_not_refuted"] += primary and all(
                    overlaps
                )
                for h, inside in membership.items():
                    summary["profiles"][profile]["hypotheses"][h] += primary and inside
        if used != set(cases):
            raise ValueError("Frozen case population was reduced")
        checks.append(summary)
    return {
        "method": "independent_exact_power_Bernstein_clock_replay_v1",
        "cohort": cohort,
        "analysis_sha256": digest(analysis_bytes),
        "queries": checks,
        "exact_inverse_endpoint_checks": endpoint_checks,
        "independent_source_enclosure_checks": bound_checks,
        "exit_code": 0,
        "candidate_calls": 0,
        "new_TT_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "numerical_tube_certified": False,
        "TT_observer_clock_equivalence_certified": False,
        "physical_time_model_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(verify(args.run, args.cohort), stream, indent=2)
        stream.write("\n")
