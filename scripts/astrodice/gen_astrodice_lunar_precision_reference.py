"""Collect independent Horizons directions for a declared lunar precision plan.

No FateBridge or native ephemeris is imported. Original response bytes, missing
probes and stencil quality remain separate from candidate accuracy.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import ssl
import urllib.request
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlencode

import certifi

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def collect(protocol_path, output):
    protocol = json.loads(protocol_path.read_text())
    centers = protocol["development_dates_tt"] + protocol["holdout_dates_tt"]
    wanted = sorted(
        {
            (datetime.fromisoformat(label) + timedelta(seconds=offset)).isoformat()
            for label in centers
            for offset in [0, *protocol["offsets_seconds"]]
        }
    )
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise ValueError("Reference output or incomplete collection already exists")
    result = {
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "candidate_imported": False,
        "candidate_compared": False,
        "outside_calendar": [],
        "missing_probe_epochs": [],
        "batches": [],
        "rows": [],
    }
    points = {}
    for start in range(0, len(wanted), 20):
        labels = wanted[start : start + 20]
        dates = [datetime.fromisoformat(label) for label in labels]
        params = {
            **protocol["reference_parameters"],
            "TLIST": " ".join(
                f"'{d.year}ad-{MONTHS[d.month-1]}-{d.day:02} {d.hour:02}:{d.minute:02}:{d.second:02}'"
                for d in dates
            ),
        }
        url = URL + "?" + urlencode(params)
        with urllib.request.urlopen(
            url, context=ssl.create_default_context(cafile=certifi.where()), timeout=45
        ) as response:
            raw = response.read()
        decoded = json.loads(raw)
        text = decoded.get("result", "")
        batch = {
            "parameters": params,
            "request_url": url,
            "raw_response_utf8": raw.decode(),
            "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
            "response": decoded,
            "result_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "rows": [],
        }
        result["batches"].append(batch)
        partial.write_text(json.dumps(result, indent=2) + "\n")
        if "$$SOE\n" not in text:
            raise ValueError(
                "Horizons returned no reference table; original response retained"
            )
        if not all(
            value in text
            for value in (
                "Target body name: Moon (301)",
                "Center body name: Earth (399)",
                "ICRF",
                "Date__(TT)",
            )
        ):
            raise ValueError(
                "Horizons lunar target/time/frame differs from declared plan"
            )
        for columns in csv.reader(
            io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
        ):
            match = re.fullmatch(
                r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.0+\s*",
                columns[0],
            )
            if match is None:
                raise ValueError("Unexpected Horizons calendar precision")
            year, month, day, hour, minute, second = match.groups()
            label = datetime(
                int(year),
                MONTHS.index(month) + 1,
                int(day),
                int(hour),
                int(minute),
                int(second),
            ).isoformat()
            ra, dec = map(float, columns[3:5])
            a, d = map(math.radians, (ra, dec))
            direction = [
                math.cos(d) * math.cos(a),
                math.cos(d) * math.sin(a),
                math.sin(d),
            ]
            if (
                label not in labels
                or label in points
                or not all(math.isfinite(x) for x in direction)
            ):
                raise ValueError("Changed, duplicated or nonfinite lunar reference row")
            points[label] = direction
            batch["rows"].append(
                {
                    "date_tt": label,
                    "ra_degrees": ra,
                    "dec_degrees": dec,
                    "printed_values": [x.strip() for x in columns[3:5]],
                    "icrf_unit_direction": direction,
                }
            )
        if {row["date_tt"] for row in batch["rows"]} != set(labels):
            raise ValueError("Horizons reference probe coverage is incomplete")
        partial.write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"Collected {len(points)}/{len(wanted)} independent lunar probes",
            flush=True,
        )
    weights = {
        k: float(
            Fraction((-1) ** (k + 1), k)
            * Fraction(
                math.factorial(6) ** 2, math.factorial(6 - k) * math.factorial(6 + k)
            )
        )
        for k in range(1, 7)
    }
    for label in centers:
        date = datetime.fromisoformat(label)
        derivatives = {
            str(step): [
                math.fsum(
                    weights[k]
                    * (
                        points[(date + timedelta(seconds=k * step)).isoformat()][axis]
                        - points[(date - timedelta(seconds=k * step)).isoformat()][axis]
                    )
                    for k in range(1, 7)
                )
                * 86400
                / step
                for axis in range(3)
            ]
            for step in protocol["steps_seconds"]
        }
        jd = (
            date.toordinal()
            + 1721424.5
            + (date.hour * 3600 + date.minute * 60 + date.second) / 86400
        )
        result["rows"].append(
            {
                "date_tt": label,
                "cohort": (
                    "holdout"
                    if label in protocol["holdout_dates_tt"]
                    else "development"
                ),
                "status": "available",
                "missing_probes": [],
                "jd_tt": jd,
                "icrf_unit_direction": points[label],
                "derivatives": derivatives,
                "icrf_direction_derivative_per_day": derivatives[
                    str(protocol["chosen_step_seconds"])
                ],
                "step_difference_arcsec_per_day": math.degrees(
                    math.dist(*derivatives.values())
                )
                * 3600,
            }
        )
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    partial.unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.protocol, args.output)


if __name__ == "__main__":
    main()
