"""Freeze exposed controls for analysis-independent dayun boundary envelopes."""

import argparse
import calendar
import gzip
import hashlib
import json
import runpy
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-dayun-boundary-clock-window-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    protocol = json.loads((STUDY / "protocol.json").read_text())
    assert (
        sha(STUDY / "protocol.json") == (STUDY / "protocol.sha256").read_text().strip()
    )
    assert all(sha(ROOT / p) == h for p, h in protocol["files"].items())
    source = runpy.run_path(
        str(ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/collector-first.py.txt")
    )
    parse = runpy.run_path(str(ROOT / "scripts/build_bazi_birth_fold_reference.py"))
    source["SourceClock"].__init__.__globals__["ROOT"] = ROOT
    instant, micros, epoch = (source[k] for k in ("instant", "micros", "EPOCH"))
    selected, unresolved, counts = {}, [], Counter()
    with gzip.open(
        ROOT / "tests/fixtures/bazi_dayun_future_clocks_v2/reference.jsonl.gz", "rt"
    ) as stream:
        header = json.loads(next(stream))
        for index, line in enumerate(stream):
            row = json.loads(line)
            if row["record_type"] == "footer":
                trailer = row
                continue
            assert row["record_type"] == "control"
            counts[row["status"]] += 1
            if row["status"] != "resolved_source_control":
                unresolved.append(
                    {
                        "source_index": index,
                        "id": row["id"],
                        "status": row["status"],
                        "unresolved_reason": row["unresolved_reason"],
                    }
                )
                continue
            key = (row["zone"], row["direction"], row["source_jie"]["year"] // 50)
            selected.setdefault(key, dict(row, source_index=index, boundary_index=0))
    rows = list(selected.values())
    later = json.loads(
        (
            ROOT / "tests/fixtures/bazi_dayun_future_gaps_v1/later-period-controls.json"
        ).read_text()
    )
    for row in later["controls"]:
        rows.append(
            dict(
                row,
                zone=row["input"]["birth_timezone"],
                direction="reverse",
                status="resolved_source_control",
            )
        )
    assert sum(counts.values()) == 116906 and len(unresolved) == 782
    clocks = {}
    output = []
    for row in rows:
        clock = clocks.setdefault(
            row["zone"], source["SourceClock"](row["zone"], parse["parse_tzif"])
        )
        root = micros(
            datetime.fromisoformat(
                row["source_jie"]["reference_civil_under_frozen_policy"]
            )
            - epoch
        )
        probes = []
        if "expected_grid" in row:
            old = [(p, True) for p in row["expected_grid"]]
            old += [(p, k in (0, 3)) for k, p in enumerate(row["expected_witnesses"])]
        else:
            old = [
                (p, k in (0, 1, 2, 3, 6)) for k, p in enumerate(row["expected_probes"])
            ]
        for probe, safe in old:
            birth = micros(datetime.fromisoformat(probe["birth_utc"]) - epoch)
            wall = source["initial_wall"](birth, root, clock.offset_at(birth))
            wall_at = instant(wall)
            boundaries = []
            unknown_boundaries = []
            for k in range(13):
                year = wall_at.year + k * 10
                shifted = wall_at.replace(
                    year=year,
                    day=min(wall_at.day, calendar.monthrange(year, wall_at.month)[1]),
                )
                try:
                    boundaries.append(clock.resolve(micros(shifted - epoch), birth))
                except ValueError as error:
                    boundaries.append(None)
                    unknown_boundaries.append({"index": k, "reason": str(error)})
            probes.append(
                {
                    "birth_utc": probe["birth_utc"],
                    "safe": safe,
                    "boundaries_utc": [
                        instant(v).isoformat() if v is not None else None
                        for v in boundaries
                    ],
                    "unknown_boundaries": unknown_boundaries,
                }
            )
        analysis = datetime.fromisoformat(row["analysis_at"])
        output.append(
            {
                "id": row["id"],
                "source_index": row.get("source_index"),
                "zone": row["zone"],
                "direction": row["direction"],
                "boundary_index": row["boundary_index"],
                "input": row["input"],
                "uncertainty_minutes": row["uncertainty_minutes"],
                "reference_root_utc": instant(root).isoformat(),
                "probes": probes,
                "contexts": [
                    {
                        "name": "original_analysis_at",
                        "analysis_at": analysis.isoformat(),
                    },
                    {
                        "name": "analysis_plus_180_days",
                        "analysis_at": (analysis + timedelta(days=180)).isoformat(),
                    },
                    {
                        "name": "explicit_age_30",
                        "analysis_at": None,
                        "analysis_age": 30,
                    },
                ],
            }
        )
    result = {
        "protocol_sha256": sha(STUDY / "protocol.json"),
        "collector_sha256": sha(__file__),
        "original_header": header,
        "original_trailer": trailer,
        "source_counts": dict(counts),
        "all_original_unknowns": unresolved,
        "rows": output,
        "control_count": len(output),
        "context_count": len(output) * 3,
        "application_imported": False,
        "original_gates_superseded": False,
        "new_model_executions": 0,
        "full_goal_complete": False,
    }
    args.output.write_bytes(
        gzip.compress(
            (
                json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode(),
            mtime=0,
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ("source_counts", "control_count", "context_count")}
        )
    )


if __name__ == "__main__":
    main()
