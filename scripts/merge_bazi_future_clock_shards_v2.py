"""Merge every fixed-index shard without changing original acceptance gates."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_json(path):
    assert sha(path) == path.with_suffix(".sha256").read_text().strip()
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("shards", nargs="+", type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    protocol_path = ROOT / "tests/fixtures/bazi_historical_point_v1/shard-protocol.json"
    protocol = bound_json(protocol_path)
    assert sha(args.source_manifest) == protocol["source_manifest_sha256"]
    assert (
        sha(ROOT / "scripts/audit_bazi_dayun_future_clocks_shard.py")
        == protocol["shard_runner_sha256"]
    )
    assert (
        sha(ROOT / "scripts/audit_bazi_dayun_future_clocks_parts.py")
        == protocol["original_runner_sha256"]
    )
    manifest = json.loads(args.source_manifest.read_text())
    source = Path(manifest["source"])
    assert all(sha(source / p) == h for p, h in manifest["files"].items())
    summary = bound_json(FIXTURE / "reference-summary.json")
    reference_path = FIXTURE / "reference.jsonl.gz"
    assert sha(reference_path) == summary["reference_sha256"]
    reports = [bound_json(p) for p in args.shards]
    n = protocol["shards"]
    assert len(reports) == n
    reports.sort(key=lambda r: r["shard_index"])
    assert [r["shard_index"] for r in reports] == list(range(n))
    counts, errors, gaps, drift, origins = Counter(), [], [], set(), {}
    for i, r in enumerate(reports):
        assert r["shard_count"] == n and r["registered_rows"] == summary["rows"]
        assert r["counts"]["completed_rows"] == len(range(i, summary["rows"], n))
        assert r["runner_sha256"] == protocol["shard_runner_sha256"]
        assert r["source_manifest_sha256"] == sha(args.source_manifest)
        assert r["reference_sha256"] == summary["reference_sha256"]
        assert r["reference_summary_sha256"] == sha(FIXTURE / "reference-summary.json")
        assert r["application_protocol_sha256"] == sha(
            FIXTURE / "application-protocol.json"
        )
        assert sha(ROOT / r["records"]) == r["records_sha256"]
        counts.update(r["counts"])
        errors.extend(r["numerical_mismatch_rows"])
        gaps.extend(r["capability_gaps"])
        drift.update(r["source_drift"])
        for name, path in r["module_origins"].items():
            assert Path(path).resolve().is_relative_to(source.resolve() / "src")
            assert name not in origins or origins[name] == path
            origins[name] = path
    records = args.output.with_suffix(".records.jsonl.gz")
    partial = records.with_suffix(".partial")
    assert not records.exists() and not partial.exists()
    actual_status_counts, positions = Counter(), {}
    with ExitStack() as stack:
        streams = [
            stack.enter_context(gzip.open(ROOT / r["records"], "rt")) for r in reports
        ]
        reference = stack.enter_context(gzip.open(reference_path, "rt"))
        header = json.loads(next(reference))
        assert (
            header["record_type"] == "header"
            and header["collector_sha256"] == summary["collector_sha256"]
        )
        output = stack.enter_context(
            gzip.GzipFile(filename=str(partial), mode="wb", mtime=0)
        )
        completed = 0
        for line in reference:
            expected = json.loads(line)
            if expected["record_type"] == "footer":
                assert expected["row_count"] == completed == summary["rows"]
                assert expected["counts"] == summary["counts"]
                assert sum(actual_status_counts.values()) == completed
                assert all(
                    summary["counts"][status] == count
                    for status, count in actual_status_counts.items()
                )
                assert not reference.read()
                break
            assert expected["record_type"] == "control"
            candidate_text = streams[completed % n].readline()
            candidate = json.loads(candidate_text)
            assert candidate["cohort_index"] == completed
            assert (
                candidate["id"] == expected["id"] and candidate["id"] not in positions
            )
            assert candidate["source_status"] == expected["status"]
            positions[candidate["id"]] = completed
            actual_status_counts[expected["status"]] += 1
            output.write(candidate_text.encode())
            completed += 1
        else:
            raise AssertionError("Missing original reference footer")
        assert all(not stream.read() for stream in streams)
    assert completed == counts["completed_rows"] == summary["rows"]
    assert (
        counts["resolved_source_controls"]
        == actual_status_counts["resolved_source_control"]
    )
    assert (
        counts["unresolved_source_controls"]
        == completed - counts["resolved_source_controls"]
    )
    drift.update(p for p, h in manifest["files"].items() if sha(source / p) != h)
    errors.sort(key=lambda r: positions[r["id"]])
    gaps.sort(key=lambda r: positions[r["id"]])
    partial.rename(records)
    result = {
        "source_manifest_sha256": sha(args.source_manifest),
        "source_drift": sorted(drift),
        "reference_sha256": sha(reference_path),
        "reference_summary_sha256": sha(FIXTURE / "reference-summary.json"),
        "application_protocol_sha256": sha(FIXTURE / "application-protocol.json"),
        "runner_sha256": sha(__file__),
        "shard_protocol_sha256": sha(protocol_path),
        "shard_runner_sha256": protocol["shard_runner_sha256"],
        "shard_receipts": {str(p): sha(p) for p in args.shards},
        "registered_rows": completed,
        "counts": dict(counts),
        "source_status_counts": dict(actual_status_counts),
        "source_collector_counts": summary["counts"],
        "numerical_mismatch_rows": errors,
        "capability_gaps": gaps,
        "records": str(records.resolve().relative_to(ROOT)),
        "records_sha256": sha(records),
        "module_origins": origins,
        "all_original_ids_and_statuses_exactly_once_in_original_order": True,
        "original_sequential_run_superseded": False,
        "calculation_or_acceptance_gates_changed": False,
        "new_model_executions": 0,
        "new_independent_observation_credit": 0,
        "scope": "Complete original cohort, fixed original-index shards; original executor counters are summed only after exact ID/status/order verification. The unchanged original assessor must still evaluate every gate, including strict envelope containment.",
        "full_goal_complete": False,
        "overall_score": None,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    records.with_suffix(".sha256").write_text(sha(records) + "\n")
    print(json.dumps({"counts": result["counts"], "all_original_ids_verified": True}))
    return int(bool(errors or gaps or drift))


if __name__ == "__main__":
    raise SystemExit(main())
