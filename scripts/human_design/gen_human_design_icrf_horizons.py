"""Independent same-response Horizons31/45 and DE440 ICRF diagnostics.

No FateBridge/Swiss imports. Explicit collection only; tests use retained raw
responses. Never overwrite attempts, reselect epochs or regrade old failures.
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

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "tests/data/human_design/icrf_horizons/evidence/plan.json"
PLAN_SHA256 = "44eb681353feabc2b3b2bb8fdea5944429f5668fb4edc8510e3d6594340a9833"
URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def plan() -> dict:
    raw = PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Prospective ICRF investigation plan changed")
    result: dict = json.loads(raw)
    if len(result["epochs"]) != 17 or len({r["jd_tt"] for r in result["epochs"]}) != 17:
        raise ValueError("All original epochs required")
    return result


def parameters(body: str) -> dict:
    fixed = plan()
    return {
        **fixed["parameters"],
        "COMMAND": f"'{fixed['bodies'][body]}'",
        "TLIST": " ".join(f"'{r['jd_tt']:.17g}'" for r in fixed["epochs"]),
    }


def parse_response(raw: bytes, body: str) -> dict:
    fixed = plan()
    payload = json.loads(raw)
    if "error" in payload:
        raise ValueError("Horizons API error: " + str(payload["error"]))
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
        raise ValueError("Missing or incorrect target/geocenter identity")
    if any(not re.fullmatch(r"DE\d+", m[3].strip()) for m in (target, center)):
        raise ValueError("Unidentified target/observer ephemeris")
    if (
        "Center-site name: GEOCENTRIC" not in text
        or text.count("$$SOE") != 1
        or text.count("$$EOE") != 1
    ):
        raise ValueError("Missing or ambiguous geocentric table")
    headers = [
        line
        for line in text.split("$$SOE")[0].splitlines()
        if "Date_________JDTT" in line
    ]
    if len(headers) != 1:
        raise ValueError("Missing or ambiguous TT column header")
    labels = next(csv.reader([headers[0]]))
    normalized = [re.sub(r"[^a-z0-9]", "", label.lower()) for label in labels]
    if (
        len(labels) != 8
        or normalized[3:5] != ["obseclon", "obseclat"]
        or normalized[5] not in {"raicrfaapp", "raicrfaapparent"}
        or normalized[6] not in {"decicrfaapp", "decicrfaapparent"}
    ):
        raise ValueError(
            "Not the declared TT/quantity31/airless ICRF quantity45 columns: "
            + repr(labels)
        )
    table = text.split("$$SOE")[1].split("$$EOE")[0].strip()
    rows, seen = {}, set()
    for cells in csv.reader(io.StringIO(table)):
        if len(cells) != len(labels):
            raise ValueError("Truncated or extra coordinate columns")
        tt, lon, lat, ra, dec = [float(cells[i]) for i in (0, 3, 4, 5, 6)]
        if not all(math.isfinite(v) for v in (tt, lon, lat, ra, dec)) or not (
            0 <= lon < 360 and 0 <= ra < 360 and -90 <= lat <= 90 and -90 <= dec <= 90
        ):
            raise ValueError("Nonfinite or out-of-range Horizons position")
        matches = [
            r
            for r in fixed["epochs"]
            if abs(tt - r["jd_tt"]) * 86400 <= fixed["epoch_match_tolerance_seconds"]
        ]
        if len(matches) != 1 or matches[0]["id"] in seen:
            raise ValueError("Missing, duplicate or shifted physical TT")
        epoch = matches[0]
        seen.add(epoch["id"])
        rows[epoch["id"]] = {
            **epoch,
            "returned_jd_tt": tt,
            "epoch_residual_seconds": (tt - epoch["jd_tt"]) * 86400,
            "ecliptic_of_date_quantity31": {"longitude": lon, "latitude": lat},
            "icrf_apparent_quantity45": {"right_ascension": ra, "declination": dec},
        }
    if seen != {r["id"] for r in fixed["epochs"]}:
        raise ValueError("Incomplete original TT cohort")
    return {
        "body": body,
        "target_id": int(target[2]),
        "target_name": target[1].strip(),
        "center_id": 399,
        "target_ephemeris": target[3].strip(),
        "center_ephemeris": center[3].strip(),
        "time_scale": "TT",
        "quantity31_frame": "IAU76_80_ecliptic_of_date_apparent",
        "quantity45_frame": "ICRF_airless_apparent",
        "csv_column_labels": labels,
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": [rows[r["id"]] for r in fixed["epochs"]],
    }


def collect(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    records, errors = [], []
    for body in plan()["bodies"]:
        params = parameters(body)
        url = URL + "?" + urlencode(params)
        (directory / f"{body}.request.json").write_text(
            json.dumps(
                {
                    "parameters": params,
                    "url": url,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            + "\n"
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
                raise ValueError("Transport failed")
            record = parse_response(process.stdout, body)
            records.append(record)
            status["parse_status"] = "all17_original_epochs"
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(
                {
                    "body": body,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "unavailable_original_epochs": 17,
                }
            )
            status.update(
                parse_status="rejected", error_type=type(exc).__name__, message=str(exc)
            )
        (directory / f"{body}.status.json").write_text(
            json.dumps(status, indent=2) + "\n"
        )
    result = {
        "method_id": "human_design_same_response_horizons31_45_reference_v1",
        "plan_sha256": PLAN_SHA256,
        "records": records,
        "errors": errors,
        "complete_all34_original_pairs": not errors and len(records) == 2,
        "original_references_replaced": False,
    }
    (directory / "reference.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"records": len(records), "errors": errors}))
    if errors:
        raise ValueError("Incomplete NASA collection; retain and inspect this attempt")


def derive_de440(output: Path) -> None:
    import numpy as np
    from skyfield.api import load, load_file  # type: ignore[import-untyped]
    from skyfield.framelib import ecliptic_frame  # type: ignore[import-untyped]

    if output.exists():
        raise FileExistsError(output)
    fixed = plan()
    for name, expected in fixed["reference_versions"].items():
        if version(name) != expected:
            raise ValueError("Changed reference dependency: " + name)
    path = ROOT / fixed["de440_kernel_path"]
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    if digest.hexdigest() != fixed["de440_kernel_sha256"]:
        raise ValueError("Changed DE440 kernel")
    kernel = load_file(str(path))
    try:
        times = load.timescale(builtin=True).tt_jd(
            np.array([r["jd_tt"] for r in fixed["epochs"]])
        )
        observer = kernel[399].at(times)
        records = []
        for body, target in fixed["bodies"].items():
            position = observer.observe(kernel[target]).apparent()
            ra, dec, _ = position.radec()
            lat, lon, _ = position.frame_latlon(ecliptic_frame)
            rotation = ecliptic_frame.rotation_at(times)
            records.append(
                {
                    "body": body,
                    "target_id": target,
                    "rows": [
                        {
                            **r,
                            "icrf_apparent": {
                                "right_ascension": float(ra.degrees[i]),
                                "declination": float(dec.degrees[i]),
                            },
                            "of_date_apparent": {
                                "longitude": float(lon.degrees[i]),
                                "latitude": float(lat.degrees[i]),
                            },
                            "icrf_to_ecliptic_of_date_rotation": [
                                [float(rotation[j, k, i]) for k in range(3)]
                                for j in range(3)
                            ],
                        }
                        for i, r in enumerate(fixed["epochs"])
                    ],
                }
            )
        value = {
            "method_id": "human_design_de440_icrf_apparent_reference_v1",
            "plan_sha256": PLAN_SHA256,
            "kernel_sha256": digest.hexdigest(),
            "versions": fixed["reference_versions"],
            "records": records,
            "original_reference_replaced": False,
        }
        output.write_text(json.dumps(value, indent=2) + "\n")
    finally:
        kernel.close()
    print("independent ICRF DE440 positions", sum(len(r["rows"]) for r in records))


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
