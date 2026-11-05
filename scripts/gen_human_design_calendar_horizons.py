"""Independent fixed near-conjunction references; never imports the calculator.

Explicit maintenance only. Network attempts are retained, not silently retried
or overwritten. Ordinary tests use frozen responses and do not contact NASA.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/data/human_design/calendar_horizons/evidence/plan.json"
KERNEL_SHA256 = "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def plan() -> dict:
    raw = PLAN.read_bytes()
    value = json.loads(raw)  # type: dict
    if len(value["epochs"]) != 17 or len({r["jd_tt"] for r in value["epochs"]}) != 17:
        raise ValueError("All distinct fixed epochs required")
    return value


def parameters(body: str) -> dict:
    fixed = plan()
    return {
        **fixed["parameters"],
        "COMMAND": f"'{fixed['bodies'][body]}'",
        # Roundtrip the binary64 physical TT; do not convert through UTC.
        "TLIST": " ".join(f"'{r['jd_tt']:.17g}'" for r in fixed["epochs"]),
    }


def parse_response(raw: bytes, body: str) -> dict:
    fixed = plan()
    payload = json.loads(raw)
    if "error" in payload:
        raise ValueError("Horizons returned an API error: " + str(payload["error"]))
    text = payload["result"]
    target = re.search(
        r"Target body name:\s*(.*?)\((\d+)\)\s*\{source:\s*([^}]+)\}", text
    )
    center = re.search(
        r"Center body name:\s*(.*?)\((\d+)\)\s*\{source:\s*([^}]+)\}", text
    )
    if (
        target is None
        or center is None
        or int(target[2]) != fixed["bodies"][body]
        or int(center[2]) != 399
    ):
        raise ValueError("Wrong or missing target/observer identity")
    if not re.fullmatch(r"DE\d+", target[3].strip()) or not re.fullmatch(
        r"DE\d+", center[3].strip()
    ):
        raise ValueError("Unidentified JPL physical ephemeris")
    if (
        "Center-site name: GEOCENTRIC" not in text
        or "Date_________JDTT" not in text
        or "ObsEcLon" not in text
        or "ObsEcLat" not in text
    ):
        raise ValueError("Wrong or missing geocentric TT quantity31 context")
    if text.count("$$SOE") != 1 or text.count("$$EOE") != 1:
        raise ValueError("Missing or duplicate ephemeris table")
    table = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0].strip()
    rows, seen = [], set()
    for cells in csv.reader(io.StringIO(table)):
        if len(cells) < 5:
            raise ValueError("Truncated Horizons coordinate row")
        jd, lon, lat = (float(cells[i]) for i in (0, 3, 4))
        if not all(math.isfinite(x) for x in (jd, lon, lat)) or not (
            0 <= lon < 360 and -90 <= lat <= 90
        ):
            raise ValueError("Unavailable or nonfinite Horizons coordinate")
        matches = [
            r
            for r in fixed["epochs"]
            if abs(r["jd_tt"] - jd) * 86400 <= fixed["epoch_match_tolerance_seconds"]
        ]
        if len(matches) != 1 or matches[0]["id"] in seen:
            raise ValueError("Unmatched, ambiguous or duplicate TT epoch")
        match = matches[0]
        seen.add(match["id"])
        rows.append(
            {
                **match,
                "returned_jd_tt": jd,
                "epoch_residual_seconds": (jd - match["jd_tt"]) * 86400,
                "longitude": lon,
                "latitude": lat,
            }
        )
    if seen != {r["id"] for r in fixed["epochs"]}:
        raise ValueError("Incomplete fixed Horizons cohort")
    lookup = {r["id"]: r for r in rows}
    return {
        "body": body,
        "target_id": int(target[2]),
        "target_name": target[1].strip(),
        "target_ephemeris": target[3].strip(),
        "center_id": int(center[2]),
        "center_ephemeris": center[3].strip(),
        "time_scale": "TT",
        "quantity": 31,
        "frame": "observer_centered_IAU76_80_ecliptic_of_date_apparent",
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": [lookup[r["id"]] for r in fixed["epochs"]],
    }


def collect(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    records = []
    for body in plan()["bodies"]:
        params = parameters(body)
        url = URL + "?" + urlencode(params)
        request = {
            "parameters": params,
            "url": url,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        (directory / f"{body}.request.json").write_text(
            json.dumps(request, indent=2) + "\n"
        )
        process = subprocess.run(
            ["curl", "--fail", "--silent", "--show-error", "--max-time", "45", url],
            capture_output=True,
        )
        (directory / f"{body}.response.json").write_bytes(process.stdout)
        (directory / f"{body}.stderr.log").write_bytes(process.stderr)
        status = {
            "curl_exit_code": process.returncode,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "raw_sha256": hashlib.sha256(process.stdout).hexdigest(),
        }
        try:
            if process.returncode:
                raise RuntimeError("Horizons transport failed")
            parsed = parse_response(process.stdout, body)
            records.append(parsed)
            status["parse_status"] = "complete_fixed_cohort"
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            status.update(
                parse_status="rejected", error_type=type(exc).__name__, error=str(exc)
            )
            raise
        finally:
            (directory / f"{body}.status.json").write_text(
                json.dumps(status, indent=2) + "\n"
            )
    result = {
        "method_id": "human_design_near_conjunction_horizons_reference_v1",
        "records": records,
        "scope": "34 fixed investigative positions, source and TT identity checked; no replacement or regrading of the original full calendar comparison.",
    }
    (directory / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "observations": sum(len(r["rows"]) for r in records),
                "targets": [r["target_name"] for r in records],
            }
        )
    )


def derive_de440(output: Path) -> None:
    import numpy as np
    from skyfield.api import load, load_file  # type: ignore[import-untyped]
    from skyfield.framelib import ecliptic_frame  # type: ignore[import-untyped]

    if output.exists():
        raise FileExistsError(output)
    fixed = plan()
    for name, expected in fixed["reference_versions"].items():
        if version(name) != expected:
            raise ValueError("Reference dependency changed: " + name)
    path = ROOT / fixed["de440_kernel_path"]
    raw = path.read_bytes()
    if (
        hashlib.sha256(raw).hexdigest() != KERNEL_SHA256
        or hashlib.md5(raw).hexdigest() != fixed["de440_kernel_md5"]
    ):
        raise ValueError("Original DE440 kernel identity changed")
    kernel = load_file(str(path))
    try:
        ts = load.timescale(builtin=True)
        times = ts.tt_jd(np.array([r["jd_tt"] for r in fixed["epochs"]]))
        observer = kernel[399].at(times)
        records = []
        for body, target in fixed["bodies"].items():
            apparent = observer.observe(kernel[target]).apparent()
            lat, lon, distance = apparent.frame_latlon(ecliptic_frame)
            rows = [
                {
                    **r,
                    "longitude": float(lon.degrees[i]),
                    "latitude": float(lat.degrees[i]),
                    "distance_au": float(distance.au[i]),
                }
                for i, r in enumerate(fixed["epochs"])
            ]
            records.append({"body": body, "target_id": target, "rows": rows})
        result = {
            "method_id": "human_design_near_conjunction_de440_reference_v1",
            "kernel_sha256": KERNEL_SHA256,
            "versions": fixed["reference_versions"],
            "records": records,
            "scope": "Same frozen34 TT/target pairs, independently generated with original DE440/Skyfield conventions; not a calculator-derived oracle.",
        }
        output.write_text(json.dumps(result, indent=2) + "\n")
    finally:
        kernel.close()
    print("independent DE440 positions", sum(len(r["rows"]) for r in records))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["horizons", "de440"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.phase == "horizons":
        collect(args.output)
    else:
        derive_de440(args.output)


if __name__ == "__main__":
    main()
