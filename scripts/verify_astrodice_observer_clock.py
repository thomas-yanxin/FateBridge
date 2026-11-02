"""Independent rational Bernstein replay of OBSERVER transfer enclosures.

Uses a separate 288-bit box implementation, direct power-basis source reader
and explicit interval proof steps. Imports no collector, Clenshaw or AD code.
The dynamics and declared numerical hypotheses remain shared limitations.
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

from scripts.verify_astrodice_vector_clock import bernstein_bounds, derivative
from scripts.verify_astrodice_vector_clock import verify as verify_vector

S = 1 << 288
K = Q(149597870700, 299792458 * 86400)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rounded(lo, hi=None, *, scale=S):
    lo, hi = Q(lo), Q(lo if hi is None else hi)
    if lo > hi:
        raise ValueError("Reversed independent box")
    return Q(lo.numerator * scale // lo.denominator, scale), Q(
        -((-hi.numerator * scale) // hi.denominator), scale
    )


def parse(pair):
    return tuple(map(Q, pair))


def add(a, b):
    return rounded(a[0] + b[0], a[1] + b[1])


def neg(a):
    return -a[1], -a[0]


def sub(a, b):
    return add(a, neg(b))


def mul(a, b):
    values = [x * y for x in a for y in b]
    return rounded(min(values), max(values))


def divide(a, b):
    if b[0] <= 0 <= b[1]:
        raise ValueError("Independent box denominator contains zero")
    return mul(a, rounded(1 / b[1], 1 / b[0]))


def square(a):
    lower = 0 if a[0] <= 0 <= a[1] else min(v * v for v in a)
    return rounded(lower, max(v * v for v in a))


def root(a):
    if a[0] < 0:
        raise ValueError("Negative independent square root")
    scaled_low, scaled_high = a[0] * S * S, a[1] * S * S
    lo = math.isqrt(scaled_low.numerator // scaled_low.denominator)
    hi = math.isqrt(scaled_high.numerator // scaled_high.denominator)
    hi += Q(hi * hi) < scaled_high
    return Q(lo, S), Q(hi, S)


def length(values):
    total = rounded(0)
    for v in values:
        total = add(total, square(v))
    return root(total)


def cover(computed, declared):
    low, high = parse(declared)
    if not low <= computed[0] <= computed[1] <= high:
        raise ValueError("Independent exact source enclosure is not covered")


class Source:
    def __init__(self, directory, window):
        raw = (directory / "header.bin").read_bytes()
        if len(raw) != 8144 or struct.unpack_from("<i", raw, 2840)[0] != 441:
            raise ValueError("Independent source header identity differs")
        self.au, self.emrat = map(Q, struct.unpack_from("<2d", raw, 2680))
        self.pointers = [
            struct.unpack_from("<3i", raw, 2696 + i * 12) for i in range(12)
        ]
        raw = (directory / f"record-responses/case-{window:02}.bin").read_bytes()
        if len(raw) != 3 * 8144:
            raise ValueError("Independent original source window incomplete")
        self.records = [
            v for v in (raw[k : k + 8144] for k in range(0, len(raw), 8144))
        ]
        self.cache = {}

    def group(self, epoch, group):
        low, high = epoch
        record = next(
            (
                r
                for r in self.records
                if Q(struct.unpack_from("<d", r)[0])
                <= low
                <= high
                < Q(struct.unpack_from("<d", r, 8)[0])
            ),
            None,
        )
        if record is None:
            raise ValueError("Independent source record support crosses a boundary")
        start, end = map(Q, struct.unpack_from("<2d", record))
        offset, count, parts = self.pointers[group]
        width = (end - start) / parts
        part = (low - start) // width
        begin = start + part * width
        if not 0 <= part < parts or high >= begin + width:
            raise ValueError("Independent source polynomial support crosses a cell")
        key = (start, group, part)
        if key not in self.cache:
            basis = [[Q(1)], [Q(0), Q(1)]]
            for _ in range(2, count):
                c = [Q(0)] + [2 * v for v in basis[-1]]
                for i, v in enumerate(basis[-2]):
                    c[i] -= v
                basis.append(c)
            positions = []
            for axis in range(3):
                index = offset - 1 + (part * 3 + axis) * count
                coefficients = map(
                    Q, struct.unpack_from("<" + str(count) + "d", record, index * 8)
                )
                p = [Q(0)] * count
                for c, b in zip(coefficients, basis):
                    for i, v in enumerate(b):
                        p[i] += c * v / self.au
                positions.append(p)
            self.cache[key] = positions + [
                [v * 2 / width for v in derivative(p)] for p in positions
            ]
        a, b = 2 * (low - begin) / width - 1, 2 * (high - begin) / width - 1
        return [rounded(*bernstein_bounds(p, a, b)) for p in self.cache[key]]

    def state(self, epoch, body):
        if body == "Venus":
            return self.group(epoch, 1)
        if body != "Earth":
            raise ValueError("Unplanned independent source body")
        emb, moon = self.group(epoch, 2), self.group(epoch, 9)
        return [sub(e, divide(m, rounded(self.emrat + 1))) for e, m in zip(emb, moon)]


def model_proof(source, reception, name, stored, plan):
    earth = source.state(reception, "Earth")[:3]
    initial = Q(plan["light_time_initial_interval_days"][1])
    epsilon = Q(0)
    history = stored["history"]
    if name == "legacy_two_linearized_delays":
        if (
            len(history) != 2
            or stored["continuous_family_contraction_upper"] is not None
        ):
            raise ValueError("Legacy light-time hypothesis was silently replaced")
        now = source.state(reception, "Venus")
        rough = now[:3]
        for step in history:
            computed = mul(
                length([sub(p, e) for p, e in zip(rough, earth)]), rounded(K)
            )
            cover(computed, step["delay_days"])
            delay = parse(step["delay_days"])
            rough = [sub(p, mul(v, delay)) for p, v in zip(now[:3], now[3:])]
    else:
        if (
            name
            not in {
                "converged_Newtonian_24",
                "converged_Newtonian_24_emission_ET_ULP_hypothesis",
            }
            or len(history) != plan["fixed_point_iterations"]
        ):
            raise ValueError("Unplanned/incomplete fixed-point hypothesis")
        if name.endswith("ULP_hypothesis"):
            seconds = [
                (v - 2451545) * 86400 for v in (reception[0] - initial, reception[1])
            ]
            epsilon = (
                max(Q(math.ulp(float(v))) for v in seconds)
                * plan["emission_error_full_binary64_ET_ULPs"]
                / 86400
            )
        broad = source.state(
            add(sub(reception, rounded(0, initial)), rounded(-epsilon, epsilon)),
            "Venus",
        )
        actual_q = length(broad[3:])[1] * K
        declared_q = Q(stored["continuous_family_contraction_upper"])
        if not actual_q <= declared_q < 1:
            raise ValueError("Independent fixed-point contraction proof failed")
        delay = rounded(0, initial)
        for step in history:
            if parse(step["input_days"]) != delay:
                raise ValueError("Fixed-point chain skipped or altered an iteration")
            emitted = source.state(
                add(sub(reception, delay), rounded(-epsilon, epsilon)), "Venus"
            )
            image = mul(
                length([sub(p, e) for p, e in zip(emitted[:3], earth)]), rounded(K)
            )
            cover(image, step["image_days"])
            a, b = parse(step["image_days"])
            if not 0 <= a <= b <= initial:
                raise ValueError("Image leaves the original fixed support")
            updated = (max(delay[0], a), min(delay[1], b))
            if updated != parse(step["next_days"]) or updated[0] > updated[1]:
                raise ValueError("Invalid fixed-point interval intersection")
            delay = updated
    if (
        Q(stored["emission_argument_radius_days"]) != epsilon
        or stored["internal_iteration_algorithm_certified"]
    ):
        raise ValueError("Emission hypothesis or algorithm scope changed")
    emitted = source.state(
        add(sub(reception, delay), rounded(-epsilon, epsilon)), "Venus"
    )
    ray = [sub(p, e) for p, e in zip(emitted[:3], earth)]
    distance = length(ray)
    cover(distance, stored["range_AU"])
    cover(mul(delay, rounded(1440)), stored["light_time_minutes"])
    for p, declared in zip(ray, stored["direction_ICRF"]):
        cover(divide(p, distance), declared)
    return len(history), 5


def observed(printed, ulps):
    exponent = Decimal(printed).as_tuple().exponent
    lsb = Q(10) ** exponent
    radius = lsb + ulps * Q(math.ulp(float(printed)))
    return rounded(Q(printed) - radius, Q(printed) + radius, scale=1 << 256)


def independent_pi():
    def atan(n, terms):
        s = sum(
            (Q((-1) ** k, (2 * k + 1) * n ** (2 * k + 1)) for k in range(terms)), Q(0)
        )
        other = s + Q((-1) ** terms, (2 * terms + 1) * n ** (2 * terms + 1))
        return min(s, other), max(s, other)

    a, b = atan(5, 80), atan(239, 32)
    return 16 * a[0] - 4 * b[1], 16 * a[1] - 4 * b[0]


def observed_direction(angles, ulps):
    pi = independent_pi()
    pairs = []
    for printed in angles:
        value = Q(printed)
        x = mul(rounded(value / 180), rounded(*pi))
        sn, cs, st, ct = rounded(0), rounded(0), x, rounded(1)
        minus_square = neg(square(x))
        for k in range(80):
            if k:
                st = divide(mul(st, minus_square), rounded((2 * k) * (2 * k + 1)))
                ct = divide(mul(ct, minus_square), rounded((2 * k - 1) * (2 * k)))
            sn, cs = add(sn, st), add(cs, ct)
        lo, hi = observed(printed, ulps)
        radius = max(value - lo, hi - value) * pi[1] / 180
        stail = Q(7) ** 161 / math.factorial(161)
        ctail = Q(7) ** 160 / math.factorial(160)
        pairs.append(
            (
                add(sn, rounded(-radius - stail, radius + stail)),
                add(cs, rounded(-radius - ctail, radius + ctail)),
            )
        )
    (sa, ca), (sd, cd) = pairs
    return [mul(cd, ca), mul(cd, sa), sd]


def intersects(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def verify(run, cohort):
    raw_plan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(raw_plan)
    for name, expected in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-queries.json").read_text()),
    }.items():
        if sha((run / name).read_bytes()) != expected:
            raise ValueError("Sealed source/protocol changed: " + name)
    calibration_root = run / (
        "vector-controls" if cohort == "A" else "B-vector-calibration"
    )
    calibration_replay = verify_vector(calibration_root, cohort)
    calibration_path = calibration_root / (cohort + "-first-analysis.json")
    calibrations = {
        q["id"]: {v["case_id"]: v for v in q["rows"]}
        for q in json.loads(calibration_path.read_text())["queries"]
    }
    data_bytes = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(data_bytes)
    before = json.loads((run / ("before-" + cohort + "-queries.json")).read_text())
    if before["collector_sha256"] != sha(
        (run / "frozen-source/scripts/astrodice_vector_clock.py").read_bytes()
    ):
        raise ValueError("OBSERVER collector differs from the sealed implementation")
    if (
        before["plan_sha256"] != sha(raw_plan)
        or data["plan_sha256"] != sha(raw_plan)
        or data["calibration_sha256"] != sha(calibration_path.read_bytes())
        or data["cohort"] != cohort
    ):
        raise ValueError("Actual collection or calibration binding changed")
    if cohort == "B" and before["prior_A_analysis_sha256"] != sha(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B collection lost original A binding")
    if (
        cohort == "B"
        and (calibration_root / "A-first-analysis.json").read_bytes()
        != (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B geometric calibration lost the same A phase binding")
    if (
        any(
            data[k]
            for k in [
                "candidate_calls",
                "new_candidate_holdouts",
                "TT_observer_clock_equivalence_certified",
                "physical_time_model_certified",
                "numerical_tubes_certified",
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Conditional diagnostics promoted to acceptance")
    queries = [q for q in plan["queries"] if q["cohort"] == cohort]
    if [q["id"] for q in data["queries"]] != [q["id"] for q in queries]:
        raise ValueError("OBSERVER query population changed")
    cases = {c["id"]: c for c in plan["cohorts"][cohort]}
    outputs = []
    steps = checks = 0
    for query, stored in zip(queries, data["queries"]):
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        if (
            sha(raw) != stored["raw_sha256"]
            or sha(raw) != receipt["raw_sha256"]
            or receipt["url"]
            != "https://ssd.jpl.nasa.gov/api/horizons.api?"
            + urllib.parse.urlencode(query["parameters"])
            or receipt["attempt"] != 1
            or receipt["verification_disabled"]
        ):
            raise ValueError("Raw response or actual query changed")
        if stored["status"] != "diagnosed":
            outputs.append(
                {
                    "id": query["id"],
                    "status": stored["status"],
                    "error": stored.get("error"),
                }
            )
            continue
        payload = json.loads(raw)
        if receipt["status"] != 200 or payload.get("error"):
            raise ValueError("Unavailable response promoted")
        text = payload["result"]
        prefix, body = text.split("$$SOE")
        body, _ = body.split("$$EOE")
        if not all(
            re.search(p, prefix)
            for p in [
                r"Target body name: Venus.*?\(299\).*?DE441",
                r"Center body name: Earth \(399\).*?DE441",
                r"Date__\(TT\)",
                r"Calendar mode\s*:\s*Gregorian",
                r"R\.A\._+\(ICRF\)",
                r"RA_\(ICRF-a-app\)",
                r"1-way_down_LT",
                r"delta,\s*deldot",
            ]
        ):
            raise ValueError("Independent OBSERVER header check failed")
        rows = [[v.strip() for v in c] for c in csv.reader(body.strip().splitlines())]
        if len(rows) != len(cases) or len(stored["rows"]) != len(cases):
            raise ValueError("OBSERVER rows were dropped")
        summary = {
            "id": query["id"],
            "primary": 0,
            "label_pass": 0,
            "profiles": {
                p: {
                    m: {
                        "all_not_refuted": 0,
                        "range_not_refuted": 0,
                        "light_time_not_refuted": 0,
                        "direction_not_refuted": 0,
                        "unknown": 0,
                    }
                    for m in plan["source_models"]
                }
                for p in plan["numerical_tube_profiles"]
            },
        }
        seen = set()
        for cells, record in zip(rows, stored["rows"]):
            near = [
                c
                for c in cases.values()
                if abs(Q(cells[1]) - Q(c["nominal_JD"])) * 86400
                <= Q(plan["row_assignment_radius_seconds"])
            ]
            if len(cells) != 12 or cells[-1] or len(near) != 1:
                raise ValueError("Invalid raw OBSERVER row")
            case = near[0]
            cid = case["id"]
            if (
                cid in seen
                or record["case_id"] != cid
                or record["role"] != case["role"]
                or record["astrometric_angles"] != cells[4:6]
                or record["apparent_angles"] != cells[9:11]
                or record["range_AU"] != cells[6]
                or record["deldot_km_per_second"] != cells[7]
                or record["light_time_minutes"] != cells[8]
            ):
                raise ValueError("Raw case or quantity identity changed")
            seen.add(cid)
            error = (Q(cells[1]) - Q(case["nominal_JD"])) * 86400
            label_pass = (
                abs(error) <= Q(plan["returned_label_match_budget_days"]) * 86400
            )
            cal = calibrations[query["id"]][cid]
            if (
                record["printed_JD"] != cells[1]
                or Q(record["label_error_seconds"]) != error
                or record["original_label_budget_pass"] != label_pass
                or record["calibration_original_label_pass"]
                != cal["original_label_budget_pass"]
            ):
                raise ValueError("Label line or geometric calibration identity changed")
            primary = case["role"] != "auxiliary_not_primary"
            summary["primary"] += primary
            summary["label_pass"] += primary and label_pass
            source = Source(run / "source-records", case["window_index"])
            for profile, settings in plan["numerical_tube_profiles"].items():
                result = record["profiles"][profile]
                calibration = cal["profiles"][profile]
                if result["calibration_all_six_not_refuted"] != calibration.get(
                    "all_six_compatible", False
                ):
                    raise ValueError(
                        "Original geometric state contradiction was hidden"
                    )
                if calibration["status"] != "bracketed":
                    if result.get("status") != "calibration_unknown":
                        raise ValueError("Unknown calibration promoted")
                    continue
                if result["reception_JD_TDB"] != calibration["effective_JD"] or set(
                    result["models"]
                ) != set(plan["source_models"]):
                    raise ValueError(
                        "Reception interval or source hypothesis set changed"
                    )
                reception = rounded(*parse(calibration["effective_JD"]), scale=1 << 256)
                obs = {
                    k: observed(record[k], settings["extra_binary64_ULPs"])
                    for k in ("range_AU", "light_time_minutes")
                }
                if {k: parse(v) for k, v in result["observed_bounds"].items()} != obs:
                    raise ValueError("Observation noise tube changed")
                direction = observed_direction(
                    record["astrometric_angles"], settings["extra_binary64_ULPs"]
                )
                for actual, declared in zip(
                    direction, result["observed_direction_ICRF"]
                ):
                    cover(actual, declared)
                for model in plan["source_models"]:
                    row = result["models"][model]
                    count = summary["profiles"][profile][model]
                    if row.get("status") == "source_model_unknown":
                        count["unknown"] += primary
                        continue
                    n, c = model_proof(source, reception, model, row, plan)
                    steps += n
                    checks += c
                    if (
                        not row["deldot_not_assessed"]
                        or not row["apparent_angles_not_assessed"]
                    ):
                        raise ValueError("Unassessed returned quantities promoted")
                    expected = {k: intersects(parse(row[k]), obs[k]) for k in obs}
                    expected["astrometric_direction_components"] = [
                        intersects(parse(a), parse(b))
                        for a, b in zip(
                            row["direction_ICRF"], result["observed_direction_ICRF"]
                        )
                    ]
                    all_ok = (
                        expected["range_AU"]
                        and expected["light_time_minutes"]
                        and all(expected["astrometric_direction_components"])
                    )
                    if (
                        row["checks"] != expected
                        or row["all_selected_observables_not_refuted"] != all_ok
                    ):
                        raise ValueError(
                            "Failed source observable or conditional score changed"
                        )
                    count["all_not_refuted"] += primary and all_ok
                    count["range_not_refuted"] += primary and expected["range_AU"]
                    count["light_time_not_refuted"] += (
                        primary and expected["light_time_minutes"]
                    )
                    count["direction_not_refuted"] += primary and all(
                        expected["astrometric_direction_components"]
                    )
        if seen != set(cases):
            raise ValueError("Original primary population changed")
        outputs.append(summary)
    return {
        "method_id": "independent_288bit_Bernstein_OBSERVER_transfer_proofs_v1",
        "cohort": cohort,
        "analysis_sha256": sha(data_bytes),
        "queries": outputs,
        "independent_interval_history_steps_checked": steps,
        "independent_model_enclosures_checked": checks,
        "geometric_calibration_replay_exit_code": calibration_replay["exit_code"],
        "exit_code": 0,
        "candidate_calls": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "TT_observer_clock_equivalence_certified": False,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run, args.cohort)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
