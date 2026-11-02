"""Freeze JPL directions and independent ERFA projections; no runtime imports."""

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import erfa
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/western-tt-common-frame-v2"


def project(tt, ra, dec, model):
    ra, dec = math.radians(ra), math.radians(dec)
    vector = [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
    delta = tt - 2451545.0
    if model.startswith("Vondrak2011"):
        epoch = 2000 + delta / 365.25
        pole_a, pole_b = erfa.ltpequ(epoch), erfa.ltpecl(epoch)
        epsilon = math.atan2(
            math.hypot(*np.cross(pole_a, pole_b)),
            float(pole_a @ pole_b),
        )
        dpsi, deps = erfa.nut00b(2451545.0, delta)
        matrix = erfa.numat(epsilon, dpsi, deps) @ erfa.ltpb(epoch)
        epsilon += deps
    elif model.startswith("IAU2006_2000A"):
        matrix = erfa.pnm06a(2451545.0, delta)
        epsilon = erfa.obl06(2451545.0, delta) + erfa.nut06a(2451545.0, delta)[1]
    else:
        dpsi, deps = erfa.nut00b(2451545.0, delta)
        epsa, _, _, _, _, matrix = erfa.pn06(2451545.0, delta, dpsi, deps)
        epsilon = epsa + deps
    equator = [math.fsum(float(a) * b for a, b in zip(row, vector)) for row in matrix]
    x = equator[0]
    y = math.cos(epsilon) * equator[1] + math.sin(epsilon) * equator[2]
    z = -math.sin(epsilon) * equator[1] + math.cos(epsilon) * equator[2]
    return [
        math.degrees(math.atan2(y, x)) % 360,
        math.degrees(math.atan2(z, math.hypot(x, y))),
    ]


def acquire(job):
    case_id, name, body, start, plan, raw_dir = job
    begin = datetime.fromisoformat(start)
    params = {
        "format": "json",
        "COMMAND": f"'{body}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TIME_TYPE": "'TT'",
        "QUANTITIES": "'31,45'",
        "REF_SYSTEM": "'ICRF'",
        "APPARENT": "'AIRLESS'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
        "TIME_DIGITS": "'FRACSEC'",
        "START_TIME": f"'{begin.isoformat(sep=' ')}'",
        "STOP_TIME": f"'{(begin + timedelta(days=plan['reference_window_days'])).isoformat(sep=' ')}'",
        "STEP_SIZE": f"'{plan['reference_grid_minutes']}m'",
    }
    raw = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "45",
            "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(params),
        ]
    )
    filename = f"{case_id}-{name}.json"
    (raw_dir / filename).write_bytes(raw)
    response = json.loads(raw)
    if "error" in response:
        raise ValueError(response["error"])
    text = response["result"]
    assert all(s in text for s in ("Date__(TT)", "ObsEcLon", "ICRF-a-app"))
    models = [plan["primary_projection"], *plan["other_projections"]]
    rows = []
    for row in csv.reader(
        io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
    ):
        stamp = row[0].strip()
        fmt = "%Y-%b-%d %H:%M:%S.%f" if "." in stamp else "%Y-%b-%d %H:%M"
        when = datetime.strptime(stamp, fmt)
        tt = 2440587.5 + (when - datetime(1970, 1, 1)).total_seconds() / 86400
        lon, lat, ra, dec = map(float, row[3:7])
        rows.append(
            dict(
                tt=tt,
                jpl_date_ecliptic=[lon, lat],
                icrf=[ra, dec],
                projections={m: project(tt, ra, dec, m) for m in models},
            )
        )
    assert (
        len(rows)
        == plan["reference_window_days"] * 1440 // plan["reference_grid_minutes"] + 1
    )
    return (
        case_id,
        name,
        dict(
            target=body,
            rows=rows,
            receipt=dict(
                parameters=params,
                raw_file=filename,
                response_sha256=hashlib.sha256(raw).hexdigest(),
            ),
        ),
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    raw_dir = args.directory / "raw"
    raw_dir.mkdir()
    protocol = FIXTURE / "protocol.json"
    plan = json.loads(protocol.read_text())
    for name, expected in plan["independent_library_versions"].items():
        assert importlib.metadata.version(name) == expected
    targets = {**plan["native_reference_targets"], **plan["body_control_targets"]}
    jobs = [
        (str(i), name, body, start, plan, raw_dir)
        for i, start in enumerate(plan["reference_cases_tt"])
        for name, body in targets.items()
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(acquire, jobs))
    cases = [
        {
            "case_id": str(i),
            "targets": {
                name: data for case_id, name, data in results if case_id == str(i)
            },
        }
        for i in range(len(plan["reference_cases_tt"]))
    ]
    report = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
        production_imports=False,
        library_versions=plan["independent_library_versions"],
        cases=cases,
    )
    (args.directory / "reference.json.gz").write_bytes(
        gzip.compress(
            json.dumps(report, indent=2, allow_nan=False).encode() + b"\n", mtime=0
        )
    )
    with zipfile.ZipFile(
        args.directory / "raw-responses.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(raw_dir.iterdir()):
            archive.write(path, path.name)
    print(
        "Collected",
        sum(len(t["rows"]) for c in cases for t in c["targets"].values()),
        "TT directions and three independent projections",
        flush=True,
    )


if __name__ == "__main__":
    main()
