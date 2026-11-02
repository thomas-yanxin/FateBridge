"""Independent exact-basis inverse proofs and binary64 bit-lattice replay.

No emission producer, Clenshaw, interval AD or candidate imports. Receiver/source
boxes use the independent Bernstein reader; lattice neighbors use IEEE bits.
"""

import argparse
import csv
import hashlib
import json
import struct
import urllib.parse
from fractions import Fraction as Q
from functools import lru_cache
from pathlib import Path

from scripts.audit_astrodice_de441_reference import direct_state
from scripts.verify_astrodice_observer_clock import (
    Source,
    add,
    cover,
    divide,
    length,
    mul,
    observed,
    observed_direction,
    parse,
    rounded,
    sub,
)
from scripts.verify_astrodice_vector_clock import verify as verify_vector

K = Q(149597870700, 299792458 * 86400)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=32)
def raw_source(directory, window):
    h = (directory / "header.bin").read_bytes()
    if len(h) != 8144 or struct.unpack_from("<i", h, 2840)[0] != 441:
        raise ValueError("Original DE441 header differs")
    au, emrat = map(Q, struct.unpack_from("<2d", h, 2680))
    pointers = [struct.unpack_from("<3i", h, 2696 + 12 * g) for g in range(12)]
    raw = (directory / f"record-responses/case-{window:02}.bin").read_bytes()
    if len(raw) != 3 * 8144:
        raise ValueError("Incomplete source records")
    return au, emrat, pointers, [raw[i : i + 8144] for i in range(0, len(raw), 8144)]


def exact_position(directory, window, epoch, body):
    au, emrat, pointers, records = raw_source(directory, window)
    record = next(
        v
        for v in records
        if Q(struct.unpack_from("<d", v)[0])
        <= epoch
        < Q(struct.unpack_from("<d", v, 8)[0])
    )
    if body == "Venus":
        return [v / au for v in direct_state(record, pointers[1], epoch)[:3]]
    if body != "Earth":
        raise ValueError("Unplanned exact source body")
    emb, moon = [direct_state(record, pointers[g], epoch) for g in (2, 9)]
    return [(e - m / (emrat + 1)) / au for e, m in zip(emb[:3], moon[:3])]


def neighbor(value, up):
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    if value == 0:
        bits = 1 if up else (1 << 63) + 1
    elif (value > 0) == up:
        bits += 1
    else:
        bits -= 1
    return struct.unpack(">d", struct.pack(">Q", bits))[0]


def enumerate_bits(low, high, maximum):
    current = float(low)
    if Q(current) < low:
        current = neighbor(current, True)
    values = []
    while Q(current) <= high:
        if len(values) == maximum:
            return "enumeration_limit", values
        values.append(current)
        current = neighbor(current, True)
    return "complete", values


def cell(value):
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    return (
        (Q(neighbor(value, False)) + Q(value)) / 2,
        (Q(neighbor(value, True)) + Q(value)) / 2,
        bits % 2 == 0,
    )


def relation(image, c):
    low, high = image
    a, b, closed = c
    return (
        (high > a or high == a and closed) and (low < b or low == b and closed),
        (low > a or low == a and closed) and (high < b or high == b and closed),
    )


def overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def to_raw(epoch, model):
    return epoch if model == "absolute_JD_binary64" else (epoch - 2451545) * 86400


def from_raw(value, model):
    return (
        Q(value) if model == "absolute_JD_binary64" else Q(2451545) + Q(value) / 86400
    )


