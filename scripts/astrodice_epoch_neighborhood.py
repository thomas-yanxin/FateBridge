"""Frozen input-neighborhood controls for reaching a source ET grid point.

All returned rows are retained. Repeated time labels use complete bipartite
label matching; source matches never override failed population/label gates.
"""

import argparse
import csv
import json
import math
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_geometric_rr import diagnose, epoch_label, geometry_plan
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube

FRAME_KEYS = (
    "support_JD",
    "derivative_bounds",
    "axis",
    "grid_hex",
    "physical_time_model_certified",
)


def perfect_matching(adjacency, slots):
    if len(adjacency) != slots:
        return False
    owners = {}

    def augment(row, seen):
        for slot in adjacency[row]:
            if not 0 <= slot < slots:
                raise ValueError("Label slot outside frozen input set")
            if slot in seen:
                continue
            seen.add(slot)
            if slot not in owners or augment(owners[slot], seen):
                owners[slot] = row
                return True
        return False

    return all(augment(row, set()) for row in range(len(adjacency)))


def expand_plan(baseline, plan):
    out = {k: v for k, v in baseline.items() if k != "queries"}
    out["queries"] = []
    for query in baseline["queries"]:
        auxiliary, *primary = query["cases"]
        for start in range(0, len(primary), plan["neighborhood_case_groups_per_batch"]):
            groups = [
                auxiliary,
                *primary[start : start + plan["neighborhood_case_groups_per_batch"]],
            ]
            epochs = []
            for case in groups:
                center = Q(case["nominal_JD"])
                offsets = (
                    [0]
                    if case["role"] == "auxiliary_not_primary"
                    else plan["input_ET_ULP_offsets"]
                )
                step = Q(math.ulp(float.fromhex(case["intended_ET_hex"]))) / 86400
                for offset in offsets:
                    epoch = center + offset * step
                    epochs.append(
                        {
                            "case_id": case["id"],
                            "offset": offset,
                            "epoch_JD": str(epoch),
                            "label": epoch_label(epoch, query["encoding"]),
                        }
                    )
            params = dict(query["parameters"])
            params["TLIST"] = "\n".join("'" + e["label"] + "'" for e in epochs)
            out["queries"].append(
                {
                    **query,
                    "id": query["id"]
                    + "-N"
                    + str(start // plan["neighborhood_case_groups_per_batch"]),
                    "parameters": params,
                    "cases": groups,
                    "wire_epochs": epochs,
                }
            )
    return out


def build(run, cohort):
    plan, _ = check_inputs(run)
    return expand_plan(geometry_plan(run, cohort), plan)


def parse_rows(raw, query, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Neighborhood service error: " + str(payload["error"]))
    prefix, text = payload["result"].split("$$SOE")
    text, _ = text.split("$$EOE")
    body = query["body"]
    ident = {"Earth": "399", "Venus": "299"}[body]
    import re

    patterns = [
        rf"Target body name: {body}.*?\({ident}\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*GEOMETRIC cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTDB",
    ]
    if any(not re.search(p, prefix) for p in patterns):
        raise ValueError("Neighborhood geometry header differs")
    output = []
    for index, cells in enumerate(csv.reader(text.strip().splitlines())):
        cells = [v.strip() for v in cells]
        if len(cells) != 9 or cells[-1]:
            raise ValueError("Neighborhood vector columns differ")
        for s in cells[:1] + cells[2:8]:
            if not math.isfinite(float(s)):
                raise ValueError("Nonfinite neighborhood component")
        near = [
            c
            for c in query["cases"]
            if abs(Q(cells[0]) - Q(c["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1:
            raise ValueError("Neighborhood case group ambiguous")
        case = near[0]
        inputs = [e for e in query["wire_epochs"] if e["case_id"] == case["id"]]
        matches = [
            i
            for i, e in enumerate(inputs)
            if abs(Q(cells[0]) - Q(e["epoch_JD"]))
            <= Q(plan["returned_label_match_budget_days"])
        ]
        output.append(
            {
                "row_index": index,
                "case_id": case["id"],
                "printed_JD": cells[0],
                "printed_calendar": cells[1],
                "printed_state": cells[2:8],
                "compatible_request_slots": matches,
            }
        )
    return output


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    child = run / ("geometry-" + cohort)
    gp = json.loads((child / "plan-before-queries.json").read_text())
    output = {
        "cohort": cohort,
        "plan_sha256": digest,
        "query_plan_sha256": sha((child / "plan-before-queries.json").read_bytes()),
        "queries": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "new_TT_source_conditions": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "full_goal_complete": False,
    }
    for query in gp["queries"]:
        raw = (child / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (child / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        if receipt["status"] != 200 or sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Unavailable or changed neighborhood response")
        rows = parse_rows(raw, query, plan)
        counts = Counter(r["case_id"] for r in rows)
        expected = Counter(e["case_id"] for e in query["wire_epochs"])
        complete = counts == expected
        groups = []
        for case in query["cases"]:
            members = [r for r in rows if r["case_id"] == case["id"]]
            inputs = [e for e in query["wire_epochs"] if e["case_id"] == case["id"]]
            label_match = perfect_matching(
                [r["compatible_request_slots"] for r in members], len(inputs)
            )
            frame = None
            saved_rows = []
            for row in members:
                profiles = {}
                for p in plan["numerical_tube_profiles"]:
                    clock = diagnose(
                        run / "source-records", case, row, query["body"], p, plan
                    )
                    f = {k: clock[k] for k in FRAME_KEYS if k in clock}
                    if frame is None:
                        frame = f
                    if frame != f:
                        raise ValueError(
                            "Frozen source frame changed across repeated rows"
                        )
                    profiles[p] = {
                        k: v for k, v in clock.items() if k not in FRAME_KEYS
                    }
                saved_rows.append({**row, "profiles": profiles})
            summaries = {}
            for p, settings in plan["numerical_tube_profiles"].items():
                hits = [
                    r
                    for r in saved_rows
                    if r["profiles"][p].get("unique_at_intended_epoch", False)
                ]
                hull = None
                if hits:
                    bounds = [
                        [
                            tube(s, settings["extra_binary64_ULPs"])
                            for s in r["printed_state"]
                        ]
                        for r in hits
                    ]
                    hull = [
                        [
                            str(min(b[i][0] for b in bounds)),
                            str(max(b[i][1] for b in bounds)),
                        ]
                        for i in range(6)
                    ]
                summaries[p] = {
                    "target_row_indices": [r["row_index"] for r in hits],
                    "target_observed": bool(hits),
                    "control_qualified": complete and label_match and bool(hits),
                    "all_target_state_hull": hull,
                    "physical_or_internal_algorithm_certified": False,
                }
            groups.append(
                {
                    "case_id": case["id"],
                    "role": case["role"],
                    "expected_rows": len(inputs),
                    "returned_rows": len(members),
                    "complete_label_matching": label_match,
                    "clock_frame": frame,
                    "rows": saved_rows,
                    "profiles": summaries,
                }
            )
        output["queries"].append(
            {
                "id": query["id"],
                "body": query["body"],
                "encoding": query["encoding"],
                "complete_population": complete,
                "raw_sha256": sha(raw),
                "groups": groups,
            }
        )
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["build", "analyze"])
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    a = p.parse_args()
    if a.action == "build":
        child = a.run / ("geometry-" + a.cohort)
        child.mkdir()
        save(child / "plan-before-queries.json", build(a.run, a.cohort))
    else:
        save(a.run / (a.cohort + "-first-analysis.json"), analyze(a.run, a.cohort))
