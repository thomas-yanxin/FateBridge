"""Full populations and first-receipt synthesis; never a new numerical gate."""

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_earth_clock import wire

PLAN_SHA = "a0f3d98fc87a185e8e87ae9222d2b02b8c238947dcd401facacba01988bf842f"


def load(root, name):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run):
    if sha(run / "plan-before-queries.json") != PLAN_SHA:
        raise ValueError("Frozen plan changed")
    plan = load(run, "plan-before-queries.json")
    for name, digest in plan["inputs_sha256"].items():
        if sha(run / name) != digest:
            raise ValueError("Frozen input changed: " + name)
    before = load(run, "before-B-queries.json")
    if before["plan_sha256"] != PLAN_SHA or before["prior_A_analysis_sha256"] != sha(
        run / "A-first-analysis.json"
    ):
        raise ValueError("B not bound to first A source analysis")
    old = load(run, "retained/original-Farkas-replay.json")
    if (
        old["count"] != 5
        or not old["all_original_contradictions_preserved"]
        or old["original_results_regraded"]
    ):
        raise ValueError("Original strict contradictions changed")
    result = {
        "plan_sha256": PLAN_SHA,
        "new_requests": 66,
        "new_primary_contexts": 1,
        "primary_nodes_per_context": 577,
        "new_candidate_holdouts": 0,
        "original_Farkas_failures_preserved": 5,
        "original_fixed_lines": plan["original_lines"],
        "cohorts": {},
        "physical_time_model_certified": False,
        "TT_derivative_certified": False,
        "physical_remainder_certified": False,
        "original_odd_polynomial_gate_replaced": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "original_gates_rerun": False,
        "full_goal_complete": False,
    }
    for cohort in ("A", "B"):
        for phase in (
            "collection",
            "first-analysis",
            "independent-clock-first",
            "native-reference-first",
            "independent-reference-first",
        ):
            if load(run, cohort + "-" + phase + "-process.json")["exit_code"]:
                raise ValueError("Failed phase promoted: " + cohort + "-" + phase)
        clock = load(run, cohort + "-independent-clock-first.json")
        proof = load(run, cohort + "-independent-reference-first.json")
        fits = load(run, cohort + "-native-reference-first.json")
        if (
            clock["clock_analysis_sha256"]
            != sha(run / (cohort + "-first-analysis.json"))
            or proof["reference_analysis_sha256"]
            != sha(run / (cohort + "-native-reference-first.json"))
            or proof["independent_native_clock_proof_sha256"]
            != sha(run / (cohort + "-independent-clock-first.json"))
        ):
            raise ValueError("First proof/input binding changed")
        statuses = []
        for query in [q for q in plan["queries"] if q["cohort"] == cohort]:
            _, receipt = wire(run, query)
            statuses.append(receipt["status"])
        models = []
        for entry in fits["models"]:
            population = entry["population"]
            if [r["offset_seconds"] for r in population] != list(range(-1440, 1441, 5)):
                raise ValueError("Primary population reduced")
            item = {
                k: entry[k]
                for k in (
                    "profile",
                    "coordinate_family",
                    "rounding_hypothesis",
                    "status",
                    "required_nodes",
                    "qualified_nodes",
                )
            }
            item["qualified_pair_counts"] = dict(
                Counter(str(len(r["qualified_pairs"])) for r in population)
            )
            item["failed_offsets_seconds"] = [
                r["offset_seconds"] for r in population if not r["qualified"]
            ]
            item["failed_label_offsets_seconds"] = [
                r["offset_seconds"] for r in population if not r["label_budget_pass"]
            ]
            if entry["qualified_nodes"] != 577:
                if (
                    entry["status"] != "full_clock_population_unqualified"
                    or "fit_input_sha256" in entry
                ):
                    raise ValueError("Partial model used for fitting")
            else:
                fit = fits["fits_by_input_sha256"][entry["fit_input_sha256"]]
                item["fit_input_sha256"] = entry["fit_input_sha256"]
                item["conditional_quality"] = fit["quality"]
                item["producer_exact_certificate_records"] = sum(
                    c["status"] == "exact_primal_dual_optimum"
                    for w in fit["all_windows"]
                    for a in w["axes"]
                    for c in a["certificates"]
                )
                scale = (
                    86400 if entry["coordinate_family"] == "absolute_JD_binary64" else 1
                )
                epochs = {
                    r["offset_seconds"]: Q(float.fromhex(r["qualified_pairs"][0][0]))
                    * scale
                    for r in population
                }
                departure = [t - epochs[0] - o for o, t in sorted(epochs.items())]
                item["source_elapsed_minus_nominal_seconds"] = {
                    "minimum": str(min(departure)),
                    "maximum": str(max(departure)),
                    "distinct": list(map(str, sorted(set(departure)))),
                }
            models.append(item)
        if len(models) != 8:
            raise ValueError("Model population reduced")
        output = {
            "HTTP_statuses": dict(Counter(map(str, statuses))),
            "independent_clock_proof": clock,
            "independent_reference_proof": proof,
            "models": models,
            "nominal_same_order_control": fits["nominal_same_order_control"].get(
                "quality", fits["nominal_same_order_control"]
            ),
        }
        if cohort == "A":
            rows = fits["old_A_apparent_angle_comparison"]
            output["old_apparent_angles_exact_text_matches"] = sum(
                r["exact_text_match"] for r in rows
            )
            output["old_apparent_angles_population"] = len(rows)
            output["old_apparent_changed_offsets_seconds"] = [
                r["offset_seconds"] for r in rows if not r["exact_text_match"]
            ]
        result["cohorts"][cohort] = output
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    value = audit(args.run)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
