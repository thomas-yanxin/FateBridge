"""Keep literal official failures and explain nominal clock disagreements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.validation.human_design_official import official_chart_checks


def source_plan_links(
    plan_raw: bytes, cohort: dict[str, Any], expected_sha256: str
) -> dict[str, Any]:
    actual_digest = hashlib.sha256(plan_raw).hexdigest()
    if actual_digest != expected_sha256:
        raise ValueError("Frozen input plan bytes differ from the required digest")
    plan = json.loads(plan_raw)
    required = {row["id"]: row for row in plan["cases"]}
    if not required or len(required) != len(plan["cases"]):
        raise ValueError("Original plan has no cases or duplicate identities")
    ids = [row["id"] for row in cohort["cases"]]
    missing = [identifier for identifier in required if identifier not in ids]
    unexpected = [identifier for identifier in ids if identifier not in required]
    duplicates = sorted({identifier for identifier in ids if ids.count(identifier) > 1})
    cases = [
        {
            "id": row["id"],
            "original_input_matched": row["id"] in required
            and row["birth_input"] == required[row["id"]]["birth_input"],
        }
        for row in cohort["cases"]
    ]
    ordered = ids == [identifier for identifier in required if identifier in ids]
    actual_complete = len(ids) == len(required) and not (
        missing or unexpected or duplicates
    )
    metadata = (
        type(cohort.get("planned_case_count")) is int
        and cohort["planned_case_count"] == len(required)
        and type(cohort.get("observed_case_count")) is int
        and cohort.get("observed_case_count") == len(ids)
        and cohort.get("missing_planned_ids") == missing
        and cohort.get("collection_status")
        == ("complete" if actual_complete else "incomplete")
        and cohort.get("source", {}).get("plan_sha256") == actual_digest
    )
    return {
        "original_plan_sha256": actual_digest,
        "required_plan_case_count": len(required),
        "observed_case_count": len(ids),
        "missing_planned_ids": missing,
        "unexpected_ids": unexpected,
        "duplicate_ids": duplicates,
        "ids_follow_original_order": ordered,
        "collection_metadata_consistent": metadata,
        "input_link_cases": cases,
        "all_supplied_rows_retained": len(cases) == len(cohort["cases"]),
        "complete_source_plan_links": actual_complete
        and metadata
        and ordered
        and all(row["original_input_matched"] for row in cases),
        "scope": "Required IDs and inputs come from the explicitly pinned plan, not cohort counters. Missing or altered cases cannot become a complete declared set by editing its metadata.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.cohort.read_bytes()
    cohort = json.loads(raw)
    links = source_plan_links(args.plan.read_bytes(), cohort, args.expected_plan_sha256)
    report = official_chart_checks(cohort)
    observed = len(cohort["cases"])
    source_complete = links["complete_source_plan_links"]
    result = {
        "method_id": "human_design_official_clock_link_audit_v1",
        "status": (
            "bounded_declared_cohort_conforms"
            if source_complete
            and report["status"] == "bounded_official_examples_matched"
            else "not_achieved"
        ),
        "source_collection_complete": source_complete,
        "planned_case_count": links["required_plan_case_count"],
        "observed_case_count": observed,
        "missing_planned_ids": links["missing_planned_ids"],
        "source_plan_links": links,
        "official_chart_checks": report,
        "cohort_sha256": hashlib.sha256(raw).hexdigest(),
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "all_supplied_rows_and_raw_comparison_counts_retained": True,
        "all_three_axes_full_marks": False,
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "scope": "Declared finite source set only. Clock labels do not authenticate internal source TT, historical clocks, future leaps, physical accuracy, complete source prose, arbitrary interpretation or reality. No failed row or old threshold is changed.",
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "source_collection_complete",
                    "planned_case_count",
                    "observed_case_count",
                )
            }
        )
    )
    raise SystemExit(result["status"] != "bounded_declared_cohort_conforms")


if __name__ == "__main__":
    main()
