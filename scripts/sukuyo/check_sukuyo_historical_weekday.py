"""A bounded quoted Hinoo weekday sequence, not a historical-clock oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_historical_calendar import SOURCE
from fatebridge.core.sukuyo_sources import load_source

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "tests/data/sukuyo-historical-weekday-primary.json"


def verify_weekday(capture: Path | None = None) -> dict:
    from scripts.sukuyo.audit_sukuyo_t2465_primary import SATQuotationParser

    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    parser = SATQuotationParser()
    for row in fixture["selected_html_quotations"]:
        parser.feed(row["html"])
    text = "".join("".join(v) for v in parser.lines.values())
    for excerpt in [
        fixture["clock_question_literal"],
        "承和七年正月一日。土曜直日",
        "二日日曜直日。三日月曜直日",
        "四日火曜直日。五日水曜直日。六日木曜直",
        "日。七日金曜直日。八日土曜直日",
    ]:
        if excerpt not in text:
            raise ValueError("Quoted Hinoo weekday witness changed")
    if (
        capture is not None
        and hashlib.sha256(capture.read_bytes()).hexdigest()
        != fixture["source_metadata"]["sha256"]
    ):
        raise ValueError("Full historical weekday capture changed")
    if capture is not None and any(
        row["html"] not in capture.read_text()
        for row in fixture["selected_html_quotations"]
    ):
        raise ValueError("Weekday quotation differs from captured HTML")
    source = load_source(SOURCE)
    months = [m for m in source.data["months"] if [m[1], m[2], m[3]] == [840, 1, False]]
    if len(months) != 1 or len(fixture["expected_labels"]) != 8:
        raise ValueError("Bounded weekday control scope changed")
    rows, errors = [], []
    for offset, label in enumerate(fixture["expected_labels"]):
        civil = date.fromordinal(months[0][0] + offset)
        context = calendar_mansion(
            civil.isoformat(),
            "12:00:00",
            "+09:00",
            calendar_basis="japanese_naoj_historical_utc09",
        )
        actual = day_evidence(context)["weekday"]
        row = {
            "printed_lunar_fields": [840, 1, offset + 1, False],
            "printed_luminary": label,
            "reference_civil_date": civil.isoformat(),
            "calculated_weekday": actual,
        }
        if (
            label != actual["luminary"]
            or [
                context[k]
                for k in ["lunar_year", "lunar_month", "lunar_day", "is_leap_month"]
            ]
            != row["printed_lunar_fields"]
        ):
            errors.append(row)
        rows.append(row)
    return {
        "format": "sukuyo_historical_weekday_control_v1",
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "runtime_reference_sha256": source.sha256,
        "bounded_correlated_sequence_count": 1,
        "printed_weekday_labels_checked": 8,
        "rows": rows,
        "mismatches": errors,
        "full_publisher_capture_hash_checked": capture is not None,
        "quoted_hinoo_attribution_independently_collated": False,
        "historical_daybreak_or_hourly_order_accepted": False,
        "scope": fixture["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_weekday(args.capture)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return bool(result["mismatches"])


if __name__ == "__main__":
    raise SystemExit(main())
