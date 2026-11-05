"""Compare the solar clock to frozen JPL data; do not grade life predictions."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.utils.solar_time import (
    EQUATION_OF_TIME_METHOD,
    calculate_equation_of_time_minutes,
)

ROOT = Path(__file__).resolve().parents[1]


def _summary(rows: list[dict[str, Any]], tolerance: float) -> dict[str, Any]:
    errors = []
    failed = []
    for row in rows:
        instant = datetime.fromisoformat(row["instant"])
        actual = calculate_equation_of_time_minutes(instant)
        error = abs(actual - row["equation_of_time_minutes"]) * 60
        errors.append(error)
        if error > tolerance:
            failed.append({"instant": row["instant"], "absolute_error_seconds": error})
    return {
        "count": len(rows),
        "within_tolerance": len(rows) - len(failed),
        "maximum_error_seconds": max(errors),
        "mean_error_seconds": math.fsum(errors) / len(errors),
        "failed_count": len(failed),
        "first_failures": failed[:20],
    }


def load_daily_sweep() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    folder = ROOT / "tests/data/bazi_solar_sweep_v1"
    manifest = folder / "manifest.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        != manifest.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen daily manifest changed")
    reference = json.loads(manifest.read_text())
    rows = []
    for source in reference["references"]:
        data = (folder / source["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError("Frozen daily source changed")
        reply = json.loads(gzip.decompress(data))
        table = reply["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        for row in csv.reader(io.StringIO(table)):
            instant = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f")
            if instant.year >= source["stop_year_exclusive"]:
                continue
            dut1 = None if row[4].strip() == "n.a." else float(row[4])
            equation = ((float(row[3]) - 12 + 12) % 24 - 12) * 60 - (dut1 or 0) / 60
            rows.append(
                {
                    "instant": instant.isoformat() + "+00:00",
                    "equation_of_time_minutes": equation,
                }
            )
    if len(rows) != reference["expected_total"] or len(
        {r["instant"] for r in rows}
    ) != len(rows):
        raise ValueError("Incomplete or overlapping daily oracle")
    return rows, reference


def audit_solar(include_sweep: bool = False) -> dict[str, Any]:
    fixture = ROOT / "tests/data/bazi-solar-jpl-v1.json"
    if (
        hashlib.sha256(fixture.read_bytes()).hexdigest()
        != fixture.with_suffix(".sha256").read_text().strip()
    ):
        raise ValueError("Frozen solar oracle changed")
    data = json.loads(fixture.read_text())
    all_rows = {}
    for split in ("development", "reserved"):
        selected = [
            row
            for group in data["references"]
            if group["split"] == split
            for row in group["rows"]
        ]
        all_rows[split] = _summary(selected, data["tolerance_seconds"])
    if include_sweep:
        rows, manifest = load_daily_sweep()
        all_rows["exploratory_daily"] = _summary(rows, manifest["tolerance_seconds"])
        all_rows["exploratory_daily"][
            "classification"
        ] = "exposed independent reference regression; not a blind trial"
    return {
        "method_id": "bazi_solar_equation_independent_audit_v1",
        "equation_of_time_method": EQUATION_OF_TIME_METHOD,
        "evaluation_classification": "current_implementation_on_exposed_independent_reference_not_blind",
        "reference_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "tolerance_seconds": data["tolerance_seconds"],
        "comparisons": all_rows,
        "all_references_within_tolerance": all(
            r["failed_count"] == 0 for r in all_rows.values()
        ),
        "scope": "Equatorial Greenwich apparent-minus-mean solar clock only; UTC/UT1, date, zone and longitude assumptions remain explicit. Does not certify full calendars, classical rules, interpretation or life-event prediction.",
        "independence": "JPL responses retained verbatim. Whole-year split and tolerance fixed before the first Meeus/NOAA candidate evaluation; The current implementation is evaluated on already exposed independent data, not assigned the former candidate's holdout status.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-sweep", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_solar(args.with_sweep)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["comparisons"]))
    return 0 if result["all_references_within_tolerance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
