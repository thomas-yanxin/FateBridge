"""Scheduling proofs and synthetic merge fault tests; no accuracy credit."""

import gzip
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def merge_case(tmp_path, monkeypatch):
    script = ROOT / "scripts/bazi/merge_bazi_future_clock_shards.py"
    spec = importlib.util.spec_from_file_location("_clock_merge", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path.resolve()
    fixture = root / "tests/data/bazi_dayun_future_clocks_v2"
    fixture.mkdir(parents=True)
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "FIXTURE", fixture)

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n")
        path.with_suffix(".sha256").write_text(module.sha(path) + "\n")

    def records(path, rows):
        path.write_bytes(
            gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode(), mtime=0)
        )

    engine = root / "engine/src/fatebridge"
    engine.mkdir(parents=True)
    (engine / "__init__.py").write_text("")
    manifest = root / "manifest.json"
    write(
        manifest,
        {
            "source": str(root / "engine"),
            "files": {"src/fatebridge/__init__.py": module.sha(engine / "__init__.py")},
        },
    )
    runner = root / "scripts/bazi/audit_bazi_dayun_future_clocks_shard.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("# synthetic scheduling witness\n")
    protocol = {
        "source_manifest_sha256": module.sha(manifest),
        "shards": 2,
        "shard_runner_sha256": module.sha(
            root / "scripts/bazi/audit_bazi_dayun_future_clocks_shard.py"
        ),
    }
    write(root / "tests/data/bazi_historical_point_v1/shard-protocol.json", protocol)
    rows = [
        {
            "record_type": "control",
            "id": str(i),
            "status": "resolved_source_control" if i != 3 else "synthetic_unknown",
        }
        for i in range(4)
    ]
    statuses = dict(Counter(r["status"] for r in rows))
    statuses["synthetic_scanned_candidate_cells"] = 1234
    ref = fixture / "reference.jsonl.gz"
    records(
        ref,
        [
            {"record_type": "header", "collector_sha256": "x"},
            *rows,
            {"record_type": "footer", "row_count": 4, "counts": statuses},
        ],
    )
    write(
        fixture / "reference-summary.json",
        {
            "reference_sha256": module.sha(ref),
            "collector_sha256": "x",
            "rows": 4,
            "counts": statuses,
        },
    )
    write(fixture / "application-protocol.json", {})
    shards = []
    for i in range(2):
        path = root / f"shard{i}.json"
        rec = root / f"shard{i}.records.jsonl.gz"
        subset = rows[i::2]
        records(
            rec,
            [
                {
                    "cohort_index": int(r["id"]),
                    "id": r["id"],
                    "source_status": r["status"],
                }
                for r in subset
            ],
        )
        resolved = sum(r["status"] == "resolved_source_control" for r in subset)
        write(
            path,
            {
                "shard_index": i,
                "shard_count": 2,
                "registered_rows": 4,
                "counts": {
                    "completed_rows": 2,
                    "resolved_source_controls": resolved,
                    "unresolved_source_controls": 2 - resolved,
                },
                "source_manifest_sha256": module.sha(manifest),
                "runner_sha256": protocol["shard_runner_sha256"],
                "reference_sha256": module.sha(ref),
                "reference_summary_sha256": module.sha(
                    fixture / "reference-summary.json"
                ),
                "application_protocol_sha256": module.sha(
                    fixture / "application-protocol.json"
                ),
                "records": rec.name,
                "records_sha256": module.sha(rec),
                "source_drift": [],
                "numerical_mismatch_rows": [],
                "capability_gaps": [],
                "module_origins": {},
            },
        )
        shards.append(path)
    output = root / "merged.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--source-manifest",
            str(manifest),
            "--output",
            str(output),
            *map(str, shards),
        ],
    )
    return module, shards, output, write, records


def test_merge_keeps_every_unknown_and_original_order(merge_case):
    module, _, output, _, _ = merge_case
    assert module.main() == 0
    result = json.loads(output.read_text())
    assert result["counts"]["completed_rows"] == 4
    assert result["counts"]["unresolved_source_controls"] == 1
    assert result["all_original_ids_and_statuses_exactly_once_in_original_order"]
    assert not result["calculation_or_acceptance_gates_changed"]
    with gzip.open(output.with_suffix(".records.jsonl.gz"), "rt") as f:
        assert [json.loads(line)["id"] for line in f] == ["0", "1", "2", "3"]


@pytest.mark.parametrize(
    "fault",
    [
        "missing_row",
        "duplicate_id",
        "wrong_runner",
        "wrong_index",
        "wrong_unknown_status",
    ],
)
def test_merge_rejects_forged_or_incomplete_cohorts_even_with_rebound_hashes(
    merge_case, fault
):
    module, shards, output, write, records = merge_case
    path = shards[1]
    report = json.loads(path.read_text())
    rec = module.ROOT / report["records"]
    with gzip.open(rec, "rt") as f:
        rows = [json.loads(line) for line in f]
    if fault == "missing_row":
        rows.pop()
    elif fault == "duplicate_id":
        rows[-1]["id"] = "1"
    elif fault == "wrong_index":
        rows[-1]["cohort_index"] = 2
    elif fault == "wrong_unknown_status":
        rows[-1]["source_status"] = "resolved_source_control"
    elif fault == "wrong_runner":
        report["runner_sha256"] = "0" * 64
    records(rec, rows)
    report["records_sha256"] = module.sha(rec)
    write(path, report)
    with pytest.raises((AssertionError, ValueError)):
        module.main()
    assert not output.exists()
