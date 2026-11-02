"""Post-discovery five-point derivative of independent apparent positions.

Use the same isolated fixed ERFA/NumPy environment as the first collector.
All requests are journalled before parsing. No FateBridge/Swiss import.
Neither the first protocol nor its printed-rate failures are replaced.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gen_astrodice_apparent_reference import (
    MONTHS,
    direction_and_rate,
    project_motion,
    request,
)


def difference(points, center, step_seconds):
    times = [center + timedelta(seconds=step_seconds * k) for k in [-2, -1, 1, 2]]
    vectors = [points[t.isoformat()] for t in times]
    return [
        (a - 8 * b + 8 * c - d) * 86400 / (12 * step_seconds)
        for a, b, c, d in zip(*vectors)
    ]


def generate(args):
    protocol = json.loads(args.protocol.read_text())
    initial_protocol = json.loads(args.initial_protocol.read_text())
    initial = json.loads(args.initial_reference.read_text())
    for key, path in [
        ("initial_protocol_sha256", args.initial_protocol),
        ("initial_reference_sha256", args.initial_reference),
    ]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != protocol[key]:
            raise ValueError("Initial reference identity changed")
    for name in ["pyerfa", "numpy"]:
        if importlib.metadata.version(name) != protocol[name + "_version"]:
            raise ValueError("Independent derivative dependency changed")
    args.archive.mkdir(parents=True, exist_ok=True)
    references = []
    for source in initial["references"]:
        samples = sorted(
            {
                (
                    datetime.fromisoformat(row["date_tt"]) + timedelta(seconds=offset)
                ).isoformat()
                for row in source["rows"]
                for offset in protocol["offsets_seconds"]
            }
        )
        points = {}
        batches = []
        for offset in range(0, len(samples), 60):
            dates = samples[offset : offset + 60]
            query = {
                **initial_protocol,
                "reference_parameters": {
                    **initial_protocol["reference_parameters"],
                    "QUANTITIES": protocol["quantities"],
                },
            }
            record = request(source["target_id"], dates, query)
            (args.archive / f"{source['body']}-{offset:04}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n"
            )
            text = record["response"].get("result", "")
            if "$$SOE\n" not in text:
                raise ValueError(
                    "Missing derivative reference batch: "
                    + record["response"].get("error", text)
                )
            rows = []
            for raw in csv.reader(
                io.StringIO(text.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
            ):
                match = re.fullmatch(
                    r"\s*(\d{1,4})-(\w{3})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.\d+\s*",
                    raw[0],
                )
                if match is None:
                    raise ValueError("Unexpected derivative epoch format")
                year, month, day, hour, minute, second = match.groups()
                date = datetime(
                    int(year),
                    MONTHS[month],
                    int(day),
                    int(hour),
                    int(minute),
                    int(second),
                ).isoformat()
                ra, dec = map(float, raw[3:5])
                if not math.isfinite(ra) or not math.isfinite(dec) or date in points:
                    raise ValueError(
                        "Nonfinite or duplicate derivative source position"
                    )
                unit = direction_and_rate(ra, dec, 0, 0)[0]
                points[date] = unit
                rows.append(
                    {
                        "date_tt": date,
                        "ra_degrees": ra,
                        "dec_degrees": dec,
                        "printed_values": [v.strip() for v in raw[3:5]],
                        "icrf_unit_direction": unit,
                    }
                )
            if {r["date_tt"] for r in rows} != set(dates):
                raise ValueError("Derivative batch lost requested samples")
            batches.append({**record, "rows": rows})
        derived = []
        for row in source["rows"]:
            center = datetime.fromisoformat(row["date_tt"])
            rates = {
                str(step): difference(points, center, step)
                for step in protocol["five_point_step_seconds"]
            }
            rate = rates["1800"]
            item = {
                "date_tt": row["date_tt"],
                "jd_tt": row["jd_tt"],
                "icrf_direction_derivative_per_day": rate,
                "five_point_derivatives": rates,
                "stencil_difference_arcsec_per_day": math.degrees(
                    math.dist(rate, rates["3600"])
                )
                * 3600,
                "printed_quantity46_difference_arcsec_per_day": math.degrees(
                    math.dist(rate, row["icrf_direction_derivative_per_day"])
                )
                * 3600,
            }
            if row["date_tt"] in initial_protocol["modern_display_frame_dates_tt"]:
                item["erfa_display_frame"] = project_motion(
                    row["jd_tt"],
                    row["icrf_unit_direction"],
                    rate,
                    protocol["frame_derivative_step_days"],
                )
            derived.append(item)
        references.append(
            {
                "body": source["body"],
                "target_id": source["target_id"],
                "unavailable_requested_epochs": source["unavailable_requested_epochs"],
                "batches": batches,
                "rows": derived,
            }
        )
        print(
            f"{source['body']}: {len(samples)} position probes -> {len(derived)} two-step five-point derivatives",
            flush=True,
        )
    forbidden = [
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in ["fatebridge", "swisseph"]
        )
    ]
    if forbidden:
        raise RuntimeError("Forbidden implementation imported by derivative generator")
    return {
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "position_helper_sha256": hashlib.sha256(
            Path(__file__).with_name("gen_astrodice_apparent_reference.py").read_bytes()
        ).hexdigest(),
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "forbidden_implementation_imports": [],
        "versions": {
            name: importlib.metadata.version(name) for name in ["pyerfa", "numpy"]
        },
        "references": references,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    for name in [
        "protocol",
        "initial-protocol",
        "initial-reference",
        "output",
        "archive",
    ]:
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = generate(args)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