def infer_proof(run, case, row, cal, profile, stored, plan):
    if stored["calibration_all_six_not_refuted"] != cal.get(
        "all_six_compatible", False
    ):
        raise ValueError("Geometric state contradiction hidden")
    if cal["status"] != "bracketed":
        if stored["status"] != "calibration_unknown":
            raise ValueError("Unavailable calibration promoted")
        return 0, 0
    if stored["status"] == "source_model_unknown":
        return 0, 0
    low, high = map(Q, cal["effective_JD"])
    mid = (low + high) / 2
    if (
        stored["reception_JD"] != cal["effective_JD"]
        or Q(stored["Earth_center_JD"]) != mid
    ):
        raise ValueError("Receiver argument changed")
    source = Source(run / "source-records", case["window_index"])
    reception = rounded(low, high, scale=1 << 256)
    center = exact_position(run / "source-records", case["window_index"], mid, "Earth")
    if list(map(Q, stored["Earth_center_AU"])) != center:
        raise ValueError("Independent exact Earth center differs")
    independent_earth = source.state(reception, "Earth")[:3]
    earth = [parse(v) for v in stored["Earth_box_AU"]]
    for actual, declared in zip(independent_earth, stored["Earth_box_AU"]):
        cover(actual, declared)
    radius = Q(stored["Earth_radius_AU"])
    maximum_square = sum(
        max(abs(a - c), abs(b - c)) ** 2 for (a, b), c in zip(earth, center)
    )
    if radius < 0 or radius**2 < maximum_square:
        raise ValueError("Receiver position ball understated")
    obs = observed(
        row["range_AU"], plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    )
    if parse(stored["observed_range_AU"]) != obs:
        raise ValueError("Original range uncertainty tube changed")
    expanded = (obs[0] - radius, obs[1] + radius)
    if parse(stored["expanded_range_AU"]) != expanded or expanded[0] <= 0:
        raise ValueError("Triangle expansion differs")
    nominal = mid - Q(row["range_AU"]) * K
    if Q(stored["search_center_JD"]) != nominal:
        raise ValueError("Search center selected after observing residual")
    radius_time = Q(plan["emission_search_radius_seconds"]) / 86400
    support = rounded(nominal - radius_time, nominal + radius_time, scale=1 << 256)
    broad = source.state(support, "Venus")
    ray = [sub(p, rounded(c)) for p, c in zip(broad[:3], center)]
    fprime = rounded(0)
    for p, v in zip(ray, broad[3:]):
        fprime = add(fprime, mul(p, v))
    fprime = mul(rounded(2), fprime)
    radial = divide(fprime, mul(rounded(2), length(ray)))
    cover(fprime, stored["squared_distance_derivative"])
    cover(radial, stored["radial_derivative_AU_per_day"])
    dl, dh = parse(stored["radial_derivative_AU_per_day"])
    minimum = min(abs(dl), abs(dh)) if dl * dh > 0 else Q(0)
    if minimum < Q(plan["minimum_absolute_emission_radial_derivative_AU_per_day"]):
        if stored["status"] != "conditioning_unknown":
            raise ValueError("Unconditioned source inversion promoted")
        return 0, 0
    sign = 1 if dl > 0 else -1

    def squared(epoch):
        positions = exact_position(
            run / "source-records", case["window_index"], epoch, "Venus"
        )
        return sum((v - c) ** 2 for v, c in zip(positions, center))

    targets = (
        (expanded[0] ** 2, expanded[1] ** 2)
        if sign == 1
        else (-(expanded[1] ** 2), -(expanded[0] ** 2))
    )
    inv = stored["inverse"]
    if inv["status"] != "bracketed":
        if stored["status"] != "source_range_unbracketed" or not (
            sign * squared(nominal - radius_time) > targets[0]
            or sign * squared(nominal + radius_time) < targets[1]
        ):
            raise ValueError("Unbracketed status cannot be verified")
        return 0, 0
    if stored["status"] != "inferred":
        raise ValueError("Inverse status changed")
    brackets = [parse(b) for b in inv["boundary_brackets_JD"]]
    for (a, b), target in zip(brackets, targets):
        if (
            not nominal - radius_time <= a <= b <= nominal + radius_time
            or b - a
            != 2 * radius_time / 2 ** plan["emission_inverse_bisection_iterations"]
            or not sign * squared(a) <= target <= sign * squared(b)
        ):
            raise ValueError("Exact inverse endpoint witness failed")
    a, b = brackets[0][0], brackets[1][1]
    if parse(inv["effective_JD"]) != (a, b) or parse(
        stored["effective_emission_JD"]
    ) != (a, b):
        raise ValueError("Effective inverse interval differs from proof brackets")
    continuous = (low - obs[1] * K, high - obs[0] * K)
    if (
        parse(stored["continuous_emission_JD"]) != continuous
        or stored["continuous_necessary_overlap"] != overlap((a, b), continuous)
        or parse(stored["effective_minus_continuous_seconds"])
        != ((a - continuous[1]) * 86400, (b - continuous[0]) * 86400)
    ):
        raise ValueError("Continuous source hypothesis score changed")
    direction = observed_direction(
        row["astrometric_angles"],
        plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"],
    )
    for actual, declared in zip(direction, stored["observed_direction_ICRF"]):
        cover(actual, declared)
    if set(stored["lattices"]) != set(plan["lattice_coordinate_models"]):
        raise ValueError("A lattice hypothesis was dropped")
    candidate_checks = 0
    for model in plan["lattice_coordinate_models"]:
        lattice = stored["lattices"][model]
        status, points = enumerate_bits(
            to_raw(a, model), to_raw(b, model), plan["maximum_lattice_points_per_model"]
        )
        if (
            lattice["enumeration_status"] != status
            or lattice["points_in_effective_interval"] != len(points)
            or len(lattice["candidates"]) != len(points)
        ):
            raise ValueError("Complete float lattice enumeration changed")
        admissible = 0
        for value, item in zip(points, lattice["candidates"]):
            epoch = from_raw(value, model)
            if (
                Q(item["raw_exact"]) != Q(value)
                or Q(float.fromhex(item["raw_hex"])) != Q(value)
                or Q(item["epoch_JD"]) != epoch
            ):
                raise ValueError("Binary64 candidate identity changed")
            c = cell(value)
            if (
                parse(item["rounding_cell"]["bounds"]) != c[:2]
                or item["rounding_cell"]["lower_included"] != c[2]
                or item["rounding_cell"]["upper_included"] != c[2]
            ):
                raise ValueError("Nearest even-tie rounding cell changed")
            # Use the same declared Earth box after independently proving it.
            venus = source.state(rounded(epoch, scale=1 << 256), "Venus")[:3]
            ray = [sub(v, e) for v, e in zip(venus, earth)]
            distance = length(ray)
            cover(distance, item["range_AU"])
            for p, declared in zip(ray, item["direction_ICRF"]):
                cover(divide(p, distance), declared)
            next_epoch = sub(reception, mul(distance, rounded(K)))
            image = (
                next_epoch
                if model == "absolute_JD_binary64"
                else mul(sub(next_epoch, rounded(2451545)), rounded(86400))
            )
            cover(image, item["next_image_raw"])
            intersects, contained = relation(parse(item["next_image_raw"]), c)
            expected = {
                "range_overlap": overlap(parse(item["range_AU"]), obs),
                "astrometric_components_overlap": [
                    overlap(parse(x), parse(y))
                    for x, y in zip(
                        item["direction_ICRF"], stored["observed_direction_ICRF"]
                    )
                ],
                "nearest_cell_intersects": intersects,
                "entire_next_image_inside_cell": contained,
            }
            possible = (
                expected["range_overlap"]
                and all(expected["astrometric_components_overlap"])
                and intersects
            )
            if (
                item["checks"] != expected
                or item["hypothesis_not_refuted"] != possible
                or item["physical_or_internal_algorithm_certified"]
            ):
                raise ValueError("Candidate predicate or physical scope changed")
            admissible += possible
            candidate_checks += 1
        if (
            lattice["hypotheses_not_refuted"] != admissible
            or lattice["unique_not_refuted"]
            != (status == "complete" and admissible == 1)
            or lattice["conditional_refuted"]
            != (status == "complete" and admissible == 0)
        ):
            raise ValueError("Lattice model failure/ambiguity hidden")
    return 4, candidate_checks


