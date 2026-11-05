"""Audit all original official cohorts and the unchanged full768 profile plan.

All original19/193 cases stay in the check. Their frozen source evidence supplies
the existing official vocabulary, without changing the shared verifier. Missing
profile cases and literal-name failures never become a passing full-coverage gate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import fatebridge
from fatebridge.application.execution import execute_tool
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_official import (
    combine_official_chart_cohorts,
    official_chart_checks,
)

ROOT = Path(__file__).resolve().parents[2]
PLAN = "tests/fixtures/human-design-profile-coverage-plan.json"
PLAN_SHA256 = "ea4e0cd15bd228a3002bd055aaeaae28264b5edf0d51505af1828c29e78ce143"
ORIGINALS = (
    ("original8", "tests/fixtures/human-design-official-charts.json", 8),
    ("original11", "tests/fixtures/human-design-official-authority-charts.json", 11),
    ("original193", "tests/fixtures/human-design-official-cross-charts.json", 193),
)
EXTRA_PRESERVED = {
    "tests/fixtures/human-design-official-authority-charts.json": "552d68813be5b40076981aa07f4e34c2965c5ecc6444537a539ffec06df6ecc7",
    "tests/fixtures/human-design-authority-plan.json": "0988244e85d00676593bd51b96e21d7f402a45bc73e5808c507e6256894fd2c8",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(profile: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    if sha256(root / PLAN) != PLAN_SHA256:
        raise ValueError("Original768 profile plan changed")
    plan = json.loads((root / PLAN).read_text())
    fingerprints = {PLAN: PLAN_SHA256}
    for name, expected in {
        **plan["preserved_cohorts_sha256"],
        **EXTRA_PRESERVED,
    }.items():
        if sha256(root / name) != expected:
            raise ValueError(f"Required original source changed: {name}")
        fingerprints[name] = expected
    cohorts = []
    for name, path, count in ORIGINALS:
        original = json.loads((root / path).read_text())
        if len(original["cases"]) != count:
            raise ValueError(f"Required original cohort count changed: {name}")
        cohorts.append((name, original))
    cohorts = [
        ("original19", combine_official_chart_cohorts(cohorts[0][1], cohorts[1][1])),
        cohorts[2],
    ]
    planned = plan["cases"]
    ids = [r["id"] for r in profile["cases"]]
    if ids != [r["id"] for r in planned[: len(ids)]]:
        raise ValueError("Profile observations must retain the exact planned prefix")
    if any(
        a["birth_input"] != b["birth_input"] for a, b in zip(profile["cases"], planned)
    ):
        raise ValueError("Profile birth input differs from original frozen plan")
    missing = [r["id"] for r in planned[len(ids) :]]
    if (
        profile["planned_case_count"] != 768
        or profile["observed_case_count"] != len(ids)
        or profile["missing_planned_ids"] != missing
        or profile["collection_status"] != ("incomplete" if missing else "complete")
        or profile["source"]["plan_sha256"] != PLAN_SHA256
    ):
        raise ValueError("Profile completeness metadata differs from actual cases")
    cohorts.append(("profile768", profile))
    all_ids = [r["id"] for _, ref in cohorts for r in ref["cases"]]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate case identifiers across required cohorts")
    combined = combine_official_chart_cohorts(*(ref for _, ref in cohorts))
    return {
        "cohorts": cohorts,
        "combined": combined,
        "missing": missing,
        "input_fingerprints": fingerprints,
    }


def split_official_checks(
    prepared: dict[str, Any], official: dict[str, Any]
) -> list[dict[str, Any]]:
    expected = [r["id"] for r in prepared["combined"]["cases"]]
    if [r["id"] for r in official["cases"]] != expected:
        raise ValueError(
            "Official report dropped, duplicated or reordered required cases"
        )
    groups = []
    offset = 0
    for name, ref in prepared["cohorts"]:
        rows = official["cases"][offset : offset + len(ref["cases"])]
        offset += len(rows)
        mechanics = sum(
            not r.get("gate_line_mismatches", ["not_checked"])
            and bool(r.get("structure_checks"))
            and all(v for k, v in r["structure_checks"].items() if k != "cross_name")
            for r in rows
        )
        names = sum(
            r.get("structure_checks", {}).get("cross_name") is True for r in rows
        )
        groups.append(
            {
                "cohort": name,
                "cases_required": len(ref["cases"]),
                "gate_lines_expected": 26 * len(ref["cases"]),
                "gate_lines_checked": sum(r.get("gate_lines_checked", 0) for r in rows),
                "gate_lines_matched": sum(r.get("gate_lines_matched", 0) for r in rows),
                "all_mechanics_matched": mechanics,
                "literal_name_matches": names,
                "literal_name_failures": len(rows) - names,
                "complete_chart_matches": sum(r["status"] == "matched" for r in rows),
                "calculation_error_ids": [
                    r["id"] for r in rows if r["status"] == "calculation_error"
                ],
                "case_ids": [r["id"] for r in rows],
                "source": ref["source"],
                "source_cohorts": ref.get("cohorts", []),
                "scope": ref["scope"],
            }
        )
    return groups


def audit(
    cohort_path: Path, output_directory: Path, root: Path = ROOT
) -> dict[str, Any]:
    raw = cohort_path.read_bytes()
    prepared = prepare(json.loads(raw), root)
    output_directory.mkdir(exist_ok=False)
    official = official_chart_checks(prepared["combined"])
    groups = split_official_checks(prepared, official)
    spec = next(s for s in CATALOG if s.key == "human_design")
    readings = []
    with gzip.open(output_directory / "complete-runs.jsonl.gz", "wt") as stream:
        for cohort_name, ref in prepared["cohorts"]:
            for case in ref["cases"]:
                record: dict[str, Any] = {"cohort": cohort_name, "id": case["id"]}
                try:
                    run = execute_tool(spec, spec.request_model(**case["birth_input"]))
                    record["run"] = run
                    proof = verify_human_design_reading(run)
                    record["proof"] = proof
                except Exception as error:
                    proof = {
                        "status": "not_verified",
                        "exception_type": type(error).__name__,
                        "message": str(error),
                    }
                    record["proof"] = proof
                readings.append(
                    {"cohort": cohort_name, "id": case["id"], "proof": proof}
                )
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
    changed = [
        name
        for name, expected in prepared["input_fingerprints"].items()
        if sha256(root / name) != expected
    ]
    if cohort_path.read_bytes() != raw:
        changed.append(str(cohort_path))
    complete = not prepared["missing"]
    local_passed = (
        complete
        and not changed
        and all(r["status"] == "matched" for r in official["cases"])
        and all(
            r["proof"]["status"] == "verified_fixed_template_reading" for r in readings
        )
    )
    report = {
        "method_id": "human_design_all_required_official_profile_cohorts_v1",
        "status": "bounded_required_cohorts_passed" if local_passed else "not_achieved",
        "profile_planned": 768,
        "profile_observed": len(prepared["cohorts"][-1][1]["cases"]),
        "missing_profile_ids": prepared["missing"],
        "all_original_cases_retained": True,
        "required_total_case_count": 980,
        "observed_total_case_count": len(prepared["combined"]["cases"]),
        "cohort_summaries": groups,
        "official_chart_checks": official,
        "served_reading_checks": readings,
        "cohort_sha256": hashlib.sha256(raw).hexdigest(),
        "source_inputs": prepared["input_fingerprints"],
        "source_inputs_changed_after_audit": changed,
        "audit_script_sha256": sha256(Path(__file__)),
        "engine_import_path": str(Path(fatebridge.__file__).resolve()),
        "all_three_axes_full_marks": False,
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "real_world_sample_size": 0,
        "scope": "Original19and193 plus all available observations from the unchanged768input plan. Each cohort keeps its original scope, every required ID and every failed row. Original source vocabulary gate, literal names and numerical criteria are unchanged. Full768 observation coverage is separate from chart conformance, complete384line/fixing/source-authentication, arbitrary model explanation, whole-calendar accuracy and prediction. Fixed-template verification is not live-model holdout acceptance.",
    }
    (output_directory / "checks.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.cohort, args.output_directory)
    print(
        json.dumps(
            {
                "status": report["status"],
                "profile_observed": report["profile_observed"],
                "profile_planned": report["profile_planned"],
                "cohorts": [
                    {
                        k: r[k]
                        for k in (
                            "cohort",
                            "cases_required",
                            "all_mechanics_matched",
                            "literal_name_failures",
                        )
                    }
                    for r in report["cohort_summaries"]
                ],
                "fixed_template_verified": sum(
                    r["proof"]["status"] == "verified_fixed_template_reading"
                    for r in report["served_reading_checks"]
                ),
            }
        )
    )
    raise SystemExit(report["status"] != "bounded_required_cohorts_passed")


if __name__ == "__main__":
    main()
