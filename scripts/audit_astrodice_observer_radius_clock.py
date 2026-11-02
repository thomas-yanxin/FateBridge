"""Post-observation population audit; no refitting or new clock hypotheses.

Geometric eligibility requires an exact six-component witness on the same
declared IEEE grid. A missing witness is kept separate from disjoint qualified
sets. These are conditional source-argument tests, not physical clock proofs.
"""

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_emission_epoch import enumerate_bits, from_raw
from scripts.verify_astrodice_joint_epoch import exact_state
from scripts.verify_astrodice_vector_clock import observed_bounds

PLAN_SHA = "30a87fc946995e75bdfb0a7cca24b9ec2a95abc652bdc8b983d1fe35697c8f93"
ORIGIN_PLAN_SHA = "ba830837e432f22c1790c017ba157e661e5eb79a3f57aaa3b33a7292ed0b9d32"
FAMILIES = ("absolute_JD_binary64", "seconds_from_J2000_binary64")
HYPOTHESES = ("one_round_source_norm", "two_round_source_norm")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(root, name):
    return json.loads((root / name).read_text())


def seal(root, name, folder):
    hashes = load(root, name)
    for path, digest in hashes.items():
        if sha(root / folder / path) != digest:
            raise ValueError("Frozen source changed: " + path)
    return len(hashes)


def geometry_points(run, case, row, profile, family, plan):
    item = row["profiles"][profile]
    result = {
        "original_label_budget_pass": row["original_label_budget_pass"],
        "inverse_status": item["status"],
        "all_six_interval_overlap": item.get("all_six_compatible", False),
        "grid_status": "not_enumerated",
        "grid_hex": [],
        "exact_all_six_matches_hex": [],
        "qualified": False,
    }
    if item["status"] != "bracketed":
        return result
    a, b = map(Q, item["effective_JD"])
    if family == FAMILIES[1]:
        a, b = (a - 2451545) * 86400, (b - 2451545) * 86400
    status, points = enumerate_bits(a, b, plan["maximum_lattice_points_per_model"])
    result["grid_status"] = status
    result["grid_hex"] = [v.hex() for v in points]
    if status != "complete":
        return result
    bounds = [
        observed_bounds(
            v, plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
        )
        for v in row["printed_state"]
    ]
    matches = []
    for value in points:
        state = exact_state(
            run / "source-records",
            case["window_index"],
            from_raw(value, family),
            "Earth",
        )
        if all(a <= v <= b for v, (a, b) in zip(state, bounds)):
            matches.append(value.hex())
    result["exact_all_six_matches_hex"] = matches
    result["qualified"] = row["original_label_budget_pass"] and bool(matches)
    return result


