"""Independent exact-basis/Bernstein paired-clock and emission proofs.

No paired-clock producer, Clenshaw or interval AD imports. Shared DE441 dynamics
and declared printing tubes remain conditional, never physical certification.
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.parse
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_emission_epoch import exact_position, infer_proof
from scripts.verify_astrodice_observer_clock import Source, cover, parse, rounded
from scripts.verify_astrodice_observer_timescale import inspect
from scripts.verify_astrodice_vector_clock import observed_bounds


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(run, query):
    raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
    receipt = json.loads(
        (run / "responses" / (query["id"] + ".receipt.json")).read_text()
    )
    if (
        receipt["raw_sha256"] != digest(raw)
        or receipt["attempt"] != 1
        or receipt["verification_disabled"]
        or receipt["url"]
        != "https://ssd.jpl.nasa.gov/api/horizons.api?"
        + urllib.parse.urlencode(query["parameters"])
    ):
        raise ValueError("Raw query/transport identity differs")
    return raw, receipt


def raw_rows(raw, query, cases, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Service error cannot be a vector")
    text = payload["result"]
    prefix, rows = text.split("$$SOE")
    rows, _ = rows.split("$$EOE")
    body = query["body"]
    ids = {"Earth": "399", "Venus": "(?:299|2)"}
    if (
        body not in ids
        or query["parameters"]["COMMAND"] != {"Earth": "'399'", "Venus": "'299'"}[body]
    ):
        raise ValueError("Target identity differs")
    for expr in [
        rf"Target body name: {body}.*?\({ids[body]}\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*GEOMETRIC cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTT",
    ]:
        if not re.search(expr, prefix):
            raise ValueError("Independent frame/center/time header mismatch")
    output = []
    seen = set()
    for cells in csv.reader(rows.strip().splitlines()):
        c = [v.strip() for v in cells]
        if len(c) != 9 or c[-1]:
            raise ValueError("Original vector columns differ")
        near = [
            x
            for x in cases
            if abs(Q(c[0]) - Q(x["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Independent raw identity is ambiguous")
        case = near[0]
        seen.add(case["id"])
        output.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD": case["nominal_JD"],
                "printed_JD": c[0],
                "printed_calendar": c[1],
                "printed_state": c[2:8],
                "original_label_budget_pass": abs(Q(c[0]) - Q(case["nominal_JD"]))
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in cases}:
        raise ValueError("Original vector coverage reduced")
    return output


def vector_proof(run, body, case, original, record, plan):
    if {k: record[k] for k in original} != original:
        raise ValueError("Printed vector or role changed")
    source = Source(run / "source-records", case["window_index"])
    nominal = Q(case["nominal_JD"])
    radius = Q(plan["source_inverse_search_radius_seconds"]) / 86400
    broad = source.state(
        rounded(nominal - radius, nominal + radius, scale=1 << 256), body
    )
    for actual, declared in zip(broad[3:], record["derivative_bounds"]):
        cover(actual, declared)
    declared = list(map(parse, record["derivative_bounds"]))
    conditioning = [min(abs(a), abs(b)) if a * b > 0 else Q(0) for a, b in declared]
    axis = max(range(3), key=conditioning.__getitem__)
    if axis != record["axis"] or conditioning[axis] < Q(
        plan["minimum_monotone_position_derivative_AU_per_day"]
    ):
        raise ValueError("Conditioned axis rule changed")
    if set(record["profiles"]) != set(plan["numerical_tube_profiles"]):
        raise ValueError("Profile omitted")
    checks = boxes = 0
    for name, profile in plan["numerical_tube_profiles"].items():
        item = record["profiles"][name]
        obs = [
            observed_bounds(x, profile["extra_binary64_ULPs"])
            for x in original["printed_state"]
        ]
        sign = 1 if declared[axis][0] > 0 else -1
        targets = obs[axis] if sign == 1 else (-obs[axis][1], -obs[axis][0])

        def evaluate(t):
            return (
                sign
                * exact_position(run / "source-records", case["window_index"], t, body)[
                    axis
                ]
            )

        if item["status"] != "bracketed":
            if item["status"] != "unbracketed" or not (
                evaluate(nominal - radius) > targets[0]
                or evaluate(nominal + radius) < targets[1]
            ):
                raise ValueError("Unbracketed status unproved")
            continue
        brackets = list(map(parse, item["boundary_brackets_JD"]))
        for (a, b), target in zip(brackets, targets):
            if not (
                nominal - radius <= a <= b <= nominal + radius
                and b - a
                == 2 * radius / 2 ** plan["source_inverse_bisection_iterations"]
                and evaluate(a) <= target <= evaluate(b)
            ):
                raise ValueError("Exact inverse endpoint failed")
            checks += 2
        lo, hi = brackets[0][0], brackets[1][1]
        if parse(item["effective_JD"]) != (lo, hi):
            raise ValueError("Source inverse interval changed")
        actual = source.state(rounded(lo, hi, scale=1 << 256), body)
        if len(item["source_state_bounds"]) != 6:
            raise ValueError("Source component dropped")
        for a, b in zip(actual, item["source_state_bounds"]):
            cover(a, b)
            boxes += 1
        flags = [
            a <= d and c <= b
            for (a, b), (c, d) in zip(map(parse, item["source_state_bounds"]), obs)
        ]
        if item["component_compatible"] != flags or item["all_six_compatible"] != all(
            flags
        ):
            raise ValueError("Source component contradiction hidden")
    return checks, boxes


def paired_proof(run, case, earth, venus, stored, profile, plan):
    e, v = earth["profiles"][profile], venus["profiles"][profile]
    if e["status"] != "bracketed" or v["status"] != "bracketed":
        if stored != {"status": "calibration_unknown"}:
            raise ValueError("Unavailable pair promoted")
        return 0
    ea, eb = parse(e["effective_JD"])
    va, vb = parse(v["effective_JD"])
    a, b = max(ea, va), min(eb, vb)
    expected = {
        "Earth_minus_Venus_seconds": [str((ea - vb) * 86400), str((eb - va) * 86400)],
        "Earth_six_not_refuted": e["all_six_compatible"],
        "Venus_six_not_refuted": v["all_six_compatible"],
    }
    if a > b:
        if stored != {**expected, "status": "disjoint"}:
            raise ValueError("Disjoint clocks hidden")
        return 0
    if (
        any(stored[k] != v for k, v in expected.items())
        or stored["status"] != "intersecting"
        or parse(stored["common_JD"]) != (a, b)
    ):
        raise ValueError("Common clock intersection changed")
    if set(stored["common_checks"]) != {"Earth", "Venus"}:
        raise ValueError("Paired source omitted")
    count = 0
    all_flags = []
    source = Source(run / "source-records", case["window_index"])
    for body, row in [("Earth", earth), ("Venus", venus)]:
        actual = source.state(rounded(a, b, scale=1 << 256), body)
        check = stored["common_checks"][body]
        if len(check["source_state_bounds"]) != 6:
            raise ValueError("Common component dropped")
        for x, y in zip(actual, check["source_state_bounds"]):
            cover(x, y)
            count += 1
        obs = [
            observed_bounds(
                x, plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
            )
            for x in row["printed_state"]
        ]
        flags = [
            a <= d and c <= b
            for (a, b), (c, d) in zip(map(parse, check["source_state_bounds"]), obs)
        ]
        if check["component_compatible"] != flags:
            raise ValueError("Joint source flag differs")
        all_flags.extend(flags)
    if stored["joint_necessary_not_refuted"] != (
        e["all_six_compatible"] and v["all_six_compatible"] and all(all_flags)
    ):
        raise ValueError("Necessary pair condition promoted")
    return count


def verify(run, cohort):
    planraw = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(planraw)
    before = json.loads((run / ("before-" + cohort + "-queries.json")).read_text())
    if cohort == "B" and before["prior_A_analysis_sha256"] != digest(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("B lost A binding")
    analysisraw = (run / (cohort + "-batch-bound-analysis.json")).read_bytes()
    data = json.loads(analysisraw)
    if (
        data["cohort"] != cohort
        or data.get("batch_binding_version") != "exact_wire_time_batch_v1"
        or data["plan_sha256"] != digest(planraw)
        or any(
            data[k]
            for k in [
                "candidate_calls",
                "new_candidate_holdouts",
                "physical_time_model_certified",
                "numerical_tubes_certified",
                "internal_emission_algorithm_certified",
                "full_goal_complete",
            ]
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Source diagnosis promoted to acceptance")
    cases = plan["cohorts"][cohort]
    queries = [
        q for q in plan["queries"] if q["cohort"] == cohort and q["kind"] == "vector"
    ]
    if [q["id"] for q in queries] != [q["id"] for q in data["vectors"]]:
        raise ValueError("Vector query coverage changed")
    endpoints = boxes = emission_endpoints = candidates = 0
    vector_summary = []
    for q, g in zip(queries, data["vectors"]):
        raw, receipt = wire(run, q)
        if (
            receipt["status"] != 200
            or g["raw_sha256"] != digest(raw)
            or g["body"] != q["body"]
            or g["encoding"] != q["encoding"]
        ):
            raise ValueError("Vector provenance differs")
        originals = raw_rows(raw, q, cases, plan)
        if len(originals) != len(g["rows"]):
            raise ValueError("Vector row omitted")
        stats = {
            p: {"primary": 0, "label_pass": 0, "six_not_refuted": 0}
            for p in plan["numerical_tube_profiles"]
        }
        for original, record in zip(originals, g["rows"]):
            case = next(c for c in cases if c["id"] == original["case_id"])
            n, k = vector_proof(run, q["body"], case, original, record, plan)
            endpoints += n
            boxes += k
            if case["role"] != "auxiliary_not_primary":
                for p, s in stats.items():
                    s["primary"] += 1
                    s["label_pass"] += original["original_label_budget_pass"]
                    s["six_not_refuted"] += record["profiles"][p].get(
                        "all_six_compatible", False
                    )
        vector_summary.append({"id": q["id"], "profiles": stats})
    expected_pairs = [(e, c) for e in ["JD", "MJD", "CAL"] for c in cases]
    if len(data["pairs"]) != len(expected_pairs):
        raise ValueError("Paired case omitted")
    pair_summary = {
        p: {
            "primary": 0,
            "intersecting": 0,
            "disjoint": 0,
            "calibration_unknown": 0,
            "joint_not_refuted": 0,
        }
        for p in plan["numerical_tube_profiles"]
    }
    for pair, (encoding, case) in zip(data["pairs"], expected_pairs):
        if any(
            pair[k] != v
            for k, v in {
                "case_id": case["id"],
                "nominal_JD": case["nominal_JD"],
                "encoding": encoding,
                "role": case["role"],
            }.items()
        ) or set(pair["profiles"]) != set(plan["numerical_tube_profiles"]):
            raise ValueError("Pair identity changed")
        groups = {
            g["body"]: next(r for r in g["rows"] if r["case_id"] == case["id"])
            for g in data["vectors"]
            if g["encoding"] == encoding
        }
        for p, item in pair["profiles"].items():
            boxes += paired_proof(
                run, case, groups["Earth"], groups["Venus"], item, p, plan
            )
            if case["role"] != "auxiliary_not_primary":
                s = pair_summary[p]
                s["primary"] += 1
                s[item["status"]] += 1
                s["joint_not_refuted"] += item.get("joint_necessary_not_refuted", False)
    transfers = []
    expected = []
    for spec in plan["transfer_groups"][cohort]:
        sp = json.loads(
            (run / spec["observation_root"] / "plan-before-queries.json").read_text()
        )
        expected.extend(
            (spec, sp, q)
            for q in sp["queries"]
            if q["cohort"] == spec["cohort"]
            and q["time_type"] == "TT"
            and q.get("kind", "observer") == "observer"
        )
    if len(data["transfers"]) != len(expected):
        raise ValueError("Transfer group omitted")
    for group, (spec, sp, q) in zip(data["transfers"], expected):
        raw, receipt = wire(run / spec["observation_root"], q)
        obs = inspect(raw, receipt["status"], q, sp["cohorts"][spec["cohort"]], sp)
        keys = (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        )
        bindings = {}
        for body in ("Earth", "Venus"):
            vector_query = next(
                v
                for v in plan["queries"]
                if v["cohort"] == cohort
                and v["kind"] == "vector"
                and v["encoding"] == q["encoding"]
                and v["body"] == body
            )
            if any(
                not isinstance(parameters.get(k), str) or not parameters[k].strip()
                for parameters in (q["parameters"], vector_query["parameters"])
                for k in keys
            ):
                raise ValueError("Incomplete explicit time input batch")
            bindings[body] = all(
                q["parameters"][k] == vector_query["parameters"][k] for k in keys
            )
        if group["clock_time_batches_match"] != bindings:
            raise ValueError("Cross-batch source-clock transfer was promoted")
        if any(
            group[k] != v
            for k, v in {
                **spec,
                "query_id": q["id"],
                "encoding": q["encoding"],
                "raw_sha256": digest(raw),
                "status": obs["status"],
            }.items()
        ):
            raise ValueError("Original observer group changed")
        if obs["status"] != "supported":
            if group["rows"]:
                raise ValueError("Unavailable observation promoted")
            transfers.append({"query": q["id"], "status": obs["status"]})
            continue
        if len(obs["rows"]) != len(group["rows"]):
            raise ValueError("Transfer row omitted")
        stats = {
            p: {
                m: {
                    "primary": 0,
                    "inferred": 0,
                    "statuses": {},
                    "ET_unique": 0,
                    "ET_refuted": 0,
                    "ET_multi_or_unknown": 0,
                }
                for m in plan["transfer_receiver_models"]
            }
            for p in plan["numerical_tube_profiles"]
        }
        for row, record in zip(obs["rows"], group["rows"]):
            if {k: record[k] for k in row} != row or set(record["profiles"]) != set(
                plan["numerical_tube_profiles"]
            ):
                raise ValueError("Raw transfer identity differs")
            case = next(
                c for c in sp["cohorts"][spec["cohort"]] if c["id"] == row["case_id"]
            )
            pc = next(c for c in cases if Q(c["nominal_JD"]) == Q(case["nominal_JD"]))
            paired = next(
                x
                for x in data["pairs"]
                if x["case_id"] == pc["id"] and x["encoding"] == q["encoding"]
            )
            for p, models in record["profiles"].items():
                if set(models) != set(plan["transfer_receiver_models"]):
                    raise ValueError("Receiver model omitted")
                for model, value in models.items():
                    if model == "common_clock":
                        item = paired["profiles"][p]
                        cal = (
                            {
                                "status": "bracketed",
                                "effective_JD": item["common_JD"],
                                "all_six_compatible": item[
                                    "joint_necessary_not_refuted"
                                ],
                            }
                            if item["status"] == "intersecting"
                            else {
                                "status": "common_clock_unknown",
                                "all_six_compatible": False,
                            }
                        )
                    else:
                        vg = next(
                            g
                            for g in data["vectors"]
                            if g["body"] == model and g["encoding"] == q["encoding"]
                        )
                        cal = next(r for r in vg["rows"] if r["case_id"] == pc["id"])[
                            "profiles"
                        ][p]
                    if (
                        value["calibration"] != cal
                        or value["inference"]["status"] == "source_model_unknown"
                    ):
                        raise ValueError(
                            "Receiver calibration changed or unchecked unknown"
                        )
                    if not all(bindings.values()):
                        if value["inference"] != {
                            "status": "cross_batch_clock_unqualified",
                            "calibration_all_six_not_refuted": cal.get(
                                "all_six_compatible", False
                            ),
                        }:
                            raise ValueError(
                                "Unqualified clock batch promoted to an emission result"
                            )
                        n, k = 0, 0
                    else:
                        n, k = infer_proof(
                            run, case, row, cal, p, value["inference"], plan
                        )
                    emission_endpoints += n
                    candidates += k
                    if case["role"] == "auxiliary_not_primary":
                        continue
                    s = stats[p][model]
                    s["primary"] += 1
                    status = value["inference"]["status"]
                    s["statuses"][status] = s["statuses"].get(status, 0) + 1
                    if status == "inferred":
                        s["inferred"] += 1
                        et = value["inference"]["lattices"][
                            "seconds_from_J2000_binary64"
                        ]
                        s["ET_unique"] += et["unique_not_refuted"]
                        s["ET_refuted"] += et["conditional_refuted"]
                        s["ET_multi_or_unknown"] += not (
                            et["unique_not_refuted"] or et["conditional_refuted"]
                        )
        transfers.append({**spec, "query": q["id"], "profiles": stats})
    return {
        "method": "independent_direct_basis_Bernstein_paired_receiver_clock_v1",
        "cohort": cohort,
        "analysis_sha256": digest(analysisraw),
        "vectors": vector_summary,
        "pairs": pair_summary,
        "transfers": transfers,
        "geometric_inverse_endpoint_checks": endpoints,
        "source_enclosure_checks": boxes,
        "emission_inverse_endpoint_checks": emission_endpoints,
        "emission_candidate_enclosure_checks": candidates,
        "exit_code": 0,
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x") as f:
        json.dump(verify(args.run, args.cohort), f, indent=2)
        f.write("\n")
