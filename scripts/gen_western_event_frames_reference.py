"""Add frozen JPL apparent inertial directions and independent ERFA frame projections.

Maintenance-only isolated ERFA environment; no FateBridge or Swiss imports.
The initial date-frame comparison, its failure and tolerances are retained.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import erfa
from gen_western_event_paths_reference import independent_events, unwrap
from refine_western_station_reference import vertex

ROOT = Path(__file__).resolve().parents[1]
URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def project(tt, ra, dec, variant):
    ra, dec = math.radians(ra), math.radians(dec)
    unit = [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
    delta = tt - 2451545.0
    if variant.endswith("2000A_true_ecliptic_of_date"):
        matrix = erfa.pnm06a(2451545.0, delta)
        epsilon = erfa.obl06(2451545.0, delta) + erfa.nut06a(2451545.0, delta)[1]
    else:
        dpsi, deps = erfa.nut00b(2451545.0, delta)
        epsa, _, _, _, _, matrix = erfa.pn06(2451545.0, delta, dpsi, deps)
        epsilon = epsa + deps
    equator = [math.fsum(float(a) * b for a, b in zip(row, unit)) for row in matrix]
    x = equator[0]
    y = math.cos(epsilon) * equator[1] + math.sin(epsilon) * equator[2]
    z = -math.sin(epsilon) * equator[1] + math.cos(epsilon) * equator[2]
    return [
        math.degrees(math.atan2(y, x)) % 360,
        math.degrees(math.atan2(z, math.hypot(x, y))),
    ]


def acquire(job):
    case_id, planet, body, start, plan, archive = job
    begin = datetime.fromisoformat(start)
    params = {
        **plan["reference_parameters"],
        "format": "json",
        "COMMAND": f"'{body}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "START_TIME": f"'{begin.isoformat(sep=' ')}'",
        "STOP_TIME": f"'{(begin+timedelta(days=21)).isoformat(sep=' ')}'",
        "STEP_SIZE": "'60m'",
    }
    raw = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            "3",
            "--max-time",
            "45",
            URL + "?" + urlencode(params),
        ]
    )
    filename = f"{case_id}-{planet}.json"
    (archive / filename).write_bytes(raw)
    response = json.loads(raw)
    if "error" in response:
        raise ValueError(response["error"])
    text = response["result"]
    assert all(s in text for s in ["Date__(TT)", "ObsEcLon", "ICRF-a-app"])
    rows = []
    for line in csv.reader(
        io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
    ):
        t = datetime.strptime(line[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
        tt = 2440587.5 + (t - datetime(1970, 1, 1)).total_seconds() / 86400
        lon, lat, ra, dec = map(float, line[3:7])
        rows.append(
            {
                "julian_day_tt": tt,
                "jpl_date_ecliptic": [lon, lat],
                "icrf_ra_dec": [ra, dec],
                "projections": {
                    v: project(tt, ra, dec, v) for v in plan["frame_models"]
                },
            }
        )
    assert len(rows) == 505
    return (
        case_id,
        planet,
        rows,
        dict(
            parameters=params,
            response_sha256=hashlib.sha256(raw).hexdigest(),
            raw_file=filename,
            raw_response_utf8=raw.decode(),
        ),
    )


def event_reference(samples):
    original = independent_events(samples)
    refined = []
    for event in original:
        row = dict(event)
        if event["kind"] == "station":
            data = samples[event["bodies"][0]]
            values = unwrap(data)
            i = min(
                range(len(data)), key=lambda i: abs(data[i][0] - event["julian_day_tt"])
            )
            offset, uncertainty = vertex(values, i, 12)
            short, _ = vertex(values, i, 6)
            row.update(
                julian_day_tt=data[i][0] + offset,
                spacing_stability_seconds=abs(offset - short) * 86400,
                coordinate_rounding_time_bound_seconds=uncertainty,
            )
        refined.append(row)
    return refined


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--reference-point-control", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Frozen references cannot be overwritten")
    pp = ROOT / "tests/fixtures/western-event-frames-protocol.json"
    plan = json.loads(pp.read_text())
    initial = ROOT / "tests/fixtures/western-event-paths-horizons.json"
    assert (
        hashlib.sha256(initial.read_bytes()).hexdigest()
        == plan["initial_reference_sha256"]
    )
    for name, ver in plan["independent_library_versions"].items():
        assert importlib.metadata.version(name) == ver
    first = json.loads(initial.read_text())
    bodies = json.loads(
        (ROOT / "tests/fixtures/western-event-paths-protocol.json").read_text()
    )["reference_bodies"]
    control = None
    if args.reference_point_control:
        control_path = (
            ROOT / "tests/fixtures/western-event-reference-points-protocol.json"
        )
        control = json.loads(control_path.read_text())
        bodies = {
            p: control["native_reference_targets"][p]
            for p in control["control_acquisition_bodies"]
        }
    args.archive.mkdir(parents=True, exist_ok=True)
    jobs = [
        (c["case_id"], p, body, c["start_tt_calendar"], plan, args.archive)
        for c in first["cases"]
        for p, body in bodies.items()
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, jobs))
    if control:
        previous = ROOT / "tests/fixtures/western-event-frames-horizons.json"
        assert (
            hashlib.sha256(previous.read_bytes()).hexdigest()
            == control["prior_common_frame_reference_sha256"]
        )
        for c in json.loads(previous.read_text())["cases"]:
            for planet, rows in c["rows"].items():
                if planet not in bodies:
                    results.append((c["case_id"], planet, rows, c["receipts"][planet]))
        # Preserve the original native/traditional planet ordering, which
        # defines the orientation of the signed ray IDs in both comparisons.
        ordering = list(
            json.loads(
                (ROOT / "tests/fixtures/western-event-paths-protocol.json").read_text()
            )["reference_bodies"]
        )
        results.sort(key=lambda row: (row[0], ordering.index(row[1])))
    cases = []
    for c in first["cases"]:
        chosen = [r for r in results if r[0] == c["case_id"]]
        frames = {}
        for variant in plan["frame_models"]:
            samples = {
                p: [[r["julian_day_tt"], *r["projections"][variant]] for r in rows]
                for _, p, rows, _ in chosen
            }
            frames[variant] = {"samples": samples, "events": event_reference(samples)}
        cases.append(
            {
                "case_id": c["case_id"],
                "start_julian_day_tt": c["start_julian_day_tt"],
                "rows": {p: rows for _, p, rows, _ in chosen},
                "frames": frames,
                "receipts": {p: receipt for _, p, _, receipt in chosen},
            }
        )
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(pp.read_bytes()).hexdigest(),
        "production_imports": False,
        "swiss_imports": False,
        "library_versions": plan["independent_library_versions"],
        "initial_reference_sha256": plan["initial_reference_sha256"],
        "source": URL,
        "cases": cases,
    }
    if control:
        result["reference_point_control_protocol_sha256"] = hashlib.sha256(
            control_path.read_bytes()
        ).hexdigest()
        result["native_reference_targets"] = control["native_reference_targets"]
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        "Collected two same-epoch windows and independent frame projections", flush=True
    )


if __name__ == "__main__":
    main()
