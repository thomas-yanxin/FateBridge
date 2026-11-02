"""Complete the original nine-point Earth/JD grid as isolated controls.

The same-TT-batch controls keep TT input labels separate from TDB source targets.
All results are posthoc development evidence; the strict B failure stays failed.
"""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_earth_clock import parse as parse_TT
from scripts.astrodice_geometric_rr import diagnose
from scripts.audit_astrodice_epoch_neighborhood import table_audit
from scripts.verify_astrodice_earth_clock import raw_rows as raw_TT
from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_geometric_rr import clock_proof


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(run):
    plan = json.loads((run / "plan-before-queries.json").read_text())
    base = run / "isolated-and-TT-controls"
    rawcp = (base / "plan-before-queries.json").read_bytes()
    cp = json.loads(rawcp)
    if (
        digest(rawcp)
        != json.loads((base / "implementation-before-queries.json").read_text())[
            "plan_sha256"
        ]
    ):
        raise ValueError("Isolated control protocol changed")
    for n, h in cp["inputs_sha256"].items():
        if digest((base / n).read_bytes()) != h:
            raise ValueError("Original isolation source binding changed")
    baseline = json.loads((run / "geometry-A/plan-before-queries.json").read_text())
    sourceplan = json.loads(
        (run / "prior-context/prior-leaves/plan-before-queries.json").read_text()
    )
    previous = json.loads((run / "posthoc-transport-population-audit.json").read_text())
    if (
        previous["original_B_analysis_exit_code"] != 1
        or previous["overall_frozen_neighborhood_acceptance"]
    ):
        raise ValueError("Original frozen B failure changed")
    reports = []
    isolated = {}
    oldqueries = json.loads(
        (run / "separator-controls/plan-before-queries.json").read_text()
    )["queries"]
    for q in oldqueries:
        if q["comparison"] == "one_primary_epoch_with_original_auxiliary":
            isolated[q["selected_offset"]] = next(
                x for x in previous["development_controls"] if x["id"] == q["id"]
            )
    for q in cp["queries"]:
        if (
            q["comparison"]
            == "complete_original_nine_point_Earth_JD_grid_with_isolated_requests"
        ):
            parent = next(
                x for x in baseline["queries"] if x["id"] == q["source_query"]
            )
            epochs = [
                e
                for e in parent["wire_epochs"]
                if e["case_id"] == "geometry-auxiliary"
                or e["offset"] == q["selected_offset"]
            ]
            params = {
                **parent["parameters"],
                "TLIST": "\n".join("'" + e["label"] + "'" for e in epochs),
            }
            if (
                q["parameters"] != params
                or q["wire_epochs"] != epochs
                or q["cases"] != parent["cases"]
            ):
                raise ValueError("Isolated control changed an original input")
            report = table_audit(base, q, plan, run / "source-records")
            isolated[q["selected_offset"]] = report
            reports.append(report)
            continue
        if q["comparison"] != "same_original_TT_wire_batch_Earth_geometry":
            raise ValueError("Unknown isolated control")
        source = next(
            x for x in sourceplan["queries"] if x["id"] == q["source_LT_query"]
        )
        parent = next(
            x
            for x in baseline["queries"]
            if x["body"] == "Earth" and x["encoding"] == q["encoding"]
        )
        params = dict(parent["parameters"])
        for k in (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        ):
            params[k] = source["parameters"][k]
        if q["parameters"] != params or q["cases"] != parent["cases"]:
            raise ValueError("Same-TT control changed its time batch")
        inputs = []
        for c in sourceplan["cohorts"]["A"]:
            c = dict(c)
            if c["role"] == "auxiliary_not_primary":
                c["id"] = "geometry-auxiliary"
            inputs.append(c)
        if q["input_cases"] != inputs:
            raise ValueError("TT input/source-target identities merged")
        raw, receipt = wire(base, q)
        report = {
            "id": q["id"],
            "HTTP_status": receipt["status"],
            "raw_sha256": digest(raw),
            "input_scale": "TT",
            "source_scale": "TDB",
            "same_original_TT_time_batch": True,
            "new_candidate_holdouts": 0,
            "new_TT_source_conditions": 0,
        }
        if receipt["status"] != 200:
            reports.append({**report, "availability": "HTTP_unavailable", "rows": []})
            continue
        rows = raw_TT(raw, q, inputs, plan)
        if rows != parse_TT(raw, q, inputs, plan):
            raise ValueError("Independent TT parsers disagree")
        output = []
        for row in rows:
            case = next(c for c in q["cases"] if c["id"] == row["case_id"])
            if case["role"] == "auxiliary_not_primary":
                continue
            profiles = {}
            for p in plan["numerical_tube_profiles"]:
                saved = diagnose(run / "source-records", case, row, "Earth", p, plan)
                checked = clock_proof(
                    run / "source-records", case, row, "Earth", p, saved, plan
                )
                profiles[p] = {
                    "clock": saved,
                    "candidate_points_independently_checked": checked,
                }
            output.append(
                {"TT_input_row": row, "TDB_source_target": case, "profiles": profiles}
            )
        reports.append({**report, "availability": "valid_table", "rows": output})
    if set(isolated) != set(range(-4, 5)):
        raise ValueError("Original isolated grid was truncated")
    grid = []
    for offset in range(-4, 5):
        report = isolated[offset]
        item = {
            "input_ET_ULP_offset": offset,
            "id": report["id"],
            "availability": report["availability"],
        }
        if report["availability"] == "valid_table":
            group = next(
                g for g in report["groups"] if g["role"] != "auxiliary_not_primary"
            )
            rows = group["original_frozen_clock_method_applied_posthoc"]
            if len(rows) != 1:
                raise ValueError("Isolated primary population changed")
            item["profiles"] = {}
            for p, value in rows[0]["profiles"].items():
                clock = value["clock"]
                matches = clock.get("all_six_grid_matches", [])
                target = next(
                    c
                    for c in baseline["queries"][0]["cases"]
                    if c["role"] != "auxiliary_not_primary"
                )["intended_ET_hex"]
                item["profiles"][p] = {
                    "all_six_grid_matches": matches,
                    "match_minus_intended_seconds": [
                        str(Q(float.fromhex(v)) - Q(float.fromhex(target)))
                        for v in matches
                    ],
                    "target_observed": clock.get("unique_at_intended_epoch", False),
                    "label_matching": group["complete_label_matching"],
                    "qualified_control": report["complete_population"]
                    and group["complete_label_matching"]
                    and clock.get("unique_at_intended_epoch", False),
                }
        grid.append(item)
    return {
        "kind": "posthoc_complete_original_Earth_JD_grid_and_TT_controls_v1",
        "isolated_original_grid": grid,
        "additional_controls": reports,
        "new_candidate_holdouts": 0,
        "new_TT_source_conditions": 0,
        "original_A_B_scores_unchanged": True,
        "original_B_analysis_exit_code": 1,
        "overall_frozen_neighborhood_acceptance": False,
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
