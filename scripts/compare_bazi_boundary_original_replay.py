"""Pair every original control; preservation never substitutes for acceptance."""

import argparse
import ast
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "docs/validation/bazi-dayun-boundary-original-replay-v1"
ORDER = ("year", "month", "day", "hour")


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


def canonical(value):
    """Retain JSON types, array order and every field; reject non-JSON NaNs."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def leaf_changes(before, after, path=""):
    """Keep all differences, including missing/null and bool/number changes."""
    if type(before) is not type(after):
        return [dict(path=path, before=before, after=after)]
    if isinstance(before, dict):
        changes = []
        for key in sorted(set(before) | set(after)):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in before or key not in after:
                item = dict(
                    path=child, before_present=key in before, after_present=key in after
                )
                if key in before:
                    item["before"] = before[key]
                if key in after:
                    item["after"] = after[key]
                changes.append(item)
            else:
                changes.extend(leaf_changes(before[key], after[key], child))
        return changes
    if isinstance(before, list):
        changes = []
        for index, (left, right) in enumerate(
            zip_longest(before, after, fillvalue=_MISSING)
        ):
            child = path + "/" + str(index)
            if left is _MISSING or right is _MISSING:
                item = dict(
                    path=child,
                    before_present=left is not _MISSING,
                    after_present=right is not _MISSING,
                )
                if left is not _MISSING:
                    item["before"] = left
                if right is not _MISSING:
                    item["after"] = right
                changes.append(item)
            else:
                changes.extend(leaf_changes(left, right, child))
        return changes
    return [] if before == after else [dict(path=path, before=before, after=after)]


_MISSING = object()


def missing_multiset(before, after):
    missing = Counter(map(canonical, before)) - Counter(map(canonical, after))
    return [
        dict(value=json.loads(value), missing_count=count)
        for value, count in sorted(missing.items())
    ]


def grid_changes(before, after):
    def keyed(rows):
        result = {}
        for row in rows:
            key = tuple(row["pillars"][name] for name in ORDER)
            assert key not in result
            result[key] = row
        return result

    old, new = keyed(before["pillars_candidates"]), keyed(after["pillars_candidates"])
    changed, removed = [], []
    for key, row in old.items():
        if key not in new:
            removed.append(list(key))
            continue
        for field in ("sample_count", "first_sample_at", "last_sample_at"):
            if canonical(row[field]) != canonical(new[key][field]):
                changed.append(
                    dict(
                        pillars=list(key),
                        field=field,
                        before=row[field],
                        after=new[key][field],
                    )
                )
    for field in (
        "sample_count",
        "uncertainty_minutes",
        "sampling_policy",
        "birth_at_range",
    ):
        if canonical(before[field]) != canonical(after[field]):
            changed.append(dict(field=field, before=before[field], after=after[field]))
    return dict(removed_pillar_candidates=removed, changed_minute_grid_fields=changed)


def outside_receipt(record):
    """Recompute strict containment from saved source labels and UTC bounds."""
    first = [
        p for p in record["actual_range"]["dayun_boundary_ranges"] if p["period"] == 1
    ]
    assert len(first) == 1
    low, high = utc(first[0]["earliest_start_at"]), utc(first[0]["latest_start_at"])
    assert low <= high
    return [
        p
        for p in record["timeline_probes"]
        if p["safe_distance_gate"]
        and not low <= utc(p["reference"]["manual_start_at"]) <= high
    ]


def compare_record(before, after, index):
    assert isinstance(before["id"], str) and before["id"] == after["id"]
    assert type(before["cohort_index"]) is int and type(after["cohort_index"]) is int
    assert before["cohort_index"] == after["cohort_index"] == index
    assert before["source_status"] == after["source_status"]
    assert type(before["adjudicated"]) is bool and type(after["adjudicated"]) is bool
    assert before["adjudicated"] is after["adjudicated"]
    result = {
        key: before[key]
        for key in ("id", "cohort_index", "source_status", "adjudicated")
    }
    if not before["adjudicated"]:
        result["unknown_record_exact"] = canonical(before) == canonical(after)
        result["unknown_leaf_changes"] = leaf_changes(before, after)
        result["preservation_failures"] = (
            [] if result["unknown_record_exact"] else ["unknown_record_changed"]
        )
        return result
    old_outside, new_outside = outside_receipt(before), outside_receipt(after)
    old_fail, new_fail = bool(old_outside), bool(new_outside)
    transition = (
        "retained"
        if old_fail and new_fail
        else "fixed" if old_fail else "introduced" if new_fail else "passing"
    )
    result.update(
        strict_before_failed=old_fail,
        strict_after_failed=new_fail,
        strict_transition=transition,
        before_point_observations=len(before["timeline_probes"]),
        after_point_observations=len(after["timeline_probes"]),
        point_probes_exact=canonical(before["timeline_probes"])
        == canonical(after["timeline_probes"]),
        point_probe_leaf_changes=leaf_changes(
            before["timeline_probes"], after["timeline_probes"], "/timeline_probes"
        ),
        removed_states=sorted(
            set(before["actual_statuses"]) - set(after["actual_statuses"])
        ),
        added_states=sorted(
            set(after["actual_statuses"]) - set(before["actual_statuses"])
        ),
        lost_declared_inverse_events=missing_multiset(
            before["declared_inverse_events"], after["declared_inverse_events"]
        ),
        numerical_mismatches_exact=canonical(before["numerical_mismatches"])
        == canonical(after["numerical_mismatches"]),
        **compare_boundaries(
            before["actual_range"]["dayun_boundary_ranges"],
            after["actual_range"]["dayun_boundary_ranges"],
        ),
        **grid_changes(before["actual_range"], after["actual_range"]),
    )
    failures = []
    for label, record, calculated in (
        ("before", before, old_outside),
        ("after", after, new_outside),
    ):
        if canonical(calculated) != canonical(
            record["safe_source_witnesses_outside_probe_envelope"]
        ):
            failures.append(label + "_stored_strict_receipt_inconsistent")
        states = sorted(
            {r["status"] for r in record["actual_range"]["current_dayun_candidates"]}
        )
        if states != record["actual_statuses"]:
            failures.append(label + "_stored_current_states_inconsistent")
    lost_event_objects, lost_probe_objects = {}, {}
    for layer in ("event_analysis", "dayun_event_analysis"):
        old, new = before["actual_range"][layer], after["actual_range"][layer]
        lost_event_objects[layer] = missing_multiset(old["events"], new["events"])
        lost_probe_objects[layer] = missing_multiset(old["probes"], new["probes"])
    result.update(
        lost_event_objects=lost_event_objects, lost_probe_objects=lost_probe_objects
    )
    if not result["point_probes_exact"]:
        failures.append("point_probe_object_changed")
    if not result["numerical_mismatches_exact"]:
        failures.append("numerical_mismatches_changed")
    for field in (
        "removed_states",
        "removed_periods",
        "shrunken_bounds",
        "removed_pillar_candidates",
        "changed_minute_grid_fields",
        "lost_declared_inverse_events",
    ):
        if result[field]:
            failures.append(field)
    if any(lost_event_objects.values()):
        failures.append("old_event_objects_lost")
    if any(lost_probe_objects.values()):
        failures.append("old_probe_objects_lost")
    if transition == "introduced":
        failures.append("strict_failure_introduced")
    result["preservation_failures"] = failures
    return result


def compare_streams(before, after, emit):
    """Consume every record once, preserving both directions of every failure."""
    counts, mismatches, transitions, seen = (
        Counter(),
        {},
        {k: [] for k in ("fixed", "introduced", "retained")},
        set(),
    )
    for index, (left, right) in enumerate(zip_longest(before, after)):
        assert left is not None and right is not None, "Missing or extra cohort record"
        a, b = json.loads(left), json.loads(right)
        assert a["id"] not in seen, "Duplicate original identity"
        result = compare_record(a, b, index)
        seen.add(a["id"])
        counts["rows"] += 1
        if not a["adjudicated"]:
            counts["unknown"] += 1
        else:
            counts["known"] += 1
            counts["before_strict_failures"] += result["strict_before_failed"]
            counts["after_strict_failures"] += result["strict_after_failed"]
            transition = result["strict_transition"]
            counts["strict_" + transition] += 1
            if transition != "passing":
                transitions[transition].append(a["id"])
            counts["before_point_observations"] += result["before_point_observations"]
            counts["after_point_observations"] += result["after_point_observations"]
            for field in ("expanded_bounds", "added_periods", "added_states"):
                counts["rows_with_" + field] += bool(result[field])
        for failure in result["preservation_failures"]:
            mismatches.setdefault(failure, []).append(a["id"])
        emit(result)
    return dict(
        counts=dict(counts),
        mismatch_ids=mismatches,
        strict_transition_ids=transitions,
        all_original_ids_once_in_original_order=True,
        preservation_diagnostics_passed=not mismatches,
    )


def verify_legacy_helpers():
    original = ast.parse(
        (ROOT / "scripts/compare_bazi_dayun_legacy_closure.py").read_text()
    )
    current = ast.parse(Path(__file__).read_text())
    for name in ("utc", "compare_boundaries"):
        left = next(
            n
            for n in original.body
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        right = next(
            n for n in current.body if isinstance(n, ast.FunctionDef) and n.name == name
        )
        assert ast.dump(left, include_attributes=False) == ast.dump(
            right, include_attributes=False
        )


def record_path(path):
    resolved = Path(path).resolve()
    return (
        str(resolved.relative_to(ROOT))
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--assessment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    verify_legacy_helpers()
    plan = bound_json(REPLAY / "cohort-protocol.json")
    execution = bound_json(REPLAY / "execution-protocol.json")
    assert all(sha(ROOT / n) == h for n, h in plan["files"].items())
    before, after = bound_json(args.before), bound_json(args.after)
    assert (
        args.before.resolve()
        == (
            ROOT
            / "docs/validation/bazi-dayun-state-clipping-v1/legacy-merged-first.json"
        ).resolve()
    )
    assert after["source_manifest_sha256"] == execution["source_manifest_sha256"]
    assert after["runner_sha256"] == execution["merger_sha256"]
    assert before["reference_sha256"] == after["reference_sha256"]
    assessment = bound_json(args.assessment)
    assert assessment["audit_sha256"] == sha(args.after)
    assert (
        assessment["assessor_sha256"]
        == plan["files"]["scripts/assess_bazi_future_clock_audit.py"]
    )
    for audit in (before, after):
        assert sha(ROOT / audit["records"]) == audit["records_sha256"]
    records = args.output.with_suffix(".records.jsonl.gz")
    partial = records.with_suffix(".partial")
    assert not records.exists() and not partial.exists()
    with (
        gzip.open(ROOT / before["records"], "rt") as old_stream,
        gzip.open(ROOT / after["records"], "rt") as new_stream,
        partial.open("xb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as output,
    ):
        result = compare_streams(
            old_stream,
            new_stream,
            lambda row: output.write(
                (
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                ).encode()
            ),
        )
    counts = result["counts"]
    assert (
        counts["rows"] == plan["registered_rows"]
        and counts["known"] == plan["known"]
        and counts["unknown"] == plan["unknown"]
    )
    assert (
        counts["before_point_observations"]
        == counts["after_point_observations"]
        == 812868
    )
    assert counts["before_strict_failures"] == plan["baseline_strict_failures"]
    assert counts["after_strict_failures"] == after["counts"].get(
        "probe_envelopes_not_covering_safe_source_witnesses", 0
    )
    assert assessment["original_counts"] == after["counts"]
    assert all(sha(ROOT / n) == h for n, h in plan["files"].items())
    partial.rename(records)
    result.update(
        before_audit=str(args.before),
        before_audit_sha256=sha(args.before),
        after_audit=str(args.after),
        after_audit_sha256=sha(args.after),
        unchanged_assessment=str(args.assessment),
        assessment_sha256=sha(args.assessment),
        comparator_sha256=sha(__file__),
        records=record_path(records),
        records_sha256=sha(records),
        registered_cohort_acceptance_passed=assessment[
            "registered_cohort_acceptance_passed"
        ],
        failed_original_conditions=assessment["failed_conditions"],
        original_gates_superseded=False,
        new_state_repair_credit=0,
        new_model_executions=0,
        new_independent_observation_credit=0,
        continuous_extrema_certified=False,
        physical_accuracy_certified=False,
        full_goal_complete=False,
        authority_certified=False,
        overall_score=None,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    records.with_suffix(".sha256").write_text(sha(records) + "\n")
    print(
        json.dumps(
            dict(
                counts=counts,
                mismatch_counts={k: len(v) for k, v in result["mismatch_ids"].items()},
                registered_cohort_acceptance_passed=result[
                    "registered_cohort_acceptance_passed"
                ],
            )
        )
    )
    return int(
        not result["preservation_diagnostics_passed"]
        or not result["registered_cohort_acceptance_passed"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
