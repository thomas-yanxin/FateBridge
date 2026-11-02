"""Summarize saved lunar proofs and check every centre's source-cell interior.

This is receipt/eligibility replay, not a new numerical independence claim.
Original external endpoint failures and old global gate codes remain visible.
"""

import argparse
import hashlib
import json
import struct
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_lunar_split import PLAN_SHA, SOURCE_INPUTS_SHA, tdb_label


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cell_interior(lo, hi, record_start, record_end, subdivisions):
    if not record_start <= lo <= hi < record_end or subdivisions <= 0:
        raise ValueError("Centre source interval outside an original record")
    width = (record_end - record_start) / subdivisions
    part = (lo - record_start) // width
    margin = min(
        lo - record_start - part * width, record_start + (part + 1) * width - hi
    )
    return int(part), margin


def audit(run):
    if (
        sha(run / "plan-before-analysis.json") != PLAN_SHA
        or sha(run / "source-inputs-before-evaluation.json") != SOURCE_INPUTS_SHA
    ):
        raise ValueError("Lunar source design or raw input seal changed")
    plan = json.loads((run / "plan-before-analysis.json").read_text())
    for name, h in json.loads(
        (run / "source-inputs-before-evaluation.json").read_text()
    ).items():
        if sha(run / name) != h:
            raise ValueError("Bound original source input changed")
    before = json.loads((run / "code-before-holdout.json").read_text())
    for name, h in before.items():
        if sha(run / "source-before-holdout" / name) != h:
            raise ValueError("Frozen heldout code changed: " + name)
    results = {}
    centres = {}
    for split in ["development", "heldout"]:
        candidate = run / (split + "-first.json")
        data = json.loads(candidate.read_text())
        proof = json.loads((run / (split + "-independent-first.json")).read_text())
        if (
            proof["candidate_sha256"] != sha(candidate)
            or proof["plan_sha256"] != PLAN_SHA
            or proof["rows"] != len(data["rows"])
            or proof["points"] != len(data["points"])
            or not proof["strict_independent_containment"]
        ):
            raise ValueError(
                "Saved independent receipt is not bound to the first output"
            )
        if split == "heldout":
            if proof != json.loads(
                (run / "heldout-independent-isolated-first.json").read_text()
            ):
                raise ValueError("Isolated heldout result differs")
        if (
            proof["old_gate_codes"] != [2, 1]
            or proof["whole_production_accuracy_certified"] is not False
            or proof["full_goal_complete"] is not False
        ):
            raise ValueError("Source-model check promoted")
        results[split] = {
            "candidate_sha256": sha(candidate),
            "independent_sha256": sha(run / (split + "-independent-first.json")),
            "rows": proof["rows"],
            "model_points": proof["points"],
            "profiles": {},
            "all_cases": proof["summary"],
        }
        for row, summary in zip(data["rows"], proof["summary"]):
            if (row["protocol"], row["date_label"]) != (
                summary["protocol"],
                summary["date_label"],
            ):
                raise ValueError("Receipt row association changed")
            key = (row["window"], row["epoch_source_jd"])
            if key in centres and centres[key] != row["center"]:
                raise ValueError("Duplicate numerical centres disagree")
            centres[key] = row["center"]
            for profile, p in summary["profiles"].items():
                totals = results[split]["profiles"].setdefault(
                    profile,
                    {
                        "cases": 0,
                        "named_model_step_passed": 0,
                        "maximum_step_difference_upper_arcsec_per_source_day": 0,
                        "maximum_template_bias_upper_arcsec_per_source_day": 0,
                    },
                )
                totals["cases"] += 1
                totals["named_model_step_passed"] += int(
                    p["named_model_step_check_passed"]
                )
                totals["maximum_step_difference_upper_arcsec_per_source_day"] = max(
                    totals["maximum_step_difference_upper_arcsec_per_source_day"],
                    p["step_difference_upper_arcsec_per_source_day"],
                )
                totals["maximum_template_bias_upper_arcsec_per_source_day"] = max(
                    totals["maximum_template_bias_upper_arcsec_per_source_day"],
                    p["maximum_template_bias_upper_arcsec_per_source_day"],
                )
        if split == "development":
            centres[(2, str(tdb_label(plan["record_window_labels"][2])))] = data[
                "lunar_3000_source_control"
            ]
    if results["development"]["rows"] != 20 or results["heldout"]["rows"] != 4:
        raise ValueError("A cohort was narrowed")
    header = (run / "header.bin").read_bytes()
    pointers = [struct.unpack_from("<3i", header, 2696 + 12 * g) for g in range(12)]
    interiors = []
    for (window, epoch), center in sorted(centres.items()):
        raw = (run / f"record-responses/case-{window:02}.bin").read_bytes()
        for clock in ["reception_epoch", "emission_epoch"]:
            lo, hi = map(Q, center[clock])
            record = next(
                (
                    raw[k : k + 8144]
                    for k in range(0, len(raw), 8144)
                    if Q(struct.unpack_from("<d", raw, k)[0])
                    <= lo
                    <= hi
                    < Q(struct.unpack_from("<d", raw, k + 8)[0])
                ),
                None,
            )
            if record is None:
                raise ValueError("Centre source support not in an original record")
            start, end = map(Q, struct.unpack_from("<2d", record))
            for group in [2, 9]:
                part, margin = cell_interior(lo, hi, start, end, pointers[group][2])
                interiors.append(
                    {
                        "window": window,
                        "epoch_source_jd": epoch,
                        "clock": clock,
                        "source_group": group,
                        "part": int(part),
                        "strict_interior_margin_source_days": str(margin),
                        "qualified": margin > 0,
                    }
                )
    old = []
    for filename in plan["old_studies"]:
        name = filename.replace("-protocol", "-reference")
        p = run / "before-change/tests/fixtures" / name
        d = json.loads(p.read_text())
        failed = [
            {
                "date_tt": v["date_tt"],
                "step_difference_arcsec_per_day": v["step_difference_arcsec_per_day"],
            }
            for v in d["rows"]
            if v["step_difference_arcsec_per_day"]
            > float(plan["fixed_rate_arcsec_per_day"])
        ]
        if len(failed) != 4:
            raise ValueError("An original four-failure record changed")
        old.append(
            {
                "reference": name,
                "original_sha256": sha(p),
                "original_failed_template_count": len(failed),
                "original_failed_rows": failed,
                "original_result_regraded": False,
            }
        )
    return {
        "plan_sha256": PLAN_SHA,
        "source_inputs_sha256": SOURCE_INPUTS_SHA,
        "role": "Saved independent proof bindings plus mandatory posthoc centre source-interiority check; not a fresh full numerical replay",
        "results": results,
        "distinct_source_centres_including_control": len(centres),
        "source_interiority_checks": interiors,
        "all_selected_centres_strictly_inside_source_cells": all(
            x["qualified"] for x in interiors
        ),
        "old_external_reference_failures": old,
        "fixed_position_arcsec": "0.02",
        "fixed_rate_arcsec_per_day": "0.002",
        "new_external_observations": 0,
        "new_production_accuracy_holdouts": 0,
        "production_default_backend_changed": False,
        "production_formulas_changed": False,
        "physical_TT_TDB_certified": False,
        "Horizons_model_equivalence_certified": False,
        "old_gate_codes": [2, 1],
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = audit(a.run)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(
        json.dumps(
            {
                "distinct_centres": result["distinct_source_centres_including_control"],
                "interiority_checks": len(result["source_interiority_checks"]),
                "all_interiors_qualified": result[
                    "all_selected_centres_strictly_inside_source_cells"
                ],
                "old_gate_codes": [2, 1],
            }
        )
    )
    if not result["all_selected_centres_strictly_inside_source_cells"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
