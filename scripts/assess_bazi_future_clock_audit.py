"""Apply every registered future-clock gate, including finite-envelope misses."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(audit, source):
    counts = audit["counts"]
    total = source["rows"]
    resolved = source["counts"]["resolved_source_control"]
    conditions = {
        "same_frozen_reference": audit["reference_sha256"]
        == source["reference_sha256"],
        "all_registered_rows_completed": audit["registered_rows"]
        == counts["completed_rows"]
        == total,
        "all_source_resolved_rows_assessed": counts["resolved_source_controls"]
        == resolved,
        "all_source_unresolved_rows_retained": counts.get(
            "unresolved_source_controls", 0
        )
        == total - resolved,
        "no_frozen_runtime_drift": not audit["source_drift"],
        "no_safe_numerical_mismatches": not audit["numerical_mismatch_rows"],
        "no_registered_capability_gaps": not audit["capability_gaps"],
        "all_declared_current_states_retained": counts.get(
            "ranges_with_all_declared_current_states", 0
        )
        == resolved,
        "all_declared_inverse_events_retained": counts.get(
            "ranges_with_declared_inverse_event", 0
        )
        == resolved,
        "no_missing_known_current_states": counts.get(
            "ranges_missing_known_current_state", 0
        )
        == 0,
        "no_missing_declared_inverse_events": counts.get(
            "ranges_without_declared_inverse_event", 0
        )
        == 0,
        "all_safe_source_witnesses_inside_probe_envelopes": counts.get(
            "probe_envelopes_not_covering_safe_source_witnesses", 0
        )
        == 0,
        "no_application_partition_unknowns_in_resolved_controls": counts.get(
            "ranges_with_application_unresolved_cells", 0
        )
        == 0,
    }
    return {
        "conditions": conditions,
        "registered_cohort_acceptance_passed": all(conditions.values()),
        "failed_conditions": [
            name for name, passed in conditions.items() if not passed
        ],
        "original_counts": counts,
        "near_inverse_diagnostics_retained": counts.get(
            "near_inverse_boundary_probe_diagnostics", 0
        ),
        "source_grid_already_covered_rows": counts.get(
            "source_minute_grid_already_has_all_declared_states", 0
        ),
        "new_state_repair_credit": 0,
        "full_goal_complete": False,
        "authority_certified": False,
        "overall_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--source-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Preserve first assessment"
    for p in [args.audit, args.source_summary]:
        assert sha(p) == p.with_suffix(".sha256").read_text().strip()
    audit = json.loads(args.audit.read_text())
    source = json.loads(args.source_summary.read_text())
    root = Path(__file__).resolve().parents[1]
    assert sha(root / audit["records"]) == audit["records_sha256"]
    result = assess(audit, source)
    result.update(
        audit=str(args.audit),
        audit_sha256=sha(args.audit),
        source_summary=str(args.source_summary),
        source_summary_sha256=sha(args.source_summary),
        assessor_sha256=sha(__file__),
        scope="All registered numerical/state/inverse/envelope gates; exit0 from the original executor alone is insufficient. No source labels, numerical tolerance, envelope or unknowns changed.",
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            {
                "registered_cohort_acceptance_passed": result[
                    "registered_cohort_acceptance_passed"
                ],
                "failed_conditions": result["failed_conditions"],
            }
        )
    )
    return int(not result["registered_cohort_acceptance_passed"])


if __name__ == "__main__":
    raise SystemExit(main())
