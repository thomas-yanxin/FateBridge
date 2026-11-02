"""Paired Earth/Venus effective source clocks and conditional emission transfer.

Maintenance source diagnosis, not certified physical clocks or acceptance.
Earth is 399, reconstructed from EMB minus geocentric Moon/(EMRAT+1).
"""

import argparse
import csv
import json
import math
import re
import struct
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_batch_binding import matching_time_batches
from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_de441_records import group_state, header
from scripts.astrodice_emission_epoch import infer
from scripts.astrodice_observer_timescale import classify
from scripts.astrodice_vector_clock import check_inputs, inverse, save, sha, tube


def parse(raw, query, cases, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Service error: " + str(payload["error"]))
    body = query["body"]
    if body not in {"Earth", "Venus"}:
        raise ValueError("Unplanned body")
    expected_id = {"Earth": "399", "Venus": "299"}[body]
    if query["parameters"]["COMMAND"] != "'" + expected_id + "'":
        raise ValueError("Body command differs")
    prefix, text = payload["result"].split("$$SOE")
    text, _ = text.split("$$EOE")
    identifiers = "399" if body == "Earth" else "(?:299|2)"
    for pattern in [
        rf"Target body name: {body}.*?\({identifiers}\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*GEOMETRIC cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTT",
    ]:
        if re.search(pattern, prefix) is None:
            raise ValueError("Raw body/frame/time contract differs")
    rows = []
    seen = set()
    for cells in csv.reader(text.strip().splitlines()):
        c = [v.strip() for v in cells]
        if (
            len(c) != 9
            or c[-1]
            or not all(math.isfinite(float(v)) for v in c[:1] + c[2:8])
        ):
            raise ValueError("Unplanned vector columns or nonfinite state")
        epoch = Q(c[0])
        near = [
            v
            for v in cases
            if abs(epoch - Q(v["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Ambiguous vector row")
        case = near[0]
        seen.add(case["id"])
        error = epoch - Q(case["nominal_JD"])
        rows.append(
            {
                "case_id": case["id"],
                "role": case["role"],
                "nominal_JD": case["nominal_JD"],
                "printed_JD": c[0],
                "printed_calendar": c[1],
                "printed_state": c[2:8],
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {v["id"] for v in cases}:
        raise ValueError("Original vector cases missing")
    return rows


def exact_axis(source, window, epoch, body, axis):
    meta = header((source / "header.bin").read_bytes())
    raw = (source / f"record-responses/case-{window:02}.bin").read_bytes()
    records = [raw[i : i + 8144] for i in range(0, len(raw), 8144)]
    record = next(
        r
        for r in records
        if Q(struct.unpack_from("<d", r)[0])
        <= epoch
        < Q(struct.unpack_from("<d", r, 8)[0])
    )
    groups = (1,) if body == "Venus" else (2, 9)
    supports = []
    for g in groups:
        _, _, parts = meta["pointers"][g]
        start, end = map(Q, struct.unpack_from("<2d", record))
        width = (end - start) / parts
        start += ((epoch - start) // width) * width
        supports.append((start, start + width))
    low, high = max(v[0] for v in supports), min(v[1] for v in supports)

    def evaluate(t):
        if not low <= t < high:
            raise ValueError("Inverse left an original source cell")
        values = [group_state(meta, record, t, g)[axis] for g in groups]
        value = (
            values[0]
            if body == "Venus"
            else values[0] - values[1] / (1 + Q(meta["earth_moon_mass_ratio"]))
        )
        return value / Q(meta["au_km"])

    return evaluate


def diagnose(source, case, row, body, plan):
    epoch = Q(case["nominal_JD"])
    radius = Q(plan["source_inverse_search_radius_seconds"]) / 86400
    reader = Reader(source, case["window_index"])
    broad = reader.state(A(I(epoch - radius, epoch + radius), 1), body)
    derivatives = [v.d.bounds() for v in broad[:3]]
    conditioning = [min(abs(a), abs(b)) if a * b > 0 else Q(0) for a, b in derivatives]
    axis = max(range(3), key=conditioning.__getitem__)
    if conditioning[axis] < Q(plan["minimum_monotone_position_derivative_AU_per_day"]):
        raise ValueError("No well-conditioned source axis")
    evaluate = exact_axis(source, case["window_index"], epoch, body, axis)
    result = {
        **row,
        "axis": axis,
        "derivative_bounds": [list(map(str, v)) for v in derivatives],
        "profiles": {},
    }
    for name, settings in plan["numerical_tube_profiles"].items():
        bounds = [
            tube(v, settings["extra_binary64_ULPs"]) for v in row["printed_state"]
        ]
        item = inverse(
            evaluate,
            epoch,
            bounds[axis],
            derivatives[axis][0] > 0,
            radius,
            plan["source_inverse_bisection_iterations"],
        )
        if item["status"] == "bracketed":
            a, b = map(Q, item["effective_JD"])
            states = reader.state(A(I(a, b), 1), body)
            boxes = [v.v.bounds() for v in states]
            flags = [x <= v and u <= y for (x, y), (u, v) in zip(boxes, bounds)]
            item.update(
                source_state_bounds=[list(map(str, v)) for v in boxes],
                component_compatible=flags,
                all_six_compatible=all(flags),
            )
        result["profiles"][name] = item
    return result


def pair(reader, earth, venus, profile, plan):
    e, v = earth["profiles"][profile], venus["profiles"][profile]
    if e["status"] != "bracketed" or v["status"] != "bracketed":
        return {"status": "calibration_unknown"}
    ea, eb = map(Q, e["effective_JD"])
    va, vb = map(Q, v["effective_JD"])
    a, b = max(ea, va), min(eb, vb)
    result = {
        "Earth_minus_Venus_seconds": [str((ea - vb) * 86400), str((eb - va) * 86400)],
        "Earth_six_not_refuted": e["all_six_compatible"],
        "Venus_six_not_refuted": v["all_six_compatible"],
    }
    if a > b:
        return {**result, "status": "disjoint"}
    checks = {}
    for body, row in [("Earth", earth), ("Venus", venus)]:
        states = reader.state(A(I(a, b), 1), body)
        boxes = [x.v.bounds() for x in states]
        observed = [
            tube(x, plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"])
            for x in row["printed_state"]
        ]
        flags = [x <= v and u <= y for (x, y), (u, v) in zip(boxes, observed)]
        checks[body] = {
            "source_state_bounds": [list(map(str, x)) for x in boxes],
            "component_compatible": flags,
        }
    return {
        **result,
        "status": "intersecting",
        "common_JD": list(map(str, (a, b))),
        "common_checks": checks,
        "joint_necessary_not_refuted": e["all_six_compatible"]
        and v["all_six_compatible"]
        and all(all(c["component_compatible"]) for c in checks.values()),
    }


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    result = {
        "batch_binding_version": "exact_wire_time_batch_v1",
        "plan_sha256": digest,
        "cohort": cohort,
        "vectors": [],
        "pairs": [],
        "transfers": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "internal_emission_algorithm_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    cases = plan["cohorts"][cohort]
    for q in plan["queries"]:
        if q["cohort"] != cohort or q["kind"] != "vector":
            continue
        raw = (run / "responses" / (q["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (q["id"] + ".receipt.json")).read_text()
        )
        if receipt["status"] != 200 or sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Unavailable or changed raw vector")
        rows = parse(raw, q, cases, plan)
        result["vectors"].append(
            {
                "id": q["id"],
                "body": q["body"],
                "encoding": q["encoding"],
                "raw_sha256": sha(raw),
                "rows": [
                    diagnose(
                        run / "source-records",
                        next(c for c in cases if c["id"] == row["case_id"]),
                        row,
                        q["body"],
                        plan,
                    )
                    for row in rows
                ],
            }
        )
    for encoding in ("JD", "MJD", "CAL"):
        groups = {
            g["body"]: {r["case_id"]: r for r in g["rows"]}
            for g in result["vectors"]
            if g["encoding"] == encoding
        }
        for case in cases:
            e, v = groups["Earth"][case["id"]], groups["Venus"][case["id"]]
            result["pairs"].append(
                {
                    "case_id": case["id"],
                    "nominal_JD": case["nominal_JD"],
                    "encoding": encoding,
                    "role": case["role"],
                    "profiles": {
                        p: pair(
                            Reader(run / "source-records", case["window_index"]),
                            e,
                            v,
                            p,
                            plan,
                        )
                        for p in plan["numerical_tube_profiles"]
                    },
                }
            )
    specs = plan["transfer_groups"][cohort]
    for spec in specs:
        obsroot = run / spec["observation_root"]
        sp = json.loads((obsroot / "plan-before-queries.json").read_text())
        osc = sp["cohorts"][spec["cohort"]]
        for q in sp["queries"]:
            if (
                q["cohort"] != spec["cohort"]
                or q["time_type"] != "TT"
                or (q.get("kind") and q["kind"] != "observer")
            ):
                continue
            raw = (obsroot / "responses" / (q["id"] + ".raw")).read_bytes()
            receipt = json.loads(
                (obsroot / "responses" / (q["id"] + ".receipt.json")).read_text()
            )
            if sha(raw) != receipt["raw_sha256"]:
                raise ValueError("Original observer changed")
            parsed = classify(raw, receipt["status"], q, osc, sp)
            bindings = {
                body: matching_time_batches(
                    q,
                    next(
                        v
                        for v in plan["queries"]
                        if v["cohort"] == cohort
                        and v["kind"] == "vector"
                        and v["encoding"] == q["encoding"]
                        and v["body"] == body
                    ),
                )
                for body in ("Earth", "Venus")
            }
            group = {
                **spec,
                "query_id": q["id"],
                "encoding": q["encoding"],
                "raw_sha256": sha(raw),
                "status": parsed["status"],
                "clock_time_batches_match": bindings,
                "rows": [],
            }
            if parsed["status"] == "supported":
                for row in parsed["rows"]:
                    case = next(c for c in osc if c["id"] == row["case_id"])
                    pc = next(
                        c for c in cases if Q(c["nominal_JD"]) == Q(case["nominal_JD"])
                    )
                    found = next(
                        p
                        for p in result["pairs"]
                        if p["encoding"] == q["encoding"] and p["case_id"] == pc["id"]
                    )
                    row["profiles"] = {}
                    for profile in plan["numerical_tube_profiles"]:
                        models = {}
                        for model in plan["transfer_receiver_models"]:
                            if model == "common_clock":
                                p = found["profiles"][profile]
                                cal = (
                                    {
                                        "status": "bracketed",
                                        "effective_JD": p["common_JD"],
                                        "all_six_compatible": p[
                                            "joint_necessary_not_refuted"
                                        ],
                                    }
                                    if p["status"] == "intersecting"
                                    else {
                                        "status": "common_clock_unknown",
                                        "all_six_compatible": False,
                                    }
                                )
                            else:
                                vg = next(
                                    g
                                    for g in result["vectors"]
                                    if g["encoding"] == q["encoding"]
                                    and g["body"] == model
                                )
                                cal = next(
                                    c for c in vg["rows"] if c["case_id"] == pc["id"]
                                )["profiles"][profile]
                            models[model] = {
                                "calibration": cal,
                                "inference": (
                                    infer(
                                        run / "source-records",
                                        case,
                                        row,
                                        cal,
                                        profile,
                                        plan,
                                    )
                                    if all(bindings.values())
                                    else {
                                        "status": "cross_batch_clock_unqualified",
                                        "calibration_all_six_not_refuted": cal.get(
                                            "all_six_compatible", False
                                        ),
                                    }
                                ),
                            }
                        row["profiles"][profile] = models
                    group["rows"].append(row)
            result["transfers"].append(group)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    save(
        args.output or args.run / (args.cohort + "-batch-bound-analysis.json"),
        analyze(args.run, args.cohort),
    )