def verify(run, cohort):
    raw_plan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(raw_plan)
    for name, expected in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-analysis.json").read_text()),
    }.items():
        if digest((run / name).read_bytes()) != expected:
            raise ValueError("Frozen input drift: " + name)
    data_raw = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(data_raw)
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != digest(raw_plan)
        or any(
            data[k]
            for k in [
                "candidate_calls",
                "new_candidate_holdouts",
                "TT_observer_clock_equivalence_certified",
                "physical_time_model_certified",
                "numerical_tubes_certified",
                "internal_emission_algorithm_certified",
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Diagnostics promoted to acceptance")
    specs = (
        plan["development_groups"]
        if cohort == "A"
        else [
            {
                "cohort": "B",
                "observation_root": ".",
                "calibration_root": "B-vector-calibration",
            }
        ]
    )
    expected_groups = []
    for spec in specs:
        source_plan = json.loads(
            (run / spec["observation_root"] / "plan-before-queries.json").read_text()
        )
        expected_groups.extend(
            (spec, q, source_plan)
            for q in source_plan["queries"]
            if q["cohort"] == spec["cohort"]
        )
        verify_vector(run / spec["calibration_root"], spec["cohort"])
    if len(data["groups"]) != len(expected_groups):
        raise ValueError("Development or held-out group missing")
    if cohort == "B":
        before = json.loads((run / "before-B-queries.json").read_text())
        if before["collector_sha256"] != digest(
            (run / "frozen-source/scripts/astrodice_vector_clock.py").read_bytes()
        ):
            raise ValueError("New OBSERVER collector differs from the sealed source")
        if (
            before["plan_sha256"] != digest(raw_plan)
            or before["prior_A_analysis_sha256"]
            != digest((run / "A-first-analysis.json").read_bytes())
            or (run / "B-vector-calibration/A-first-analysis.json").read_bytes()
            != (run / "A-first-analysis.json").read_bytes()
        ):
            raise ValueError("B collection lost the fixed A phase binding")
    endpoint_checks = candidates = 0
    summary = []
    for group, (spec, query, source_plan) in zip(data["groups"], expected_groups):
        if (
            any(group[k] != spec[k] for k in ("observation_root", "calibration_root"))
            or group["source_cohort"] != spec["cohort"]
            or group["query_id"] != query["id"]
        ):
            raise ValueError("Group source binding changed")
        obsroot = run / spec["observation_root"]
        calroot = run / spec["calibration_root"]
        calpath = calroot / (spec["cohort"] + "-first-analysis.json")
        calibrations = {q["id"]: q for q in json.loads(calpath.read_text())["queries"]}
        raw = (obsroot / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (obsroot / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        if (
            digest(raw) != group["raw_sha256"]
            or digest(raw) != receipt["raw_sha256"]
            or receipt["url"]
            != "https://ssd.jpl.nasa.gov/api/horizons.api?"
            + urllib.parse.urlencode(query["parameters"])
            or group["calibration_sha256"] != digest(calpath.read_bytes())
            or receipt["attempt"] != 1
            or receipt["verification_disabled"]
        ):
            raise ValueError("Raw observation/calibration contract changed")
        if group["status"] != "diagnosed":
            summary.append({"query": query["id"], "status": group["status"]})
            continue
        payload = json.loads(raw)
        if receipt["status"] != 200 or payload.get("error"):
            raise ValueError("Unavailable response promoted")
        text = payload["result"]
        prefix, body = text.split("$$SOE")
        body, _ = body.split("$$EOE")
        if not all(
            v in prefix
            for v in [
                "Venus",
                "(299)",
                "DE441",
                "Earth (399)",
                "Date__(TT)",
                "R.A.___(ICRF)",
                "RA_(ICRF-a-app)",
                "1-way_down_LT",
            ]
        ):
            raise ValueError("Source/frame/quantity header differs")
        rows = [
            [v.strip() for v in row] for row in csv.reader(body.strip().splitlines())
        ]
        cases = {c["id"]: c for c in source_plan["cohorts"][spec["cohort"]]}
        if len(rows) != len(cases) or len(group["rows"]) != len(cases):
            raise ValueError("Source rows were dropped")
        cal = {v["case_id"]: v for v in calibrations[query["id"]]["rows"]}
        stats = {
            "source_cohort": spec["cohort"],
            "query": query["id"],
            "primary": 0,
            "profiles": {
                p: {
                    "inferred": 0,
                    "geometric_six_not_refuted": 0,
                    "continuous_overlap": 0,
                    "lattices": {
                        m: {
                            "unique": 0,
                            "refuted": 0,
                            "multi_or_unknown": 0,
                            "joint_geometric_unique": 0,
                        }
                        for m in plan["lattice_coordinate_models"]
                    },
                }
                for p in plan["numerical_tube_profiles"]
            },
        }
        seen = set()
        for cells, record in zip(rows, group["rows"]):
            near = [
                c
                for c in cases.values()
                if abs(Q(cells[1]) - Q(c["nominal_JD"])) * 86400
                <= Q(source_plan["row_assignment_radius_seconds"])
            ]
            if len(cells) != 12 or cells[-1] or len(near) != 1:
                raise ValueError("Raw row identity is ambiguous")
            case = near[0]
            cid = case["id"]
            c = cal[cid]
            if (
                cid in seen
                or record["case_id"] != cid
                or record["role"] != case["role"]
                or record["nominal_JD"] != case["nominal_JD"]
                or record["window_index"] != case["window_index"]
                or record["astrometric_angles"] != cells[4:6]
                or record["range_AU"] != cells[6]
                or record["apparent_angles"] != cells[9:11]
                or record["light_time_minutes"] != cells[8]
                or record["deldot_km_per_second"] != cells[7]
            ):
                raise ValueError("Original range or case identity changed")
            seen.add(cid)
            error = (Q(cells[1]) - Q(case["nominal_JD"])) * 86400
            if (
                record["printed_JD"] != cells[1]
                or Q(record["label_error_seconds"]) != error
                or record["original_label_budget_pass"]
                != (
                    abs(error)
                    <= Q(source_plan["returned_label_match_budget_days"]) * 86400
                )
                or record["calibration_original_label_pass"]
                != c["original_label_budget_pass"]
            ):
                raise ValueError("Original label line changed")
            primary = case["role"] != "auxiliary_not_primary"
            stats["primary"] += primary
            for p in plan["numerical_tube_profiles"]:
                item = record["profiles"][p]
                n, k = infer_proof(run, case, record, c["profiles"][p], p, item, plan)
                endpoint_checks += n
                candidates += k
                s = stats["profiles"][p]
                s["geometric_six_not_refuted"] += (
                    primary and item["calibration_all_six_not_refuted"]
                )
                if item["status"] != "inferred":
                    continue
                s["inferred"] += primary
                s["continuous_overlap"] += (
                    primary and item["continuous_necessary_overlap"]
                )
                for m, v in item["lattices"].items():
                    s["lattices"][m]["unique"] += primary and v["unique_not_refuted"]
                    s["lattices"][m]["refuted"] += primary and v["conditional_refuted"]
                    s["lattices"][m]["multi_or_unknown"] += primary and not (
                        v["unique_not_refuted"] or v["conditional_refuted"]
                    )
                    s["lattices"][m]["joint_geometric_unique"] += (
                        primary
                        and v["unique_not_refuted"]
                        and item["calibration_all_six_not_refuted"]
                        and record["original_label_budget_pass"]
                        and record["calibration_original_label_pass"]
                    )
        if seen != set(cases):
            raise ValueError("Frozen population reduced")
        summary.append(stats)
    return {
        "method_id": "independent_exact_basis_inverse_and_IEEE_bit_lattice_replay_v1",
        "cohort": cohort,
        "analysis_sha256": digest(data_raw),
        "groups": summary,
        "exact_inverse_endpoint_checks": endpoint_checks,
        "lattice_candidate_enclosures_checked": candidates,
        "exit_code": 0,
        "candidate_calls": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "internal_emission_algorithm_certified": False,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "TT_observer_clock_equivalence_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.run, args.cohort)
    with args.output.open("x") as out:
        json.dump(value, out, indent=2)
        out.write("\n")