def audit(root):
    run = root / "radius-clock"
    if (
        sha(root / "plan-before-queries.json") != ORIGIN_PLAN_SHA
        or sha(run / "plan-before-queries.json") != PLAN_SHA
    ):
        raise ValueError("Frozen plans changed")
    origin = load(root, "plan-before-queries.json")
    plan = load(run, "plan-before-queries.json")
    for directory, p in ((root, origin), (run, plan)):
        for path, digest in p["inputs_sha256"].items():
            if sha(directory / path) != digest:
                raise ValueError("Frozen inputs changed: " + path)
    source_counts = {
        "origin_initial": seal(root, "source-seal-before-probes.json", "frozen-source"),
        "origin_before_queries": seal(
            root, "source-seal-v2-before-probes.json", "frozen-source-v2"
        ),
        "radius_before_analysis": seal(
            run, "source-seal-before-clock-analysis.json", "frozen-source"
        ),
    }
    before = load(run, "before-B-queries.json")
    if before["plan_sha256"] != PLAN_SHA or before["prior_A_analysis_sha256"] != sha(
        run / "A-first-analysis.json"
    ):
        raise ValueError("B was not bound to the original A result")
    origin_data = load(root, "A-first-analysis.json")
    if (
        origin_data["plan_sha256"] != ORIGIN_PLAN_SHA
        or len(origin_data["queries"]) != 6
    ):
        raise ValueError("Origin query population changed")
    statuses = []
    for query in origin["queries"]:
        _, receipt = wire(root, query)
        statuses.append(receipt["status"])
    old = load(run, "retained/original-Farkas-replay.json")
    if (
        old["count"] != 5
        or not old["all_original_contradictions_preserved"]
        or old["original_results_regraded"]
    ):
        raise ValueError("Original failure evidence changed")
    result = {
        "plan_sha256": PLAN_SHA,
        "origin_plan_sha256": ORIGIN_PLAN_SHA,
        "source_file_counts": source_counts,
        "origin_HTTP_statuses": dict(Counter(map(str, statuses))),
        "origin_contracts": [
            {k: q[k] for k in ("id", "origin", "encoding", "status")}
            for q in origin_data["queries"]
        ],
        "new_primary_contexts": plan["new_primary_contexts"],
        "new_candidate_holdouts": 0,
        "new_request_count": 12,
        "original_exact_Farkas_failures_preserved": 5,
        "original_fixed_lines": plan["original_lines"],
        "cohorts": {},
        "numerical_tubes_certified": False,
        "physical_time_model_certified": False,
        "Earth_view_clock_equivalence_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
        "scope": "Posthoc source/receipt/set audit; first independent mathematical proofs retained separately.",
    }
    for cohort in ("A", "B"):
        data = load(run, cohort + "-first-analysis.json")
        proof = load(run, cohort + "-independent-replay-first.json")
        for phase in ("first-analysis", "independent-replay-first"):
            if load(run, cohort + "-" + phase + "-process.json")["exit_code"]:
                raise ValueError("Failed process promoted")
        for receipt in (data, proof):
            if (
                receipt["physical_time_model_certified"]
                or receipt["Earth_view_clock_equivalence_certified"]
                or receipt["full_goal_complete"]
                or receipt["production_acceptance_exit_code"] != 2
                or receipt["retained_overall_numeric_gate_exit_code"] != 1
            ):
                raise ValueError("Conditional evidence promoted")
        queries = [q for q in plan["queries"] if q["cohort"] == cohort]
        http = []
        for query in queries:
            _, receipt = wire(run, query)
            http.append(receipt["status"])
        details = []
        for group in data["observer_queries"]:
            geometric = next(
                g
                for g in data["geometry_queries"]
                if g["encoding"] == group["encoding"]
            )
            query = next(q for q in queries if q["id"] == group["id"])
            for record in group["rows"]:
                row = record["observation"]
                case = next(c for c in query["cases"] if c["id"] == row["case_id"])
                g = next(v for v in geometric["rows"] if v["case_id"] == row["case_id"])
                inf = record["inference"]
                for profile in plan["numerical_tube_profiles"]:
                    for family in FAMILIES:
                        geom = geometry_points(run, case, g, profile, family, plan)
                        item = inf.get("profiles", {}).get(profile, {})
                        found = item.get("families", {}).get(family, {})
                        for hypothesis in HYPOTHESES:
                            points = found.get(
                                "qualified_reception_points_by_hypothesis", {}
                            ).get(hypothesis, [])
                            geo_points = geom["exact_all_six_matches_hex"]
                            common = sorted(set(points) & set(geo_points))
                            if not points:
                                status = "no_qualified_observer_points"
                            elif not geom["qualified"]:
                                status = "geometry_unqualified"
                            elif common:
                                status = "conditionally_compatible"
                            else:
                                status = "conditionally_disjoint"
                            differences = (
                                sorted(
                                    {
                                        (
                                            from_raw(float.fromhex(a), family)
                                            - from_raw(float.fromhex(b), family)
                                        )
                                        * 86400
                                        for a in points
                                        for b in geo_points
                                    }
                                )
                                if geom["qualified"]
                                else []
                            )
                            details.append(
                                {
                                    "case_id": case["id"],
                                    "role": case["role"],
                                    "encoding": group["encoding"],
                                    "profile": profile,
                                    "coordinate_family": family,
                                    "rounding_hypothesis": hypothesis,
                                    "observer_inference_status": inf["status"],
                                    "emission_grid_status": found.get(
                                        "grid_status", "not_enumerated"
                                    ),
                                    "observer_reception_points_hex": points,
                                    "geometry": geom,
                                    "common_points_hex": common,
                                    "observer_minus_geometry_seconds": list(
                                        map(str, differences)
                                    ),
                                    "status": status,
                                }
                            )
        summaries = []
        for population in ("primary", "auxiliary"):
            for profile in plan["numerical_tube_profiles"]:
                for family in FAMILIES:
                    for hypothesis in HYPOTHESES:
                        selected = [
                            d
                            for d in details
                            if (d["role"] == "auxiliary_not_primary")
                            == (population == "auxiliary")
                            and d["profile"] == profile
                            and d["coordinate_family"] == family
                            and d["rounding_hypothesis"] == hypothesis
                        ]
                        summaries.append(
                            {
                                "population": population,
                                "profile": profile,
                                "coordinate_family": family,
                                "rounding_hypothesis": hypothesis,
                                "denominator": len(selected),
                                "observer_point_counts": dict(
                                    Counter(
                                        str(len(d["observer_reception_points_hex"]))
                                        for d in selected
                                    )
                                ),
                                "geometry_qualified": sum(
                                    d["geometry"]["qualified"] for d in selected
                                ),
                                "statuses": dict(
                                    Counter(d["status"] for d in selected)
                                ),
                            }
                        )
        result["cohorts"][cohort] = {
            "HTTP_statuses": dict(Counter(map(str, http))),
            "adopted_queries": sum(q.get("adopted", False) for q in queries),
            "new_queries": sum(not q.get("adopted", False) for q in queries),
            "proof": proof,
            "summaries": summaries,
            "details": details,
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
