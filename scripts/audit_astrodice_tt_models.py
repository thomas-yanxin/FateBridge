"""Read-only posthoc synthesis, including explicitly developmental rounding.

No prospective continuous-model score is replaced by a rounding hypothesis.
There is no fitted offset, per-case winning policy, or candidate precision score.
"""

import argparse
import hashlib
import json
import math
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import Reader
from scripts.astrodice_earth_clock import pair
from scripts.verify_astrodice_earth_clock import paired_proof
from scripts.verify_astrodice_tt_models import verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nearest_epoch(seconds):
    value = float(seconds)
    exact = Q(value)
    lower = (Q(math.nextafter(value, -math.inf)) + exact) / 2
    upper = (exact + Q(math.nextafter(value, math.inf))) / 2
    if not lower <= seconds <= upper:
        raise ValueError("Nearest binary64 cell failed")
    return exact / 86400 + 2451545


def rounding_diagnostics(tt, prediction, source):
    a, b = map(Q, prediction["predicted_JD_TDB"])
    lo, hi = map(Q, source["effective_JD"])
    results = {}
    policies = {
        "round_after_analytic_conversion": lambda x: (x - 2451545) * 86400,
        "round_TT_seconds_then_add_offset": lambda x: Q(float((tt - 2451545) * 86400))
        + (x - tt) * 86400,
        "round_TT_JD_then_convert_seconds_and_add_offset": lambda x: (
            Q(float(tt)) - 2451545
        )
        * 86400
        + (x - tt) * 86400,
    }
    for name, function in policies.items():
        left, right = nearest_epoch(function(a)), nearest_epoch(function(b))
        if left != right:
            results[name] = {"status": "rounding_ambiguous", "compatible": False}
        else:
            results[name] = {
                "status": "unique_rounded_epoch",
                "ET_hex": float((left - 2451545) * 86400).hex(),
                "compatible": lo <= left <= hi,
                "source_all_six_compatible": source["all_six_compatible"],
                "physical_time_or_parser_certified": False,
            }
    return results


