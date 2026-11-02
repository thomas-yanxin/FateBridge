"""Replay same-batch alias and restored-batch development controls.

These posthoc controls add no held-out conditions and replace no old scores.
"""

import argparse
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_vector_clock import verify as verify_vectors


def load(root, name):
    return json.loads((root / name).read_text())


def audit(run):
    alias, restored = run / "alias-control", run / "restored-batch-control"
    verify_vectors(alias, "A")
    verify_vectors(restored, "A")
    verify_vectors(restored, "B")
    plan = load(run, "plan-before-queries.json")
    original = load(run, "A-first-analysis.json")
    alias_plan, alias_data = [
        load(alias, n) for n in ("plan-before-queries.json", "A-first-analysis.json")
    ]
    alias_identical = alias_total = restored_identical = restored_total = 0
    comparisons = []
    for query in alias_plan["queries"]:
        encoding = query["encoding"]
        control_query = next(
            q
            for q in plan["queries"]
            if q["cohort"] == "A"
            and q.get("body") == "Venus"
            and q["encoding"] == encoding
        )
        differences = {
            k
            for k in query["parameters"] | control_query["parameters"]
            if query["parameters"].get(k) != control_query["parameters"].get(k)
        }
        if (
            differences != {"COMMAND"}
            or query["parameters"]["COMMAND"] != "'2'"
            or control_query["parameters"]["COMMAND"] != "'299'"
        ):
            raise ValueError("Alias control changed more than COMMAND")
        old = next(g for g in original["vectors"] if g["id"] == control_query["id"])
        new = next(g for g in alias_data["queries"] if g["id"] == query["id"])
        for a, b in zip(old["rows"], new["rows"]):
            if a["case_id"] != b["case_id"]:
                raise ValueError("Alias row binding changed")
            alias_total += 1
            alias_identical += a["printed_state"] == b["printed_state"]
    for cohort in ("A", "B"):
        prior_root = run / "prior/controls/vector-calibration"
        pp, pd = [
            load(prior_root, n)
            for n in ("plan-before-queries.json", cohort + "-first-analysis.json")
        ]
        rp, rd = [
            load(restored, n)
            for n in ("plan-before-queries.json", cohort + "-first-analysis.json")
        ]
        for query in [q for q in rp["queries"] if q["cohort"] == cohort]:
            original_query = next(q for q in pp["queries"] if q["id"] == query["id"])
            if query["parameters"] != original_query["parameters"]:
                raise ValueError("Original batch was not restored exactly")
            before = next(g for g in pd["queries"] if g["id"] == query["id"])
            after = next(g for g in rd["queries"] if g["id"] == query["id"])
            combined_query = next(
                q for q in alias_plan["queries"] if q["encoding"] == query["encoding"]
            )
            differences = {
                k
                for k in query["parameters"] | combined_query["parameters"]
                if query["parameters"].get(k) != combined_query["parameters"].get(k)
            }
            if differences != {"TLIST"}:
                raise ValueError("Batch control changed a parameter other than TLIST")
            combined = next(
                g for g in alias_data["queries"] if g["id"] == combined_query["id"]
            )
            for a, b in zip(before["rows"], after["rows"]):
                if a["case_id"] != b["case_id"]:
                    raise ValueError("Restored row binding changed")
                restored_total += 1
                restored_identical += a["printed_state"] == b["printed_state"]
                c = next(
                    c
                    for c in combined["rows"]
                    if Q(c["nominal_JD"]) == Q(a["nominal_JD"])
                )
                profiles = {}
                for profile in plan["numerical_tube_profiles"]:
                    x, y = map(Q, b["profiles"][profile]["effective_JD"])
                    u, v = map(Q, c["profiles"][profile]["effective_JD"])
                    profiles[profile] = {
                        "intersecting": x <= v and u <= y,
                        "combined_minus_restored_seconds": [
                            str((u - y) * 86400),
                            str((v - x) * 86400),
                        ],
                    }
                comparisons.append(
                    {
                        "original_query": query["id"],
                        "case_id": a["case_id"],
                        "role": a["role"],
                        "nominal_JD": a["nominal_JD"],
                        "profiles": profiles,
                    }
                )
    return {
        "development_only": True,
        "new_heldout_conditions": 0,
        "alias_same_batch_rows": alias_total,
        "alias_identical_printed_states": alias_identical,
        "restored_original_rows": restored_total,
        "restored_identical_printed_states": restored_identical,
        "comparisons": comparisons,
        "profiles": {
            p: {
                "primary": sum(
                    c["role"] != "auxiliary_not_primary" for c in comparisons
                ),
                "clock_intervals_disjoint": sum(
                    c["role"] != "auxiliary_not_primary"
                    and not c["profiles"][p]["intersecting"]
                    for c in comparisons
                ),
            }
            for p in plan["numerical_tube_profiles"]
        },
        "numerical_clock_tubes_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    with args.output.open("x") as f:
        json.dump(audit(args.run), f, indent=2)
        f.write("\n")
