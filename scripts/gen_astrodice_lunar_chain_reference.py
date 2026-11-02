"""Independent seven-point apparent-position derivatives for a frozen lunar plan.

Maintenance only: isolated pyerfa2.0.1.5/numpy2.5.4. All requests, including
failures, are journalled; no FateBridge/Swiss import or residual selection.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from gen_astrodice_apparent_reference import (
    MONTHS,
    direction_and_rate,
    julian_day_tt,
    project_motion,
)

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"


def fetch(dates, protocol, archive, label):
    month_names = {number: name for name, number in MONTHS.items()}

    def calendar_label(date):
        value = datetime.fromisoformat(date)
        # Horizons requires an AD marker for calendar years below100.
        return f"{value.year}ad-{month_names[value.month]}-{value.day:02} {value.hour:02}:{value.minute:02}:{value.second:02}"

    parameters = {
        **protocol["reference_parameters"],
        "TLIST": " ".join(f"'{calendar_label(date)}'" for date in dates),
    }
    url = URL + "?" + urlencode(parameters)
    raw = subprocess.check_output(
        ["curl", "--fail", "--silent", "--show-error", "--max-time", "45", url]
    )
    response = json.loads(raw)
    record = {
        "parameters": parameters,
        "request_url": url,
        "raw_response_utf8": raw.decode(),
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "response": response,
        "result_sha256": hashlib.sha256(
            response.get("result", "").encode()
        ).hexdigest(),
    }
    (archive / f"{label}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    )
    if "$$SOE\n" not in response.get("result", ""):
        return {
            **record,
            "rows": [],
            "error": response.get("error", response.get("result", "")),
        }
    rows = []
    for raw in csv.reader(
        io.StringIO(response["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
    ):
        match = re.fullmatch(
            r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.\d+\s*", raw[0]
        )
        if match is None:
            raise ValueError("Unexpected lunar reference epoch format")
        year, month, day, hour, minute, second = match.groups()
        date = datetime(
            int(year), MONTHS[month], int(day), int(hour), int(minute), int(second)
        ).isoformat()
        ra, dec = map(float, raw[3:5])
        if not math.isfinite(ra) or not math.isfinite(dec):
            raise ValueError("Nonfinite lunar reference position")
        rows.append(
            {
                "date_tt": date,
                "ra_degrees": ra,
                "dec_degrees": dec,
                "printed_values": [v.strip() for v in raw[3:5]],
                "icrf_unit_direction": direction_and_rate(ra, dec, 0, 0)[0],
            }
        )
    if len(rows) != len(dates) or {r["date_tt"] for r in rows} != set(dates):
        raise ValueError("Lunar request epoch coverage mismatch")
    return {**record, "rows": rows}


def seven_point(points, center, step):
    vectors = [
        points[(center + timedelta(seconds=k * step)).isoformat()]
        for k in [-3, -2, -1, 1, 2, 3]
    ]
    return [
        (-a + 9 * b - 45 * c + 45 * d - 9 * e + f) * 86400 / (60 * step)
        for a, b, c, d, e, f in zip(*vectors)
    ]


def generate(args):
    protocol = json.loads(args.protocol.read_text())
    for name in ["pyerfa", "numpy"]:
        if importlib.metadata.version(name) != protocol[name + "_version"]:
            raise RuntimeError(
                "Lunar reference dependencies differ from frozen versions"
            )
    original = json.loads(args.development_reference.read_text())
    if (
        hashlib.sha256(args.development_reference.read_bytes()).hexdigest()
        != protocol["development_reference_sha256"]
    ):
        raise ValueError("Development reference identity changed")
    centers = protocol["development_dates_tt"] + protocol["holdout_dates_tt"]
    if len(centers) != len(set(centers)):
        raise ValueError("Lunar development and holdout dates overlap")
    samples = sorted(
        {
            (datetime.fromisoformat(c) + timedelta(seconds=offset)).isoformat()
            for c in centers
            for offset in [0, *protocol["offsets_seconds"]]
        }
    )
    args.archive.mkdir(parents=True, exist_ok=True)
    batches = []
    missing = []
    for offset in range(0, len(samples), 20):
        dates = samples[offset : offset + 20]
        record = fetch(dates, protocol, args.archive, f"batch-{offset:04}")
        batches.append(record)
        if "error" in record:
            for i, date in enumerate(dates):
                single = fetch(
                    [date], protocol, args.archive, f"batch-{offset:04}-probe-{i:02}"
                )
                batches.append(single)
                if "error" in single:
                    if "No ephemeris" not in single["error"]:
                        raise ValueError(
                            "Lunar reference collection failed: " + single["error"]
                        )
                    missing.append({"date_tt": date, "reason": single["error"]})
        print(
            f"Journalled {min(offset+20,len(samples))}/{len(samples)} apparent lunar positions",
            flush=True,
        )
    source_rows = [r for b in batches if "error" not in b for r in b["rows"]]
    points = {r["date_tt"]: r["icrf_unit_direction"] for r in source_rows}
    if len(points) != len(source_rows) or set(points) | {
        m["date_tt"] for m in missing
    } != set(samples):
        raise ValueError("Lunar probe coverage is incomplete or duplicated")
    rows = []
    for date in centers:
        required = [
            (datetime.fromisoformat(date) + timedelta(seconds=x)).isoformat()
            for x in [0, *protocol["offsets_seconds"]]
        ]
        unavailable = [d for d in required if d not in points]
        row = {
            "date_tt": date,
            "jd_tt": julian_day_tt(date),
            "cohort": (
                "holdout" if date in protocol["holdout_dates_tt"] else "development"
            ),
            "status": "incomplete" if unavailable else "available",
            "missing_probe_epochs": unavailable,
        }
        if not unavailable:
            rates = {
                str(step): seven_point(points, datetime.fromisoformat(date), step)
                for step in protocol["seven_point_steps_seconds"]
            }
            chosen = rates[str(protocol["chosen_step_seconds"])]
            row.update(
                icrf_unit_direction=points[date],
                icrf_direction_derivative_per_day=chosen,
                seven_point_derivatives=rates,
                stencil_difference_arcsec_per_day=math.degrees(
                    math.dist(*rates.values())
                )
                * 3600,
            )
            if date in protocol["modern_display_dates_tt"]:
                row["erfa_display_frame"] = project_motion(
                    row["jd_tt"],
                    points[date],
                    chosen,
                    protocol["frame_derivative_step_days"],
                )
        rows.append(row)
    if any(
        name == prefix or name.startswith(prefix + ".")
        for name in sys.modules
        for prefix in ["fatebridge", "swisseph"]
    ):
        raise RuntimeError("Lunar reference imported forbidden implementation")
    previous_missing = [
        r["unavailable_requested_epochs"]
        for r in original["references"]
        if r["body"] == "Moon"
    ][0]
    return {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(
            Path(__file__).with_name("gen_astrodice_apparent_reference.py").read_bytes()
        ).hexdigest(),
        "versions": {n: importlib.metadata.version(n) for n in ["pyerfa", "numpy"]},
        "forbidden_implementation_imports": [],
        "batches": batches,
        "missing_probe_epochs": missing,
        "previous_original_missing_epochs": previous_missing,
        "rows": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for name in ["protocol", "development-reference", "archive", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = generate(args)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
