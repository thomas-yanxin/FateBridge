"""Collect the predeclared continuous 23-hour Horizons grid without engine imports."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raw_protocol = args.protocol.read_bytes()
    if digest(raw_protocol) != args.protocol.with_suffix(".sha256").read_text().strip():
        raise ValueError("Protocol changed after freeze")
    protocol = json.loads(raw_protocol)
    candidate_root = Path(protocol["frozen_candidate_root"])
    expected_hashes = {
        "src/fatebridge/utils/solar_time.py": protocol["candidate_source_sha256"],
        "src/fatebridge/core/ephemeris_runtime.py": protocol["runtime_source_sha256"],
    }
    for name, expected in expected_hashes.items():
        if digest((candidate_root / name).read_bytes()) != expected:
            raise ValueError(f"Frozen candidate changed: {name}")
    raw_grid = (args.protocol.parent / "selected-instants.json").read_bytes()
    if digest(raw_grid) != protocol["selection"]["selected_instants_sha256"]:
        raise ValueError("Selection changed after freeze")
    grid = [datetime.fromisoformat(t) for t in json.loads(raw_grid)]
    stop = datetime.fromisoformat(protocol["selection"]["stop_exclusive"])
    if len(grid) != protocol["selection"]["expected_points"] or any(
        b - a != timedelta(hours=23) for a, b in zip(grid, grid[1:])
    ):
        raise ValueError("Grid is not the declared continuous selection")
    if args.output_dir.exists():
        raise FileExistsError(
            "Use a fresh collection directory; never overwrite a reply"
        )
    args.output_dir.mkdir(parents=True)
    manifest = {
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": digest(raw_protocol),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": protocol["classification"],
        "tolerance_seconds": protocol["tolerance_seconds"],
        "references": [],
    }
    rows = []
    for offset in range(0, len(grid), 9000):
        selected = grid[offset : offset + 9000]
        end = (
            grid[offset + len(selected)] if offset + len(selected) < len(grid) else stop
        )
        params = {
            **protocol["source_parameters"],
            "format": "json",
            "START_TIME": f"'{selected[0].strftime('%Y-%m-%d %H:%M:%S')}'",
            "STOP_TIME": f"'{(end - timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')}'",
        }
        response = subprocess.run(
            [
                "/usr/bin/curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "45",
                protocol["source_url"] + "?" + urlencode(params),
            ],
            capture_output=True,
        )
        name = f"chunk-{offset:06d}.json.gz"
        if response.returncode:
            (args.output_dir / f"chunk-{offset:06d}.error.txt").write_bytes(
                response.stderr
            )
            raise RuntimeError(
                f"Horizons transport failed at offset {offset}: exit {response.returncode}"
            )
        compressed = gzip.compress(response.stdout, mtime=0)
        (args.output_dir / name).write_bytes(compressed)
        reply = json.loads(response.stdout)
        if "error" in reply or "$$SOE\n" not in reply.get("result", ""):
            raise ValueError(f"Incomplete Horizons reply preserved: {name}")
        text = reply["result"]
        table = text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        current = []
        for row in csv.reader(io.StringIO(table)):
            instant = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
                tzinfo=timezone.utc
            )
            mean_clock = (
                instant.hour
                + instant.minute / 60
                + (instant.second + instant.microsecond / 1e6) / 3600
            )
            dut1 = None if row[4].strip() == "n.a." else float(row[4])
            equation = ((float(row[3]) - mean_clock + 12) % 24 - 12) * 60 - (
                dut1 or 0
            ) / 60
            current.append(
                {
                    "instant": instant.isoformat(),
                    "equation_of_time_minutes": equation,
                    "dut1_seconds": dut1,
                    "source_file": name,
                }
            )
        if [r["instant"] for r in current] != [t.isoformat() for t in selected]:
            raise ValueError(
                f"Missing, duplicate or extra instants in preserved {name}"
            )
        manifest["references"].append(
            {
                "file": name,
                "sha256": digest(compressed),
                "raw_sha256": digest(response.stdout),
                "parameters": params,
                "rows": len(current),
                "header": text.split("$$SOE", 1)[0],
            }
        )
        rows.extend(current)
        print(f"Preserved {len(rows)}/{len(grid)} selected instants", flush=True)
    if [r["instant"] for r in rows] != [t.isoformat() for t in grid]:
        raise ValueError("Full reference selection differs from predeclared grid")
    for name, expected in expected_hashes.items():
        if digest((candidate_root / name).read_bytes()) != expected:
            raise ValueError(f"Frozen candidate changed during collection: {name}")
    manifest["actual_total"] = len(rows)
    manifest["missing_dut1"] = sum(r["dut1_seconds"] is None for r in rows)
    reference = (
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    (args.output_dir / "reference.json").write_bytes(reference)
    manifest["reference_sha256"] = digest(reference)
    output = args.output_dir / "manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    output.with_suffix(".sha256").write_text(digest(output.read_bytes()) + "\n")
    print("Reference frozen; candidate has not been evaluated", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
