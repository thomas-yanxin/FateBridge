"""Compare the whole frozen original cohort without relaxing any acceptance gate."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-dayun-state-legacy-closure-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_json(path):
    assert sha(path) == path.with_suffix(".sha256").read_text().strip()
    return json.loads(path.read_text())


def utc(value):
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() is not None
    return parsed.astimezone(timezone.utc)


def compare_boundaries(before, after):
    """Compare saved UTC extrema, preserving missing and newly added periods."""

    def keyed(rows):
        result = {}
        for row in rows:
            key = (row["direction"], row["period"], row["pillar"])
            assert key not in result
            result[key] = row
        return result

    old, new = keyed(before), keyed(after)
    removed, shrunk, expanded = [], [], []
    for key, row in old.items():
        if key not in new:
            removed.append(list(key))
            continue
        for field in (
            "earliest_start_at",
            "latest_start_at",
            "earliest_end_at",
            "latest_end_at",
        ):
            a, b = utc(row[field]), utc(new[key][field])
            if a == b:
                continue
            entry = {
                "period_key": list(key),
                "field": field,
                "before": row[field],
                "after": new[key][field],
            }
            narrowed = b > a if field.startswith("earliest") else b < a
            (shrunk if narrowed else expanded).append(entry)
    return {
        "removed_periods": removed,
        "shrunken_bounds": shrunk,
        "expanded_bounds": expanded,
        "added_periods": [list(key) for key in new if key not in old],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    protocol = bound_json(STUDY / "protocol.json")
    assert all(sha(ROOT / p) == h for p, h in protocol["files"].items())
    old_path = ROOT / "docs/validation/bazi-dayun-future-clocks-split-pipeline-v1.json"
    new_path = ROOT / protocol["candidate_audit"]
    before, after = bound_json(old_path), bound_json(new_path)
    assessment = bound_json(args.assessment)
    assert assessment["audit_sha256"] == sha(new_path)
    assert (
        assessment["assessor_sha256"]
        == protocol["files"]["scripts/assess_bazi_future_clock_audit.py"]
    )
    for report in (before, after):
        assert sha(ROOT / report["records"]) == report["records_sha256"]
    output_rows = args.output.with_suffix(".records.jsonl.gz")
    assert not output_rows.exists()
    counts = Counter()
    seen = set()
    mismatches, transitions = {}, {"fixed": [], "introduced": [], "retained": []}
    with (
        gzip.open(ROOT / before["records"], "rt") as old_stream,
        gzip.open(ROOT / after["records"], "rt") as new_stream,
        gzip.GzipFile(filename=str(output_rows), mode="wb", mtime=0) as output,
    ):
        for index, pair in enumerate(zip_longest(old_stream, new_stream)):
            a_text, b_text = pair
            assert a_text is not None and b_text is not None
            a, b = json.loads(a_text), json.loads(b_text)
            assert a["id"] == b["id"] and a["id"] not in seen
            assert b["cohort_index"] == index
            assert a["source_status"] == b["source_status"]
            assert a["adjudicated"] == b["adjudicated"]
            seen.add(a["id"])
            counts["rows"] += 1
            result = {
                "id": a["id"],
                "cohort_index": index,
                "source_status": a["source_status"],
                "adjudicated": a["adjudicated"],
            }
            if not a["adjudicated"]:
                counts["unknown"] += 1
                same = a == {k: v for k, v in b.items() if k != "cohort_index"}
                result["unknown_record_exact"] = same
                if not same:
                    mismatches.setdefault("unknown_record_changed", []).append(a["id"])
            else:
                counts["known"] += 1
                old_fail = bool(a["safe_source_witnesses_outside_probe_envelope"])
                new_fail = bool(b["safe_source_witnesses_outside_probe_envelope"])
                counts["before_strict_failures"] += int(old_fail)
                counts["after_strict_failures"] += int(new_fail)
                transition = (
                    "retained"
                    if old_fail and new_fail
                    else (
                        "fixed" if old_fail else "introduced" if new_fail else "passing"
                    )
                )
                counts["strict_" + transition] += 1
                if transition != "passing":
                    transitions[transition].append(a["id"])
                bounds = compare_boundaries(
                    a["actual_range"]["dayun_boundary_ranges"],
                    b["actual_range"]["dayun_boundary_ranges"],
                )
                result.update(
                    strict_before_failed=old_fail,
                    strict_after_failed=new_fail,
                    strict_transition=transition,
                    point_probes_exact=a["timeline_probes"] == b["timeline_probes"],
                    removed_states=sorted(
                        set(a["actual_statuses"]) - set(b["actual_statuses"])
                    ),
                    added_states=sorted(
                        set(b["actual_statuses"]) - set(a["actual_statuses"])
                    ),
                    declared_inverse_events_exact=a["declared_inverse_events"]
                    == b["declared_inverse_events"],
                    numerical_mismatches_exact=a["numerical_mismatches"]
                    == b["numerical_mismatches"],
                    **bounds,
                )
                counts["before_point_probes"] += len(a["timeline_probes"])
                counts["after_point_probes"] += len(b["timeline_probes"])
                for field in (
                    "point_probes_exact",
                    "declared_inverse_events_exact",
                    "numerical_mismatches_exact",
                ):
                    if not result[field]:
                        mismatches.setdefault(field, []).append(a["id"])
                for field in ("removed_states", "removed_periods", "shrunken_bounds"):
                    if result[field]:
                        mismatches.setdefault(field, []).append(a["id"])
                for field in ("expanded_bounds", "added_periods", "added_states"):
                    counts["rows_with_" + field] += bool(result[field])
            output.write((json.dumps(result, ensure_ascii=False) + "\n").encode())
    assert counts["rows"] == protocol["registered_rows"]
    assert counts["known"] == protocol["known"]
    assert counts["unknown"] == protocol["unknown"]
    assert (
        counts["before_strict_failures"]
        == protocol["baseline_strict_envelope_failures"]
    )
    assert (
        counts["after_strict_failures"]
        == after["counts"]["probe_envelopes_not_covering_safe_source_witnesses"]
    )
    result = {
        "protocol_sha256": sha(STUDY / "protocol.json"),
        "comparator_sha256": sha(__file__),
        "before_audit": str(old_path.relative_to(ROOT)),
        "before_audit_sha256": sha(old_path),
        "after_audit": str(new_path.relative_to(ROOT)),
        "after_audit_sha256": sha(new_path),
        "unchanged_assessment": str(args.assessment),
        "assessment_sha256": sha(args.assessment),
        "counts": dict(counts),
        "mismatch_ids": mismatches,
        "strict_transition_ids": transitions,
        "records": str(output_rows.resolve().relative_to(ROOT)),
        "records_sha256": sha(output_rows),
        "all_original_ids_once_in_original_order": True,
        "preservation_diagnostics_passed": not mismatches,
        "registered_cohort_acceptance_passed": assessment[
            "registered_cohort_acceptance_passed"
        ],
        "failed_original_conditions": assessment["failed_conditions"],
        "new_state_repair_credit": 0,
        "new_independent_observation_credit": 0,
        "new_model_executions": 0,
        "continuous_extrema_certified": False,
        "physical_clock_certified": False,
        "full_goal_complete": False,
        "authority_certified": False,
        "overall_score": None,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    output_rows.with_suffix(".sha256").write_text(sha(output_rows) + "\n")
    print(
        json.dumps(
            {
                "counts": dict(counts),
                "mismatch_counts": {k: len(v) for k, v in mismatches.items()},
                "registered_cohort_acceptance_passed": result[
                    "registered_cohort_acceptance_passed"
                ],
            }
        )
    )
    return int(bool(mismatches) or not result["registered_cohort_acceptance_passed"])


if __name__ == "__main__":
    raise SystemExit(main())
