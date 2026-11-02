"""Compare two declared reception-clock hypotheses using range-inferred emission.

Maintenance diagnosis only. Quantity 30 is a conditional future leap-hold model,
not a certified TT/TDB conversion, nor a replacement for old acceptance scores.
"""

import argparse
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_emission_epoch import infer
from scripts.astrodice_observer_timescale import classify
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube


def receiver(row, calibration, model, profile, plan):
    if model == "vector_TT_source_epoch":
        return {"status": "available", "calibration": calibration}
    if model != "quantity30_current_leap_hold":
        raise ValueError("Unplanned receiver model")
    nominal = Q(row["nominal_JD"])
    if nominal < Q(plan["quantity30_modern_cutoff_JD"]):
        return {"status": "not_assessed_pre_1962"}
    if row["TDB_minus_UT_seconds"] is None:
        return {"status": "time_field_unavailable"}
    hold = Q(plan["latest_known_TAI_minus_UTC_seconds"]) + Q(
        plan["TT_minus_TAI_seconds"]
    )
    if hold != Q(plan["future_current_leap_hold_hypothesis_seconds"]):
        raise ValueError("Leap-hold decomposition differs")
    bounds = tube(
        row["TDB_minus_UT_seconds"],
        plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"],
    )
    return {
        "status": "available",
        "calibration": {
            "status": "bracketed",
            "effective_JD": [str(nominal + (v - hold) / 86400) for v in bounds],
            # No six-component source calibration was performed for this model.
            "all_six_compatible": False,
        },
    }


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    groups = plan["development_groups"] if cohort == "A" else [plan["heldout_group"]]
    result = {
        "plan_sha256": digest,
        "cohort": cohort,
        "groups": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "internal_emission_algorithm_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for spec in groups:
        obsroot, calroot = [
            run / spec[k] for k in ("observation_root", "calibration_root")
        ]
        original_plan = json.loads((obsroot / "plan-before-queries.json").read_text())
        cases = original_plan["cohorts"][spec["cohort"]]
        calpath = calroot / (spec["cohort"] + "-first-analysis.json")
        calibrations = {v["id"]: v for v in json.loads(calpath.read_text())["queries"]}
        for query in original_plan["queries"]:
            if query["cohort"] != spec["cohort"] or query["time_type"] != "TT":
                continue
            rawpath = obsroot / "responses" / (query["id"] + ".raw")
            raw = rawpath.read_bytes()
            receipt = json.loads(rawpath.with_suffix(".receipt.json").read_text())
            if sha(raw) != receipt["raw_sha256"]:
                raise ValueError("Original raw observer bytes changed")
            parsed = classify(raw, receipt["status"], query, cases, original_plan)
            group = {
                **spec,
                "query_id": query["id"],
                "raw_sha256": sha(raw),
                "calibration_sha256": sha(calpath.read_bytes()),
                "status": parsed["status"],
                "rows": [],
            }
            if parsed["status"] == "supported":
                cal = calibrations[query["id"]]
                if cal["status"] != "diagnosed":
                    raise ValueError(
                        "Unavailable geometric calibration needs explicit assessment"
                    )
                lookup = {r["case_id"]: r for r in cal["rows"]}
                for row in parsed["rows"]:
                    case = next(c for c in cases if c["id"] == row["case_id"])
                    item = {**row, "profiles": {}}
                    for profile in plan["numerical_tube_profiles"]:
                        models = {}
                        for model in plan["receiver_models"]:
                            selected = receiver(
                                row,
                                lookup[row["case_id"]]["profiles"][profile],
                                model,
                                profile,
                                plan,
                            )
                            models[model] = {**selected}
                            if selected["status"] == "available":
                                models[model]["inference"] = infer(
                                    run / "source-records",
                                    case,
                                    row,
                                    selected["calibration"],
                                    profile,
                                    plan,
                                )
                        item["profiles"][profile] = models
                    group["rows"].append(item)
            result["groups"].append(group)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    args = parser.parse_args()
    save(
        args.run / (args.cohort + "-first-analysis.json"),
        analyze(args.run, args.cohort),
    )
