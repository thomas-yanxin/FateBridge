"""Collect a frozen one-sided lunar reference without importing FateBridge.

Endpoint stencils keep every probe inside the Gregorian/Horizons range. A
least-squares derivative uses exact rational weights on equally spaced nodes.
Degree, node count, both steps and the selected step are fixed before fetch.
Raw responses, missing epochs and transport failures are retained.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

from scripts.astrodice.gen_astrodice_lunar_fractional_reference import fetch


def endpoint_weights(node_count=25, degree=10):
    nodes = range(node_count)
    powers = range(degree + 1)
    matrix = [
        [sum(Fraction(x) ** (i + j) for x in nodes) for j in powers]
        + [Fraction(i == 1)]
        for i in powers
    ]
    for i in powers:
        pivot = matrix[i][i]
        matrix[i] = [v / pivot for v in matrix[i]]
        for j in powers:
            if j != i:
                multiple = matrix[j][i]
                matrix[j] = [a - multiple * b for a, b in zip(matrix[j], matrix[i])]
    coefficients = [row[-1] for row in matrix]
    return [sum(c * x**i for i, c in enumerate(coefficients)) for x in nodes]


def collect(protocol_path, output, archive):
    protocol = json.loads(protocol_path.read_text())
    archive.mkdir(parents=True, exist_ok=False)
    weights = endpoint_weights(protocol["node_count"], protocol["polynomial_degree"])
    if [[w.numerator, w.denominator] for w in weights] != protocol["rational_weights"]:
        raise ValueError("Frozen endpoint geometry changed")
    digest = lambda b: hashlib.sha256(b).hexdigest()
    freeze = {
        "protocol_sha256": digest(protocol_path.read_bytes()),
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "fetch_helper_sha256": digest(
            Path(
                sys.modules[
                    "scripts.astrodice.gen_astrodice_lunar_fractional_reference"
                ].__file__
            ).read_bytes()
        ),
        "before_any_reference_request": True,
    }
    (archive / "collection-freeze.json").write_text(json.dumps(freeze, indent=2) + "\n")
    centers = protocol["development_dates_tt"] + protocol["holdout_dates_tt"]
    wanted = sorted(
        {
            (
                datetime.fromisoformat(d)
                + timedelta(seconds=k * h * protocol["directions"][d])
            ).isoformat()
            for d in centers
            for h in protocol["steps_seconds"]
            for k in range(protocol["node_count"])
        }
    )
    batches, missing = [], []

    def request(dates, label):
        for attempt in range(4):
            tag = f"{label}-attempt{attempt}"
            try:
                return fetch(dates, protocol, archive, tag)
            except subprocess.CalledProcessError as error:
                (archive / f"{tag}-transport-failure.json").write_text(
                    json.dumps(
                        {"returncode": error.returncode, "dates_tt": dates}, indent=2
                    )
                    + "\n"
                )
                if attempt == 3:
                    raise
                time.sleep(2**attempt)

    for start in range(0, len(wanted), 20):
        dates = wanted[start : start + 20]
        record = request(dates, f"batch-{start:04}")
        batches.append(record)
        if "error" in record:
            for index, date in enumerate(dates):
                single = request([date], f"batch-{start:04}-single-{index:02}")
                batches.append(single)
                if "error" in single:
                    if "No ephemeris" not in single["error"]:
                        raise ValueError(single["error"])
                    missing.append({"date_tt": date, "reason": single["error"]})
        print(f"Journalled batch {start}: {len(dates)} requested positions", flush=True)
    points = {
        r["date_tt"]: r["icrf_unit_direction"]
        for b in batches
        for r in b.get("rows", [])
    }
    if set(points) | {r["date_tt"] for r in missing} != set(wanted):
        raise ValueError("Endpoint request coverage changed")
    rows = []
    for date in centers:
        center = datetime.fromisoformat(date)
        direction = protocol["directions"][date]
        probes = {
            (center + timedelta(seconds=direction * k * h)).isoformat()
            for h in protocol["steps_seconds"]
            for k in range(protocol["node_count"])
        }
        absent = sorted(probes - points.keys())
        row = {
            "date_tt": date,
            "jd_tt": center.toordinal()
            + 1721424.5
            + (center.hour * 3600 + center.minute * 60 + center.second) / 86400,
            "cohort": (
                "holdout" if date in protocol["holdout_dates_tt"] else "development"
            ),
            "status": "incomplete" if absent else "available",
            "missing_probes": absent,
        }
        if not absent:
            rates = {
                str(h): [
                    math.fsum(
                        float(w)
                        * (
                            points[
                                (
                                    center + timedelta(seconds=direction * k * h)
                                ).isoformat()
                            ][axis]
                            - points[date][axis]
                        )
                        for k, w in enumerate(weights)
                    )
                    * 86400
                    / (direction * h)
                    for axis in range(3)
                ]
                for h in protocol["steps_seconds"]
            }
            row.update(
                icrf_unit_direction=points[date],
                derivatives=rates,
                icrf_direction_derivative_per_day=rates[
                    str(protocol["chosen_step_seconds"])
                ],
                step_difference_arcsec_per_day=math.degrees(math.dist(*rates.values()))
                * 3600,
            )
        rows.append(row)
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") or k == "swisseph"
        for k in sys.modules
    )
    result = {
        **freeze,
        "versions": {k: importlib.metadata.version(k) for k in ["pyerfa", "numpy"]},
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "batches": batches,
        "rows": rows,
        "missing_probe_epochs": missing,
        "candidate_imported": False,
        "candidate_compared": False,
    }
    with output.open("x") as handle:
        handle.write(
            json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ["protocol", "output", "archive"]:
        parser.add_argument("--" + field, required=True, type=Path)
    args = parser.parse_args()
    collect(args.protocol, args.output, args.archive)
