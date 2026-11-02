"""Independent Hall-subset label proof and exact-source ET grid controls.

No neighborhood producer, augmenting matcher or neighborhood parser imports.
Prior source targets define calibration requests, not fresh TT predictions.
"""

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_discrete_lt import measured
from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_emission_epoch import neighbor
from scripts.verify_astrodice_geometric_rr import (
    clock_proof,
    expected_geometry_plan,
    label,
)

FRAME_KEYS = {
    "support_JD",
    "derivative_bounds",
    "axis",
    "grid_hex",
    "physical_time_model_certified",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hall_matching(adjacency, slots):
    if len(adjacency) != slots:
        return False
    for a in adjacency:
        if any(not 0 <= v < slots for v in a):
            raise ValueError("Unplanned label slot")
    for mask in range(1, 1 << slots):
        neighbors = set()
        for i, a in enumerate(adjacency):
            if mask & (1 << i):
                neighbors.update(a)
        if len(neighbors) < mask.bit_count():
            return False
    return True


def expand_expected(baseline, plan):
    out = {k: v for k, v in baseline.items() if k != "queries"}
    out["queries"] = []
    size = plan["neighborhood_case_groups_per_batch"]
    for q in baseline["queries"]:
        primary = q["cases"][1:]
        for start in range(0, len(primary), size):
            cases = [q["cases"][0], *primary[start : start + size]]
            epochs = []
            for case in cases:
                raw = abs(float.fromhex(case["intended_ET_hex"]))
                step = (Q(neighbor(raw, True)) - Q(raw)) / 86400
                offsets = (
                    [0]
                    if case["role"] == "auxiliary_not_primary"
                    else plan["input_ET_ULP_offsets"]
                )
                for offset in offsets:
                    t = Q(case["nominal_JD"]) + offset * step
                    epochs.append(
                        {
                            "case_id": case["id"],
                            "offset": offset,
                            "epoch_JD": str(t),
                            "label": label(t, q["encoding"]),
                        }
                    )
            p = dict(q["parameters"])
            p["TLIST"] = "\n".join("'" + e["label"] + "'" for e in epochs)
            out["queries"].append(
                {
                    **q,
                    "id": q["id"] + "-N" + str(start // size),
                    "parameters": p,
                    "cases": cases,
                    "wire_epochs": epochs,
                }
            )
    return out


def raw_rows(raw, q, plan):
    data = json.loads(raw)
    if data.get("error"):
        raise ValueError("Service error is not a control response")
    prefix, content = data["result"].split("$$SOE")
    content, _ = content.split("$$EOE")
    identity = {"Earth": "399", "Venus": "299"}[q["body"]]
    patterns = [
        rf"Target body name: {q['body']}.*?\({identity}\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*GEOMETRIC cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTDB",
    ]
    if any(not re.search(p, prefix) for p in patterns):
        raise ValueError("Control table contract differs")
    result = []
    for index, line in enumerate(csv.reader(content.strip().splitlines())):
        row = [s.strip() for s in line]
        if (
            len(row) != 9
            or row[-1]
            or any(not math.isfinite(float(v)) for v in row[:1] + row[2:8])
        ):
            raise ValueError("Invalid control columns")
        near = [
            c
            for c in q["cases"]
            if abs(Q(row[0]) - Q(c["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1:
            raise ValueError("Control group is ambiguous")
        case = near[0]
        inputs = [e for e in q["wire_epochs"] if e["case_id"] == case["id"]]
        adjacency = [
            i
            for i, e in enumerate(inputs)
            if abs(Q(row[0]) - Q(e["epoch_JD"]))
            <= Q(plan["returned_label_match_budget_days"])
        ]
        result.append(
            {
                "row_index": index,
                "case_id": case["id"],
                "printed_JD": row[0],
                "printed_calendar": row[1],
                "printed_state": row[2:8],
                "compatible_request_slots": adjacency,
            }
        )
    return result


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    for n, h in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-queries.json").read_text()),
    }.items():
        if digest((run / n).read_bytes()) != h:
            raise ValueError("Frozen neighborhood input changed: " + n)
    seals = json.loads((run / "query-plans-before-source-results.json").read_text())
    for c in ("A", "B"):
        if (
            digest((run / ("geometry-" + c) / "plan-before-queries.json").read_bytes())
            != seals["query_plan_sha256"][c]
        ):
            raise ValueError("Pre-result query plan changed")
    child = run / ("geometry-" + cohort)
    rawq = (child / "plan-before-queries.json").read_bytes()
    query_plan = json.loads(rawq)
    baseline = expected_geometry_plan(run, cohort, plan, rawplan)
    if query_plan != expand_expected(baseline, plan):
        raise ValueError("Frozen neighborhood construction changed")
    before = json.loads((child / ("before-" + cohort + "-queries.json")).read_text())
    if before["plan_sha256"] != digest(rawq) or before["collector_sha256"] != digest(
        (run / "frozen-source/scripts/astrodice_vector_clock.py").read_bytes()
    ):
        raise ValueError("Control collection identity changed")
    if cohort == "B":
        binding = json.loads((run / "before-B-open-binding.json").read_text())
        if (
            binding["plan_sha256"] != digest(rawplan)
            or binding["A_analysis_sha256"]
            != digest((run / "A-first-analysis.json").read_bytes())
            or binding["A_proof_sha256"]
            != digest((run / "A-independent-replay-first.json").read_bytes())
            or before["prior_A_analysis_sha256"] != binding["A_analysis_sha256"]
            or digest((child / "A-first-analysis.json").read_bytes())
            != binding["A_analysis_sha256"]
        ):
            raise ValueError("A-before-B neighborhood binding changed")
    raw = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(raw)
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != digest(rawplan)
        or data["query_plan_sha256"] != digest(rawq)
        or data["candidate_calls"]
        or data["new_candidate_holdouts"]
        or data["new_TT_source_conditions"]
        or data["physical_time_model_certified"]
        or data["full_goal_complete"]
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Input controls promoted to acceptance")
    if len(data["queries"]) != len(query_plan["queries"]):
        raise ValueError("Control query omitted")
    stats = {
        p: {
            k: 0
            for k in (
                "primary_target_groups",
                "target_observed_groups",
                "qualified_target_groups",
                "label_matching_groups",
                "population_incomplete_groups",
                "target_rows",
            )
        }
        for p in plan["numerical_tube_profiles"]
    }
    paired = {p: {} for p in plan["numerical_tube_profiles"]}
    points = 0
    for q, saved in zip(query_plan["queries"], data["queries"]):
        rawv, receipt = wire(child, q)
        if receipt["status"] != 200:
            raise ValueError("Unavailable control table")
        rows = raw_rows(rawv, q, plan)
        actual = Counter(r["case_id"] for r in rows)
        expected = Counter(e["case_id"] for e in q["wire_epochs"])
        complete = actual == expected
        if {
            k: saved[k]
            for k in ("id", "body", "encoding", "complete_population", "raw_sha256")
        } != {
            "id": q["id"],
            "body": q["body"],
            "encoding": q["encoding"],
            "complete_population": complete,
            "raw_sha256": digest(rawv),
        } or len(
            saved["groups"]
        ) != len(
            q["cases"]
        ):
            raise ValueError("Control population or identity changed")
        for case, group in zip(q["cases"], saved["groups"]):
            members = [r for r in rows if r["case_id"] == case["id"]]
            inputs = [e for e in q["wire_epochs"] if e["case_id"] == case["id"]]
            matching = hall_matching(
                [r["compatible_request_slots"] for r in members], len(inputs)
            )
            if (
                {
                    k: group[k]
                    for k in (
                        "case_id",
                        "role",
                        "expected_rows",
                        "returned_rows",
                        "complete_label_matching",
                    )
                }
                != {
                    "case_id": case["id"],
                    "role": case["role"],
                    "expected_rows": len(inputs),
                    "returned_rows": len(members),
                    "complete_label_matching": matching,
                }
                or len(group["rows"]) != len(members)
                or set(group["profiles"]) != set(plan["numerical_tube_profiles"])
            ):
                raise ValueError("Control group, label matching or profile changed")
            frame = group["clock_frame"]
            if not members:
                if frame is not None:
                    raise ValueError("Clock frame without response rows")
            elif not isinstance(frame, dict) or set(frame) - FRAME_KEYS:
                raise ValueError("Control clock frame differs")
            for row, record in zip(members, group["rows"]):
                if {k: record[k] for k in row} != row or set(record["profiles"]) != set(
                    plan["numerical_tube_profiles"]
                ):
                    raise ValueError("Control raw row changed")
                for p, clock in record["profiles"].items():
                    if set(clock) & FRAME_KEYS:
                        raise ValueError("Per-row override of shared source support")
                    points += clock_proof(
                        run / "source-records",
                        case,
                        row,
                        q["body"],
                        p,
                        {**frame, **clock},
                        plan,
                    )
            for p, settings in plan["numerical_tube_profiles"].items():
                hits = [
                    r
                    for r in group["rows"]
                    if r["profiles"][p].get("unique_at_intended_epoch", False)
                ]
                hull = None
                if hits:
                    b = [
                        [
                            measured(s, settings["extra_binary64_ULPs"])
                            for s in r["printed_state"]
                        ]
                        for r in hits
                    ]
                    hull = [
                        [str(min(v[i][0] for v in b)), str(max(v[i][1] for v in b))]
                        for i in range(6)
                    ]
                qualified = complete and matching and bool(hits)
                if group["profiles"][p] != {
                    "target_row_indices": [r["row_index"] for r in hits],
                    "target_observed": bool(hits),
                    "control_qualified": qualified,
                    "all_target_state_hull": hull,
                    "physical_or_internal_algorithm_certified": False,
                }:
                    raise ValueError(
                        "Target selection, hull or control qualification changed"
                    )
                if case["role"] == "auxiliary_not_primary":
                    continue
                s = stats[p]
                s["primary_target_groups"] += 1
                s["target_observed_groups"] += bool(hits)
                s["qualified_target_groups"] += qualified
                s["label_matching_groups"] += matching
                s["population_incomplete_groups"] += not complete
                s["target_rows"] += len(hits)
                paired[p].setdefault((q["LT_query"], case["id"]), {})[
                    q["body"]
                ] = qualified
    pairs = {
        p: {
            "primary_pairs": len(rows),
            "both_controls_qualified": sum(
                set(v) == {"Earth", "Venus"} and all(v.values()) for v in rows.values()
            ),
        }
        for p, rows in paired.items()
    }
    return {
        "method": "independent_Hall_labels_source_ET_neighborhood_v1",
        "cohort": cohort,
        "analysis_sha256": digest(raw),
        "profiles": stats,
        "paired_controls": pairs,
        "clock_candidates_checked": points,
        "exit_code": 0,
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "new_TT_source_conditions": 0,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    with a.output.open("x") as f:
        json.dump(verify(a.run, a.cohort), f, indent=2)
        f.write("\n")
