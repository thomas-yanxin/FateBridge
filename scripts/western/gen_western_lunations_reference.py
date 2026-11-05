"""Collect JPL apparent-longitude lunations, without FateBridge imports.

USNO's minute table only seeds four-minute brackets. All root evaluations use
NASA/JPL Sun and Moon coordinates. The fixed acceptance tolerance is 15 seconds;
it must not be tuned to subsequent FateBridge results. Run only to deliberately
refresh external data; ordinary tests are offline.
"""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.western.gen_western_returns_reference import fetch, offset

ROOT = Path(__file__).resolve().parents[2]
TOLERANCE_SECONDS = 15


def coordinates(times):
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(fetch, body, times=times) for body in (10, 301)]
        sun, sun_record = tasks[0].result()
        moon, moon_record = tasks[1].result()
    if [row[0] for row in sun] != [row[0] for row in moon]:
        raise ValueError("NASA Sun/Moon timestamps differ")
    if len(sun) != len(times):
        raise ValueError("NASA response omitted requested timestamps")
    return [(s[0], (m[1] - s[1]) % 360) for s, m in zip(sun, moon)], [
        sun_record,
        moon_record,
    ]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tests/fixtures/western-lunations-horizons.json",
    )
    args = parser.parse_args()
    anchors = json.loads(
        (ROOT / "tests/fixtures/western-usno-lunations-2026.json").read_text()
    )
    states = []
    initial_times = []
    for case in anchors["cases"]:
        # Nominal UT1 components are deliberately only approximate UTC anchors.
        # The wide bracket accommodates their minute resolution and DUT1.
        centre = datetime.fromisoformat(case["nominal_ut1"]).replace(
            tzinfo=timezone.utc
        )
        left, right = centre - timedelta(seconds=120), centre + timedelta(seconds=120)
        initial_times.extend((left, right))
        states.append(
            {"type": case["type"], "target": 0 if case["type"] == "new" else 180}
        )
    initial, recordings = coordinates(initial_times)
    for index, state in enumerate(states):
        state["left"], phase_left = initial[2 * index]
        state["right"], phase_right = initial[2 * index + 1]
        state["f_left"] = offset(phase_left, state["target"])
        state["f_right"] = offset(phase_right, state["target"])
        if not state["f_left"] < 0 < state["f_right"]:
            raise ValueError("NASA did not independently bracket a lunation")
    for _ in range(4):
        times = [
            state["left"]
            + (state["right"] - state["left"])
            * (-state["f_left"] / (state["f_right"] - state["f_left"]))
            for state in states
        ]
        rows, records = coordinates(times)
        recordings.extend(records)
        for state, (at, phase) in zip(states, rows):
            residual = offset(phase, state["target"])
            state["event"], state["residual"] = at, residual
            if residual >= 0:
                state["right"], state["f_right"] = at, residual
            else:
                state["left"], state["f_left"] = at, residual
    cases = []
    for state in states:
        if abs(state["residual"]) > 1e-6:
            raise ValueError("NASA root refinement did not converge")
        cases.append(
            {
                "type": state["type"],
                "event_utc": state["event"].isoformat(),
                "target_elongation": state["target"],
                "oracle_residual_arcseconds": abs(state["residual"]) * 3600,
            }
        )
    report = {
        "source": "https://ssd.jpl.nasa.gov/api/horizons.api",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "scope": "All 25 geocentric tropical apparent-longitude New/Full Moons in 2026; UTC, Horizons last-known leap assumption",
        "tolerance_seconds": TOLERANCE_SECONDS,
        "oracle_method": "USNO anchors, independent JPL brackets and four secant evaluations; no FateBridge imports or calculated answers",
        "cases": cases,
        "recordings": recordings,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    target = args.output
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Frozen {len(cases)} JPL lunation roots with {len(recordings)} recordings")


if __name__ == "__main__":
    main()
