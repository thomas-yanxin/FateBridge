"""Receipt/population synthesis; preserves every conditional model and failure."""

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_earth_clock import wire

PLAN_SHA = "43b45b52ca4349981c8cbc5ca24860fe69be26f80ce244588b51d094e8cc1ab0"
FAMILIES = ("absolute_JD_binary64", "seconds_from_J2000_binary64")
HYPOTHESES = ("one_round_source_norm", "two_round_source_norm")


def load(root, name):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run):
    if sha(run / "plan-before-queries.json") != PLAN_SHA:
        raise ValueError("Original plan changed")
    plan = load(run, "plan-before-queries.json")
    for name, digest in plan["inputs_sha256"].items():
        if sha(run / name) != digest:
            raise ValueError("Frozen input changed: " + name)
    for name, digest in load(run, "source-seal-before-queries.json").items():
        if sha(run / "frozen-source" / name) != digest:
            raise ValueError("Frozen algorithm changed")
    before = load(run, "before-B-queries.json")
    if before["plan_sha256"] != PLAN_SHA or before["prior_A_analysis_sha256"] != sha(
        run / "A-first-analysis.json"
    ):
        raise ValueError("B not bound to original A result")
    old = load(run, "retained/original-Farkas-replay.json")
    if (
        old["count"] != 5
        or not old["all_original_contradictions_preserved"]
        or old["original_results_regraded"]
    ):
        raise ValueError("Old failure evidence changed")
    result = {
        "plan_sha256": PLAN_SHA,
        "new_primary_contexts": plan["new_primary_contexts"],
        "new_candidate_holdouts": 0,
        "candidate_calls": 0,
        "new_requests": 6,
        "original_Farkas_failures_retained": 5,
        "original_fixed_lines": plan["original_lines"],
        "cohorts": {},
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "internal_algorithm_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "original_gates_rerun": False,
        "full_goal_complete": False,
    }
    for cohort in ("A", "B"):
        data = load(run, cohort + "-first-analysis.json")
        proof = load(run, cohort + "-independent-replay-first.json")
        for phase in ("collection", "first-analysis", "independent-replay-first"):
            if load(run, cohort + "-" + phase + "-process.json")["exit_code"]:
                raise ValueError("Failed process promoted")
        for value in (data, proof):
            if (
                any(
                    value[k]
                    for k in (
                        "physical_time_model_certified",
                        "internal_algorithm_certified",
                        "full_goal_complete",
                    )
                )
                or value["production_acceptance_exit_code"] != 2
                or value["retained_overall_numeric_gate_exit_code"] != 1
            ):
                raise ValueError("Conditional evidence promoted")
        queries = [q for q in plan["queries"] if q["cohort"] == cohort]
        statuses = []
        for q in queries:
            _, receipt = wire(run, q)
            statuses.append(receipt["status"])
        if [q["id"] for q in queries] != [q["id"] for q in data["queries"]]:
            raise ValueError("Query population reduced")
        details = []
        for query, group in zip(queries, data["queries"]):
            if {r["observation"]["case_id"] for r in group["rows"]} != {
                c["id"] for c in query["cases"]
            }:
                raise ValueError("Case population reduced")
            for row in group["rows"]:
                ob = row["observation"]
                for profile, models in row["inference"]["profiles"].items():
                    if set(models) != set(FAMILIES):
                        raise ValueError("Coordinate model reduced")
                    for family, model in models.items():
                        for hypothesis in HYPOTHESES:
                            pairs = model["qualified_pairs_by_hypothesis"][hypothesis]
                            receivers = sorted({p[0] for p in pairs})
                            details.append(
                                {
                                    "case_id": ob["case_id"],
                                    "role": ob["role"],
                                    "encoding": query["encoding"],
                                    "profile": profile,
                                    "coordinate_family": family,
                                    "rounding_hypothesis": hypothesis,
                                    "original_label_budget_pass": ob[
                                        "original_label_budget_pass"
                                    ],
                                    "status": model["status"],
                                    "pairs_examined": model.get(
                                        "enumerated_pair_count", 0
                                    ),
                                    "qualified_pairs": pairs,
                                    "receiver_hex": receivers,
                                }
                            )
        summaries = []
        for population in ("primary", "auxiliary"):
            for profile in plan["numerical_tube_profiles"]:
                for family in FAMILIES:
                    for hypothesis in HYPOTHESES:
                        selected = [
                            r
                            for r in details
                            if (r["role"] == "auxiliary_not_primary")
                            == (population == "auxiliary")
                            and r["profile"] == profile
                            and r["coordinate_family"] == family
                            and r["rounding_hypothesis"] == hypothesis
                        ]
                        summaries.append(
                            {
                                "population": population,
                                "profile": profile,
                                "coordinate_family": family,
                                "rounding_hypothesis": hypothesis,
                                "denominator": len(selected),
                                "statuses": dict(
                                    Counter(r["status"] for r in selected)
                                ),
                                "qualified_pair_counts": dict(
                                    Counter(
                                        str(len(r["qualified_pairs"])) for r in selected
                                    )
                                ),
                                "receiver_counts": dict(
                                    Counter(
                                        str(len(r["receiver_hex"])) for r in selected
                                    )
                                ),
                                "label_failures": sum(
                                    not r["original_label_budget_pass"]
                                    for r in selected
                                ),
                            }
                        )
        result["cohorts"][cohort] = {
            "HTTP_statuses": dict(Counter(map(str, statuses))),
            "proof": proof,
            "summaries": summaries,
            "details": details,
        }
    previous = load(run, "retained/SSB-A-first-analysis.json")
    comparisons = []
    for row in result["cohorts"]["A"]["details"]:
        if row["role"] == "auxiliary_not_primary":
            continue
        old = next(
            q for q in previous["observer_queries"] if q["encoding"] == row["encoding"]
        )
        record = next(
            v for v in old["rows"] if v["observation"]["case_id"] == row["case_id"]
        )
        old_points = record["inference"]["profiles"][row["profile"]]["families"][
            row["coordinate_family"]
        ]["qualified_reception_points_by_hypothesis"][row["rounding_hypothesis"]]
        differences = sorted(
            {
                (Q(float.fromhex(a)) - Q(float.fromhex(b)))
                * (86400 if row["coordinate_family"] == FAMILIES[0] else 1)
                for a in row["receiver_hex"]
                for b in old_points
            }
        )
        comparisons.append(
            {
                k: row[k]
                for k in (
                    "case_id",
                    "encoding",
                    "profile",
                    "coordinate_family",
                    "rounding_hypothesis",
                )
            }
            | {
                "geocentric_receiver_hex": row["receiver_hex"],
                "SSB_observer_receiver_hex": old_points,
                "differences_seconds": list(map(str, differences)),
                "origin_clock_equivalence_certified": False,
            }
        )
    result["seen_A_origin_comparisons_posthoc"] = comparisons
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
