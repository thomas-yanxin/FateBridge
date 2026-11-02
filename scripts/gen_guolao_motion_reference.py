"""Collect a predeclared Guolao derivative reference without importing the engine.

Run in an isolated pinned ERFA/NumPy environment. Reuse the independently
specified position collector and seven-point derivative, preserve every
requested batch, and do not print reference rates before candidate freezing.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gen_astrodice_apparent_reference import julian_day_tt, project_motion
from gen_astrodice_lunar_chain_reference import fetch, seven_point


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_header(record, target, aliases):
    text = record["response"]["result"].split("$$SOE", 1)[0]
    target_match = re.search(r"Target body name:.*\((\d+)\)", text)
    if target_match is None or int(target_match[1]) not in aliases[str(target)]:
        raise ValueError("Unexpected target reference point")
    if "Center body name: Earth (399)" not in text:
        raise ValueError("Unexpected observer center")
    for label in (
        "Date__(TT)__HR:MN:SC.fff",
        "RA_(ICRF-a-app)",
        "DEC_(ICRF-a-app)",
    ):
        if label not in text:
            raise ValueError("Unexpected apparent frame/time/coordinate header")


def generate(args):
    protocol = json.loads(args.protocol.read_text())
    for package, expected in protocol["versions"].items():
        if importlib.metadata.version(package) != expected:
            raise ValueError("Independent reference dependency changed")
    for name, expected in protocol["collector_source_sha256"].items():
        if digest(Path(__file__).with_name(name)) != expected:
            raise ValueError("Frozen collector/helper identity changed")
    dates = protocol["dates_tt"]
    if len(dates) != len(set(dates)):
        raise ValueError("Duplicate protocol epoch")
    samples = sorted(
        {
            (datetime.fromisoformat(date) + timedelta(seconds=offset)).isoformat()
            for date in dates
            for offset in [0, *protocol["offsets_seconds"]]
        }
    )
    args.archive.mkdir(parents=True, exist_ok=True)
    targets = []
    for body, target in protocol["targets"].items():
        query = {
            "reference_parameters": {
                **protocol["reference_parameters"],
                "COMMAND": f"'{target}'",
            }
        }
        batches = []
        for offset in range(0, len(samples), protocol["batch_size"]):
            requested = samples[offset : offset + protocol["batch_size"]]
            label = f"{body}-{offset:04}"
            original_record = None
            try:
                original_record = fetch(requested, query, args.archive, label)
                record = original_record
                if "error" not in record:
                    validate_header(record, target, protocol["target_id_aliases"])
            except (subprocess.CalledProcessError, ValueError) as error:
                # Keep the original journal if the transport succeeded but
                # its returned contract failed. Never freeze it as valid rows.
                record = {
                    "requested_dates_tt": requested,
                    "error": str(error),
                    "type": type(error).__name__,
                    "rows": [],
                    "original_record": original_record,
                }
                if isinstance(error, subprocess.CalledProcessError):
                    record["raw_response_utf8"] = (error.output or b"").decode(
                        errors="replace"
                    )
                (args.archive / f"{label}-failure.json").write_text(
                    json.dumps(record, indent=2) + "\n"
                )
            batches.append(record)
        source = [r for b in batches if "error" not in b for r in b["rows"]]
        points = {row["date_tt"]: row["icrf_unit_direction"] for row in source}
        if len(points) != len(source) or not set(points) <= set(samples):
            raise ValueError("Duplicate or unrequested reference position")
        rows = []
        for date in dates:
            required = [
                (datetime.fromisoformat(date) + timedelta(seconds=offset)).isoformat()
                for offset in [0, *protocol["offsets_seconds"]]
            ]
            missing = [epoch for epoch in required if epoch not in points]
            row = {
                "date_tt": date,
                "jd_tt": julian_day_tt(date),
                "status": "incomplete" if missing else "available",
                "missing_probe_epochs": missing,
            }
            if not missing:
                rates = {
                    str(step): seven_point(points, datetime.fromisoformat(date), step)
                    for step in protocol["seven_point_steps_seconds"]
                }
                chosen = rates[str(protocol["chosen_step_seconds"])]
                row.update(
                    icrf_unit_direction=points[date],
                    seven_point_derivatives=rates,
                    stencil_difference_arcsec_per_day=math.degrees(
                        math.dist(*rates.values())
                    )
                    * 3600,
                    erfa_display_frame=project_motion(
                        row["jd_tt"],
                        points[date],
                        chosen,
                        protocol["frame_derivative_step_days"],
                    ),
                )
                half_step = project_motion(
                    row["jd_tt"],
                    points[date],
                    chosen,
                    protocol["frame_derivative_step_days"] / 2,
                )
                row["frame_step_difference_arcsec_per_day"] = (
                    abs(
                        half_step["longitude_speed_degrees_per_day"]
                        - row["erfa_display_frame"]["longitude_speed_degrees_per_day"]
                    )
                    * 3600
                )
            rows.append(row)
        targets.append(
            {"body": body, "target_id": target, "batches": batches, "rows": rows}
        )
        print(f"{body}: {len(rows)} requested epochs journalled", flush=True)
    forbidden = [
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in ("fatebridge", "swisseph")
        )
    ]
    if forbidden:
        raise RuntimeError("Reference collector imported the production engine")
    return {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": digest(args.protocol),
        "collector_source_sha256": protocol["collector_source_sha256"],
        "versions": protocol["versions"],
        "forbidden_implementation_imports": forbidden,
        "references": targets,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for name in ("protocol", "archive", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refuse to replace an earlier reference")
    result = generate(args)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
