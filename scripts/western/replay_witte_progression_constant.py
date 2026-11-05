"""Independently audit original time-angle arithmetic, retaining failed rows.

No FateBridge calculation is imported. An internally inconsistent source
returns exit 1 after writing its report; successful defect-detection tests do
not turn that source into a passing original-conformance result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "src/fatebridge/data/knowledge/witte1923-constant-source.json"
RECORD_SHA256 = "ccfdbaf79be14b5f5a4fef04728584c2b48175ca66382962d29ac5dffd1b5256"


def seconds(parts: list[int]) -> int:
    if len(parts) != 3 or any(type(v) is not int for v in parts):
        raise ValueError("Printed time angle requires integer h/m/s")
    h, m, s = parts
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError("Invalid printed time angle")
    # Accumulation in base60 is independent of the runtime source helper.
    total = 0
    for value in parts:
        total = total * 60 + value
    return total


def replay(record: dict) -> dict:
    rows = []
    for row in record["operations"]:
        terms = []
        for term in row["terms"]:
            sign = term["sign"]
            if type(sign) is not int or sign not in (-1, 1):
                raise ValueError("Invalid printed term sign")
            terms.append(sign * seconds(term["hms"]))
        actual, printed = sum(terms), seconds(row["printed_result_hms"])
        rows.append(
            {
                "id": row["id"],
                "computed_time_seconds": actual,
                "printed_time_seconds": printed,
                "printed_minus_computed_time_seconds": printed - actual,
                "arithmetic_matches_print": actual == printed,
            }
        )
    by_id = {r["id"]: r for r in rows}
    # Diagnose propagation separately. Do not replace any row's printed input.
    chain = (
        by_id["event_time_arc"]["computed_time_seconds"]
        + seconds([0, 2, 8])
        + seconds([21, 9, 35])
        + seconds([0, 40, 0])
    ) % 86400
    labels = record["clock_labels"]
    east = timedelta(seconds=seconds(labels["east_longitude_time"]))
    civil = datetime(*labels["civil_night_date"], *labels["civil_local_clock"])
    noon = datetime(*labels["printed_astronomical_date"], 12) + timedelta(
        seconds=seconds(labels["printed_astronomical_local_hours"])
    )
    return {
        "scope": record["scope"],
        "source": record["source"],
        "operations": rows,
        "operation_count": len(rows),
        "printed_arithmetic_consistent": all(
            r["arithmetic_matches_print"] for r in rows
        ),
        "inconsistent_operation_ids": [
            r["id"] for r in rows if not r["arithmetic_matches_print"]
        ],
        "fully_propagated_diagnostic": {
            "computed_reduced_meridian_time_seconds": chain,
            "printed_reduced_meridian_time_seconds": by_id[
                "progressed_meridian_reduction"
            ]["printed_time_seconds"],
            "printed_minus_propagated_time_seconds": by_id[
                "progressed_meridian_reduction"
            ]["printed_time_seconds"]
            - chain,
            "adopted_as_original_correction": False,
            "scope": "Conditional exact chain with the printed sidereal correction/ephemeris operands retained, not a modern independently recomputed meridian",
        },
        "conditional_clock_labels": {
            "calendar_assumption": "proleptic Gregorian for illustration only; no historical timezone/record certification",
            "civil_early_morning_then_printed_longitude": (civil - east).isoformat(),
            "printed_date_noon_plus_astronomical_hours_then_longitude": (
                noon - east
            ).isoformat(),
            "difference_seconds": int((noon - civil).total_seconds()),
            "either_interpretation_adopted": False,
        },
        "original_progression_time_key_accepted": False,
        "full_original_rulebook_accepted": False,
        "empirical_outcomes": 0,
        "all_four_objectives_validated": False,
        "authority_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-record", type=Path, default=RECORD)
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    raw = args.source_record.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RECORD_SHA256:
        raise ValueError("Frozen progression-constant source checksum mismatch")
    record = json.loads(raw)
    if (
        args.source_pdf
        and hashlib.sha256(args.source_pdf.read_bytes()).hexdigest()
        != record["source"]["source_pdf_sha256"]
    ):
        raise ValueError("Original progression-constant PDF checksum mismatch")
    report = replay(record)
    report["source_record_sha256"] = RECORD_SHA256
    report["source_pdf_bytes_checked"] = bool(args.source_pdf)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")
    return 0 if report["printed_arithmetic_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