def audit(run):
    if sha(run / "manifest.json") != (
        "c8a9a152d102cbe30e180e7358c8d3b6236632a9e2497892f821d68b01d3b094"
    ):
        raise ValueError("Frozen manifest changed")
    manifest = json.loads((run / "manifest.json").read_text())
    for name in (
        "A-independent-replay-repaired.json",
        "B-independent-replay-first.json",
    ):
        if sha(run / name) != manifest["files"][name]:
            raise ValueError("Frozen independent replay receipt changed")
    plan = json.loads((run / "plan-before-queries.json").read_text())
    predictions = json.loads((run / "predictions-before-queries.json").read_text())
    failed = json.loads((run / "A-independent-replay-first-process.json").read_text())
    if (
        failed["exit_code"] != 1
        or "TT/TDB labels conflated" not in failed["stderr"]
        or (run / "A-independent-replay-first.json").exists()
    ):
        raise ValueError("Original independent check failure replaced")
    repair = json.loads((run / "repaired-source-seal-before-B.json").read_text())
    if sha(run / "A-first-analysis.json") != repair["A_analysis_unchanged_sha256"]:
        raise ValueError("Original A result changed")
    for seal, folder in [
        (
            json.loads((run / "source-seal-before-queries.json").read_text()),
            "frozen-source",
        ),
        (repair["files"], "repaired-source"),
    ]:
        for name, value in seal.items():
            if sha(run / folder / name) != value:
                raise ValueError("Frozen implementation changed")
    ascii_text = (run / "authority/header.441.txt").read_text()
    group = ascii_text.split("GROUP   1050")[1].split("GROUP   1070")[0]
    lines = [
        list(map(int, line.split())) for line in group.splitlines() if line.strip()
    ]
    if list(map(len, lines)) != [15, 15, 15]:
        raise ValueError("Original ASCII pointer layout changed")
    pointers = list(map(list, zip(*lines)))
    if pointers[-2:] != [[1019, 0, 0], [1019, 0, 0]]:
        raise ValueError("Unexpected DE441 time series availability")
    result = {
        "plan_sha256": sha(run / "plan-before-queries.json"),
        "new_TT_source_conditions": 5,
        "new_candidate_holdouts": 0,
        "new_requests": 6,
        "adopted_A_requests": 3,
        "original_A_independent_exit_code": 1,
        "repaired_A_result_changed": False,
        "TT_minus_TDB_series_in_original_DE441": "not_present_zero_coefficients_and_zero_subintervals",
        "source_header_last_two_triples": pointers[-2:],
        "independent_replay": {},
        "summary": {},
        "same_TT_pairs": [],
        "posthoc_rounding_only": [],
        "posthoc_rounding_is_new_independent_holdout": False,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for cohort, proof_name in [
        ("A", "A-independent-replay-repaired.json"),
        ("B", "B-independent-replay-first.json"),
    ]:
        proof = verify(run, cohort)
        original = json.loads((run / proof_name).read_text())
        # Compiler paths and failed toolchain attempts describe the machine;
        # source seals, every numeric comparison and acceptance flags must match.
        attempts = proof["native_compilation_attempts"]
        if (
            not attempts
            or attempts[-1]["exit_code"] != 0
            or any(row["exit_code"] == 0 for row in attempts[:-1])
            or {k: v for k, v in proof.items() if k != "native_compilation_attempts"}
            != {k: v for k, v in original.items() if k != "native_compilation_attempts"}
        ):
            raise ValueError("Independent replay receipt changed")
        result["independent_replay"][cohort] = {
            k: v
            for k, v in proof.items()
            if k not in {"comparisons", "native_compilation_attempts"}
        }
        data = json.loads((run / (cohort + "-first-analysis.json")).read_text())
        summary = {}
        for query in data["queries"]:
            for row in query["rows"]:
                for model, by_profile in row["models"].items():
                    for profile, entry in by_profile.items():
                        key = model + ":" + profile
                        item = summary.setdefault(
                            key,
                            {
                                "rows": 0,
                                "overlap": 0,
                                "source_all_six": 0,
                                "qualified_not_refuted": 0,
                            },
                        )
                        item["rows"] += 1
                        item["overlap"] += entry["status"] == "overlap"
                        item["source_all_six"] += entry.get(
                            "source_all_six_compatible", False
                        )
                        item["qualified_not_refuted"] += entry["qualified_not_refuted"]
                        inv = row["profiles"][profile]
                        if inv["status"] == "bracketed":
                            result["posthoc_rounding_only"].append(
                                {
                                    "cohort": cohort,
                                    "query": query["id"],
                                    "case": row["case_id"],
                                    "model": model,
                                    "profile": profile,
                                    "policies": rounding_diagnostics(
                                        Q(row["nominal_JD"]),
                                        predictions[row["case_id"]][model],
                                        inv,
                                    ),
                                }
                            )
        result["summary"][cohort] = summary
        if cohort == "B":
            for enc in ("JD", "MJD", "CAL"):
                earth = next(
                    q
                    for q in data["queries"]
                    if q["encoding"] == enc and q["body"] == "Earth"
                )
                venus = next(
                    q
                    for q in data["queries"]
                    if q["encoding"] == enc and q["body"] == "Venus"
                )
                wire = [
                    q
                    for q in plan["queries"]
                    if q["cohort"] == cohort and q["encoding"] == enc
                ]
                for key in (
                    "TIME_TYPE",
                    "CAL_TYPE",
                    "TIME_DIGITS",
                    "CAL_FORMAT",
                    "TLIST_TYPE",
                    "TLIST",
                ):
                    if wire[0]["parameters"][key] != wire[1]["parameters"][key]:
                        raise ValueError("Paired TT input batches differ")
                for e in earth["rows"]:
                    v = next(r for r in venus["rows"] if r["case_id"] == e["case_id"])
                    case = next(c for c in wire[0]["cases"] if c["id"] == e["case_id"])
                    for profile in plan["numerical_tube_profiles"]:
                        saved = pair(
                            Reader(run / "source-records", case["window_index"]),
                            e,
                            v,
                            profile,
                            plan,
                        )
                        checked = paired_proof(run, case, e, v, saved, profile, plan)
                        result["same_TT_pairs"].append(
                            {
                                "encoding": enc,
                                "case": case["id"],
                                "profile": profile,
                                "source_component_boxes_checked": checked,
                                **saved,
                            }
                        )
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
