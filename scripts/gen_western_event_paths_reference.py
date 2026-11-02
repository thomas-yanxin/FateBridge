"""Freeze all-pair JPL contacts and longitude-derived stations, without runtime imports."""

import argparse
import hashlib
import itertools
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from gen_western_horary_reference import RAYS, URL, fetch

ROOT = Path(__file__).resolve().parents[1]


def unwrap(rows):
    values = [rows[0][1]]
    for a, b in zip(rows, rows[1:]):
        values.append(values[-1] + (b[1] - a[1] + 180) % 360 - 180)
    return values


def crossings(times, values, rays, **identity):
    events = []
    for i, (a, b) in enumerate(zip(values, values[1:])):
        if a == b:
            continue
        for turn in range(int(min(a, b) // 360) - 1, int(max(a, b) // 360) + 2):
            for ray in rays:
                target = turn * 360 + ray
                if (a < target <= b) or (b <= target < a):
                    events.append(
                        dict(
                            identity,
                            ray_degrees=ray,
                            direction=1 if b > a else -1,
                            julian_day_tt=times[i]
                            + (times[i + 1] - times[i]) * (target - a) / (b - a),
                        )
                    )
    return events


def independent_events(data):
    values = {p: unwrap(rows) for p, rows in data.items()}
    times = next(iter(data.values()))
    times = [r[0] for r in times]
    events = []
    for a, b in itertools.combinations(data, 2):
        relative = [x - y for x, y in zip(values[a], values[b])]
        events.extend(crossings(times, relative, RAYS, kind="contact", bodies=[a, b]))
    for planet, longitude in values.items():
        events.extend(
            crossings(
                times, longitude, range(0, 360, 30), kind="ingress", bodies=[planet]
            )
        )
        # Vertex lies within the central sample's half-grid cell; therefore
        # overlapping triples cannot count the same physical reversal twice.
        for i in range(1, len(times) - 1):
            left, center, right = longitude[i - 1 : i + 2]
            curvature = left - 2 * center + right
            if curvature == 0:
                continue
            fraction = (left - right) / (2 * curvature)
            if -0.5 < fraction <= 0.5:
                events.append(
                    {
                        "kind": "station",
                        "bodies": [planet],
                        "direction": 1 if curvature > 0 else -1,
                        "julian_day_tt": times[i]
                        + fraction * (times[i + 1] - times[i]),
                    }
                )
    return sorted(
        events, key=lambda row: (row["julian_day_tt"], row["kind"], row["bodies"])
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--raw-directory", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(
            "Refusing to overwrite a frozen reference; acquire a separately versioned dataset"
        )
    path = ROOT / "tests/fixtures/western-event-paths-protocol.json"
    protocol = json.loads(path.read_text())
    args.raw_directory.mkdir(parents=True, exist_ok=True)
    jobs = [
        (
            str(i),
            planet,
            body,
            datetime.fromisoformat(start),
            protocol["reference_window_days"],
            protocol["reference_grid_minutes"],
            args.raw_directory,
        )
        for i, start in enumerate(protocol["reference_cases_tt"])
        for planet, body in protocol["reference_bodies"].items()
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(fetch, jobs))
    cases = []
    for i, start in enumerate(protocol["reference_cases_tt"]):
        selected = [r for r in results if r[0] == str(i)]
        data = {planet: rows for _, planet, rows, _ in selected}
        cases.append(
            {
                "case_id": str(i),
                "start_tt_calendar": start,
                "start_julian_day_tt": next(iter(data.values()))[0][0],
                "samples": data,
                "expected": independent_events(data),
                "receipts": {p: receipt for _, p, _, receipt in selected},
                "raw_responses": {
                    p: json.loads(
                        (args.raw_directory / receipt["raw_file"]).read_text()
                    )
                    for _, p, _, receipt in selected
                },
            }
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source": URL,
        "production_imports": False,
        "frame": "Geocentric apparent IAU76/80 ecliptic of date; TT",
        "cases": cases,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        "Frozen",
        len(cases),
        "windows; events",
        [len(c["expected"]) for c in cases],
        flush=True,
    )


if __name__ == "__main__":
    main()
