"""Read-only synthesis of full populations; mathematical proofs stay separate.

This audit checks source/transport/receipt bindings, not a new numerical model.
It never reclassifies a conditional fit as production reference acceptance.
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_earth_clock import wire


def load(root, name):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run):
    plan = load(run, "plan-before-queries.json")
    for name, h in plan["inputs_sha256"].items():
        if sha(run / name) != h:
            raise ValueError("Input seal changed: " + name)
    if (
        plan["new_independent_astronomical_contexts"] != 1
        or plan["new_primary_epoch_nodes"] != 577
        or plan["new_candidate_holdouts"]
        or plan["original_odd_polynomial_gate_replaced"]
    ):
        raise ValueError("Experiment scope changed")
    for name, folder in [
        ("source-seal-before-queries.json", "frozen-source"),
        ("source-seal-v2-before-queries.json", "frozen-source-v2"),
    ]:
        for path, h in load(run, name).items():
            if sha(run / folder / path) != h:
                raise ValueError("Frozen source changed")
    for name, folder in [
        ("nominal-control-plan-before-B.json", "control-source-before-B"),
        ("nominal-control-units-plan-before-B.json", "control-source-units-before-B"),
    ]:
        for path, h in load(run, name)["source_files"].items():
            if sha(run / folder / path) != h:
                raise ValueError("Frozen control source changed")
    before = load(run, "before-B-queries.json")
    if before["plan_sha256"] != sha(run / "plan-before-queries.json") or before[
        "prior_A_analysis_sha256"
    ] != sha(run / "A-first-analysis.json"):
        raise ValueError("B precondition or plan changed")
    old = load(run, "A-nominal-control-first.json")
    new = load(run, "A-nominal-control-corrected.json")
    old["quality"].pop("TDB_day_not_certified_TT_day")
    old["quality"]["requested_TT_axis_not_internal_time_certified"] = True
    for row in old["fits"]:
        for item in row["axes"]:
            key = "derivative_interval_arcsec_per_TDB_day"
            if key in item:
                item["derivative_interval_arcsec_per_nominal_TT_day"] = item.pop(key)
    if old != new:
        raise ValueError("Unit repair changed numerical results")
    result = {
        "plan_sha256": sha(run / "plan-before-queries.json"),
        "new_independent_astronomical_contexts": 1,
        "primary_nodes_per_context": 577,
        "new_candidate_holdouts": 0,
        "new_request_count": 165,
        "adopted_observer_requests": 33,
        "original_exact_Farkas_failures_preserved": 5,
        "original_fixed_lines": plan["original_lines"],
        "cohorts": {},
        "OBSERVER_vector_clock_identity_certified": False,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
        "scope": "Receipt/source audit; full independent mathematical replay is recorded separately and has its own command.",
    }
    for cohort in ("A", "B"):
        queries = [q for q in plan["queries"] if q["cohort"] == cohort]
        statuses = []
        for query in queries:
            raw, receipt = wire(run, query)
            statuses.append(receipt["status"])
            if sha(run / "responses" / (query["id"] + ".raw")) != receipt["raw_sha256"]:
                raise ValueError("Raw response changed")
        item = {
            "new_queries": len(queries),
            "HTTP_statuses": dict(Counter(map(str, statuses))),
        }
        path = run / (cohort + "-first-analysis.json")
        if not path.exists():
            item["numerical_replay_status"] = "not_tested"
            result["cohorts"][cohort] = item
            continue
        data = load(run, cohort + "-first-analysis.json")
        proof = load(run, cohort + "-independent-replay-first.json")
        if (
            load(run, cohort + "-first-analysis-process.json")["exit_code"]
            or load(run, cohort + "-independent-replay-first-process.json")["exit_code"]
        ):
            raise ValueError("Failed numerical process promoted")
        control = load(
            run,
            cohort
            + (
                "-nominal-control-corrected.json"
                if cohort == "A"
                else "-nominal-control-first.json"
            ),
        )
        if (
            control["original_scores_replaced"]
            or data["full_goal_complete"]
            or proof["full_goal_complete"]
        ):
            raise ValueError("Unsupported overall success")
        profiles = {}
        for profile, rows in data["clock_population"].items():
            if [r["offset_seconds"] for r in rows] != list(range(-1440, 1441, 5)):
                raise ValueError("Source population reduced")
            qualified = sum(r["qualified"] for r in rows)
            if proof["qualified_clock_nodes"][profile] != qualified:
                raise ValueError("Proof population mismatch")
            details = {
                "nodes": len(rows),
                "qualified_nodes": qualified,
                "common_grid_counts": dict(
                    Counter(str(len(r["common_ET_hex"])) for r in rows)
                ),
                "fitting_status": data["fits"][profile]["status"],
            }
            if qualified == 577:
                epochs = {
                    r["offset_seconds"]: Q(float.fromhex(r["common_ET_hex"][0]))
                    for r in rows
                }
                departures = {o: epoch - epochs[0] - o for o, epoch in epochs.items()}
                details["source_elapsed_minus_nominal_seconds"] = {
                    "minimum": str(min(departures.values())),
                    "maximum": str(max(departures.values())),
                    "distinct_values": list(map(str, sorted(set(departures.values())))),
                }
                details["calibrated_quality"] = data["fits"][profile]["quality"]
                details["complete_calibrated_fits"] = [
                    {"window_seconds": w["window_seconds"], "degree": w["full_degree"]}
                    for w in data["fits"][profile]["all_windows"]
                    if w["status"] == "conditional_exact_polynomial_interval"
                ]
            profiles[profile] = details
        failed_labels = []
        observers = {
            q["id"]: q
            for q in plan["queries"] + plan["adopted_A_observer_queries"]
            if q["cohort"] == cohort and q["kind"] == "observer"
        }
        geometry = {q["id"]: q for q in queries if q["kind"] == "geometry"}
        for group in data["queries"]:
            for row in group["rows"]:
                if row["original_label_budget_pass"]:
                    continue
                source = geometry[group["id"]]
                query = observers[source["source_observer_id"]]
                folder = run / ("adopted-A" if cohort == "A" else "responses")
                text = (
                    json.loads((folder / (query["id"] + ".raw")).read_bytes())["result"]
                    .split("$$SOE")[1]
                    .split("$$EOE")[0]
                )
                rawrows = [
                    [v.strip() for v in c]
                    for c in csv.reader(text.strip().splitlines())
                ]
                near = [
                    c
                    for c in rawrows
                    if abs(Q(c[1]) - Q(row["nominal_JD"]))
                    <= Q(plan["returned_label_match_budget_days"])
                ]
                if len(near) != 1:
                    raise ValueError("Observer row not within original fixed line")
                observer = near[0]
                failed_labels.append(
                    {
                        "case": row["case_id"],
                        "body": group["body"],
                        "geometry_printed_JD_TT": row["printed_JD"],
                        "observer_printed_JD_TT": observer[1],
                        "geometry_label_error_seconds": str(
                            (Q(row["printed_JD"]) - Q(row["nominal_JD"])) * 86400
                        ),
                        "observer_label_error_seconds": str(
                            (Q(observer[1]) - Q(row["nominal_JD"])) * 86400
                        ),
                        "geometry_minus_observer_printed_TT_seconds": str(
                            (Q(row["printed_JD"]) - Q(observer[1])) * 86400
                        ),
                    }
                )
        item.update(
            {
                "numerical_replay_status": "completed_with_original_predicates_preserved",
                "proof": proof,
                "profiles": profiles,
                "nominal_same_order_quality": control["quality"],
                "nominal_exact_certificates_checked": control[
                    "independent_exact_certificates_checked"
                ],
                "failed_geometry_labels": failed_labels,
            }
        )
        result["cohorts"][cohort] = item
    old_failure = load(run, "original-Farkas-replay.json")
    if (
        old_failure["count"] != 5
        or not old_failure["all_original_contradictions_preserved"]
        or old_failure["original_results_regraded"]
    ):
        raise ValueError("Old failure history changed")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    value = audit(args.run)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
