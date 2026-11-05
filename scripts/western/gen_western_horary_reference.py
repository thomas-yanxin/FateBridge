"""Freeze JPL lunar sign-exit/contact references without production imports.

The protocol and tolerances exist before acquisition. Linear interpolation of
the independent 10-minute JPL grid is distinct from the native root solver.
"""

import argparse
import csv
import hashlib
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
RAYS = {
    0: "conjunction",
    60: "sextile",
    90: "square",
    120: "trine",
    180: "opposition",
    240: "trine",
    270: "square",
    300: "sextile",
}


def fetch(job):
    key, planet, body, start, days, minutes, raw_dir = job
    params = {
        "format": "json",
        "COMMAND": f"'{body}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TIME_TYPE": "'TT'",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
        "TIME_DIGITS": "'FRACSEC'",
        "START_TIME": f"'{start.isoformat(sep=' ')}'",
        "STOP_TIME": f"'{(start + timedelta(days=days)).isoformat(sep=' ')}'",
        "STEP_SIZE": f"'{minutes}m'",
    }
    raw = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "3",
            "--retry-delay",
            "1",
            "--max-time",
            "45",
            URL + "?" + urlencode(params),
        ]
    )
    response = json.loads(raw)
    if "error" in response:
        raise ValueError(response["error"])
    result = response["result"]
    if "Date__(TT)" not in result:
        raise ValueError("Independent time scale is not confirmed as TT")
    rows = []
    table = result.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    for row in csv.reader(io.StringIO(table)):
        stamp = row[0].strip()
        fmt = "%Y-%b-%d %H:%M:%S.%f" if "." in stamp else "%Y-%b-%d %H:%M"
        when = datetime.strptime(stamp, fmt)
        jd = 2440587.5 + (when - datetime(1970, 1, 1)).total_seconds() / 86400
        rows.append([jd, float(row[3]), float(row[4])])
    expected = int(days * 1440 / minutes) + 1
    assert len(rows) == expected, (planet, len(rows), expected)
    target = raw_dir / f"{key}-{planet}.json"
    target.write_bytes(raw)
    return (
        key,
        planet,
        rows,
        {
            "parameters": params,
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_file": target.name,
        },
    )


def independent_events(data):
    moon = data["Moon"]
    unwrapped_moon = [moon[0][1]]
    for previous, current in zip(moon, moon[1:]):
        unwrapped_moon.append(
            unwrapped_moon[-1] + (current[1] - previous[1] + 180) % 360 - 180
        )
    next_boundary = (int(moon[0][1] // 30) + 1) * 30

    def interpolate(i, low, high, target):
        return moon[i][0] + (moon[i + 1][0] - moon[i][0]) * (target - low) / (
            high - low
        )

    exits = [
        interpolate(i, a, b, next_boundary)
        for i, (a, b) in enumerate(zip(unwrapped_moon, unwrapped_moon[1:]))
        if a < next_boundary <= b
    ]
    assert len(exits) == 1
    exit_tt = exits[0]
    contacts = []
    for planet, samples in data.items():
        if planet == "Moon":
            continue
        values = [moon[0][1] - samples[0][1]]
        for i in range(1, len(moon)):
            relative = moon[i][1] - samples[i][1]
            previous = moon[i - 1][1] - samples[i - 1][1]
            values.append(values[-1] + (relative - previous + 180) % 360 - 180)
        for i, (a, b) in enumerate(zip(values, values[1:])):
            assert b > a
            for turn in range(int(a // 360) - 1, int(b // 360) + 2):
                for ray, aspect in RAYS.items():
                    target = ray + 360 * turn
                    if a < target <= b:
                        when = interpolate(i, a, b, target)
                        if when < exit_tt:
                            contacts.append(
                                {
                                    "other": planet,
                                    "aspect": aspect,
                                    "ray_degrees": ray,
                                    "julian_day_tt": when,
                                }
                            )
    contacts.sort(
        key=lambda row: (row["julian_day_tt"], row["other"], row["ray_degrees"])
    )
    return {
        "sign_exit_julian_day_tt": exit_tt,
        "contacts": contacts,
        "void_of_course": not contacts,
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-directory", type=Path, required=True)
    args = parser.parse_args()
    protocol_path = ROOT / "tests/fixtures/western-horary-motion-protocol.json"
    protocol = json.loads(protocol_path.read_text())
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
        data = {p: rows for _, p, rows, _ in selected}
        cases.append(
            {
                "case_id": str(i),
                "start_tt_calendar": start,
                "start_julian_day_tt": data["Moon"][0][0],
                "samples": data,
                "expected": independent_events(data),
                "receipts": {p: receipt for _, p, _, receipt in selected},
            }
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "source": URL,
        "frame": "geocentric apparent tropical ecliptic of date; TT",
        "production_imports": False,
        "cases": cases,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("Collected", len(cases), "independent lunar sign/contact windows", flush=True)


if __name__ == "__main__":
    main()
