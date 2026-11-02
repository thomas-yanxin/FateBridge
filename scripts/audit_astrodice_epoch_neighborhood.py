"""Read-only transport/population audit after the first strict B failure.

HTTP failures stay unavailable, the original numerical failure is never
regraded, and posthoc separator/single-input controls remain development only.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.astrodice_epoch_neighborhood import parse_rows, perfect_matching
from scripts.astrodice_geometric_rr import diagnose
from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_epoch_neighborhood import hall_matching, raw_rows
from scripts.verify_astrodice_geometric_rr import clock_proof


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def table_audit(base, q, plan, source=None):
    raw, receipt = wire(base, q)
    item = {
        "id": q["id"],
        "HTTP_status": receipt["status"],
        "raw_sha256": digest(raw),
        "attempt": receipt["attempt"],
        "expected_primary_groups": sum(
            c["role"] != "auxiliary_not_primary" for c in q["cases"]
        ),
    }
    if receipt["status"] != 200:
        return {
            **item,
            "availability": "HTTP_unavailable",
            "numeric_result": "not_assessed",
            "groups": [],
        }
    try:
        rows = raw_rows(raw, q, plan)
    except (ValueError, KeyError, TypeError) as error:
        return {
            **item,
            "availability": "invalid_table",
            "numeric_result": "not_assessed",
            "error": repr(error),
            "groups": [],
        }
    if parse_rows(raw, q, plan) != rows:
        raise ValueError("Control parsers disagree")
    counts = Counter(r["case_id"] for r in rows)
    expected = Counter(e["case_id"] for e in q["wire_epochs"])
    complete = counts == expected
    groups = []
    for case in q["cases"]:
        members = [r for r in rows if r["case_id"] == case["id"]]
        inputs = [e for e in q["wire_epochs"] if e["case_id"] == case["id"]]
        adjacency = [r["compatible_request_slots"] for r in members]
        matching = hall_matching(adjacency, len(inputs))
        if matching != perfect_matching(adjacency, len(inputs)):
            raise ValueError("Label matching algorithms disagree")
        g = {
            "case_id": case["id"],
            "role": case["role"],
            "expected_rows": len(inputs),
            "returned_rows": len(members),
            "distinct_requested_epochs": len({e["epoch_JD"] for e in inputs}),
            "distinct_printed_epochs": len({r["printed_JD"] for r in members}),
            "distinct_printed_states": len(
                {tuple(r["printed_state"]) for r in members}
            ),
            "complete_label_matching": matching,
            "all_raw_rows": members,
        }
        if source is not None and case["role"] != "auxiliary_not_primary":
            cache = {}
            clocks = []
            for row in members:
                record = {"row_index": row["row_index"], "profiles": {}}
                for profile in plan["numerical_tube_profiles"]:
                    key = (profile, tuple(row["printed_state"]))
                    if key not in cache:
                        saved = diagnose(source, case, row, q["body"], profile, plan)
                        checked = clock_proof(
                            source, case, row, q["body"], profile, saved, plan
                        )
                        cache[key] = {
                            "clock": saved,
                            "candidate_points_independently_checked": checked,
                        }
                    record["profiles"][profile] = cache[key]
                clocks.append(record)
            g["original_frozen_clock_method_applied_posthoc"] = clocks
        groups.append(g)
    return {
        **item,
        "availability": "valid_table",
        "complete_population": complete,
        "groups": groups,
        "numeric_result": "population_diagnostic_only",
    }


def audit(run):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    for name, h in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-queries.json").read_text()),
    }.items():
        if digest((run / name).read_bytes()) != h:
            raise ValueError("Original frozen input changed")
    aproof = json.loads((run / "A-independent-replay-first.json").read_text())
    if aproof["analysis_sha256"] != digest(
        (run / "A-first-analysis.json").read_bytes()
    ):
        raise ValueError("Original A result changed")
    bprocess = json.loads((run / "B-analysis-first-process.json").read_text())
    if (
        bprocess["exit_code"] != 1
        or (run / "B-first-analysis.json").exists()
        or (run / "B-independent-replay-first.json").exists()
    ):
        raise ValueError("Original B failure or untested numerical proof changed")
    cohorts = {}
    for c in ("A", "B"):
        base = run / ("geometry-" + c)
        qp = json.loads((base / "plan-before-queries.json").read_text())
        cohorts[c] = [table_audit(base, q, plan) for q in qp["queries"]]
    controls = run / "separator-controls"
    cp = json.loads((controls / "plan-before-queries.json").read_text())
    seal = json.loads((controls / "implementation-before-queries.json").read_text())
    if (
        digest((controls / "plan-before-queries.json").read_bytes())
        != seal["plan_sha256"]
    ):
        raise ValueError("Posthoc control protocol changed")
    original = json.loads((run / "geometry-A/plan-before-queries.json").read_text())
    reports = []
    for q in cp["queries"]:
        baseq = next(x for x in original["queries"] if x["id"] == q["source_query"])
        changed = {
            k
            for k in q["parameters"] | baseq["parameters"]
            if q["parameters"].get(k) != baseq["parameters"].get(k)
        }
        if changed != {"TLIST"}:
            raise ValueError("Control changed a non-time-list parameter")
        if q["comparison"] == "separator_only":
            sep = " " if q["id"].endswith("space") else ","
            if q["wire_epochs"] != baseq["wire_epochs"] or q["parameters"][
                "TLIST"
            ] != sep.join("'" + e["label"] + "'" for e in q["wire_epochs"]):
                raise ValueError("Separator control changed epochs")
        elif q["comparison"] == "one_primary_epoch_with_original_auxiliary":
            expected = [
                e
                for e in baseq["wire_epochs"]
                if e["case_id"] == "geometry-auxiliary"
                or e["offset"] == q["selected_offset"]
            ]
            if q["wire_epochs"] != expected or q["parameters"]["TLIST"] != "\n".join(
                "'" + e["label"] + "'" for e in expected
            ):
                raise ValueError("Single-input control moved an epoch")
        else:
            raise ValueError("Unknown development control")
        reports.append(
            {
                "comparison": q["comparison"],
                **table_audit(controls, q, plan, run / "source-records"),
            }
        )
    return {
        "kind": "posthoc_readonly_transport_and_population_diagnostic_v1",
        "cohorts": cohorts,
        "development_controls": reports,
        "original_A_independent_exit_code": aproof["exit_code"],
        "original_B_analysis_exit_code": bprocess["exit_code"],
        "B_independent_numerical_acceptance": "not_tested",
        "overall_frozen_neighborhood_acceptance": False,
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
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    with a.output.open("x") as f:
        json.dump(audit(a.run), f, indent=2)
        f.write("\n")
