"""Check a frozen profile cohort, retaining all missing strata and failures."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from fatebridge.application.execution import execute_tool
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_official import official_chart_checks


def audit(cohort_path, output_directory):
    raw = cohort_path.read_bytes()
    reference = json.loads(raw)
    if output_directory.exists():
        raise ValueError("Refusing to overwrite existing audit evidence")
    output_directory.mkdir()
    official = official_chart_checks(reference)
    spec = next(s for s in CATALOG if s.key == "human_design")
    readings = []
    with gzip.open(output_directory / "complete-runs.jsonl.gz", "wt") as stream:
        for case in reference["cases"]:
            run = execute_tool(spec, spec.request_model(**case["birth_input"]))
            proof = verify_human_design_reading(run)
            readings.append(
                {
                    "id": case["id"],
                    "proof": proof,
                    "all_three_axes_full_marks": run["validation"][
                        "all_three_axes_full_marks"
                    ],
                    "full_source_acceptance_passed": run["source_summary"][
                        "full_source_acceptance_passed"
                    ],
                }
            )
            stream.write(
                json.dumps({"id": case["id"], "run": run}, ensure_ascii=False) + "\n"
            )
    missing = reference["missing_planned_ids"]
    verified = all(
        r["proof"]["status"] == "verified_fixed_template_reading" for r in readings
    )
    report = {
        "method_id": "human_design_frozen_profile_coverage_audit_v1",
        "cohort_sha256": hashlib.sha256(raw).hexdigest(),
        "status": (
            "incomplete_coverage_with_observed_results"
            if missing
            else (
                "bounded_cohort_matched"
                if verified
                and official["status"] == "bounded_official_examples_matched"
                else "failed"
            )
        ),
        "planned": reference["planned_case_count"],
        "observed": reference["observed_case_count"],
        "missing_planned_ids": missing,
        "official_chart_checks": official,
        "served_reading_checks": readings,
        "scope": "Fixed-template fidelity for this finite cohort only. Missing strata and literal-name failures remain explicit. No live-model, complete384line semantic, cycle-origin, whole-calendar or predictive acceptance. Original19/193cohorts and38criteria remain separate and required.",
        "all_three_axes_full_marks": False,
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "real_world_sample_size": 0,
    }
    (output_directory / "checks.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.cohort, args.output_directory)
    print(
        json.dumps(
            {
                "status": report["status"],
                "observed": report["observed"],
                "planned": report["planned"],
                "gate_lines_matched": report["official_chart_checks"][
                    "gate_lines_matched"
                ],
                "literal_name_failures": report["observed"]
                - report["official_chart_checks"]["cross_names_exactly_matched"],
                "verified_fixed_readings": sum(
                    r["proof"]["status"] == "verified_fixed_template_reading"
                    for r in report["served_reading_checks"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
