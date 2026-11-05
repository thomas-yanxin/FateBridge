"""Collect frozen TT-only JPL references without importing production code."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from scripts.western.gen_western_horary_reference import fetch, independent_events

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    protocol_path = ROOT / "tests/data/astro/tt_events/protocol.json"
    protocol = json.loads(protocol_path.read_text())
    raw_dir = args.directory / "raw"
    raw_dir.mkdir(parents=True, exist_ok=False)
    jobs = [
        (
            str(i),
            planet,
            body,
            datetime.fromisoformat(start),
            protocol["reference_window_days"],
            protocol["reference_grid_minutes"],
            raw_dir,
        )
        for i, start in enumerate(protocol["reference_cases_tt"])
        for planet, body in protocol["reference_bodies"].items()
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(fetch, jobs))
    cases = []
    for i, start in enumerate(protocol["reference_cases_tt"]):
        selected = [r for r in results if r[0] == str(i)]
        samples = {planet: rows for _, planet, rows, _ in selected}
        cases.append(
            dict(
                case_id=str(i),
                start_tt_calendar=start,
                start_julian_day_tt=samples["Moon"][0][0],
                samples=samples,
                expected=independent_events(samples),
                receipts={planet: receipt for _, planet, _, receipt in selected},
            )
        )
    report = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        production_imports=False,
        cases=cases,
    )
    output = json.dumps(report, indent=2, allow_nan=False).encode() + b"\n"
    (args.directory / "reference.json.gz").write_bytes(gzip.compress(output, mtime=0))
    print("Collected", len(cases), "TT windows without production imports", flush=True)


if __name__ == "__main__":
    main()
