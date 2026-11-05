"""Check four frozen date headings; preserve the two annotation relocations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo import calendar_mansion
from fatebridge.core.sukuyo_shogonji_daily import SOURCE
from fatebridge.core.sukuyo_sources import load_source


def verify_daily_annotations(capture: Path | None = None) -> dict[str, Any]:
    source = load_source(SOURCE)
    bundle = source.data
    fixture = ROOT / "tests/data/sukuyo-shogonji-daily.json"
    original = json.loads(fixture.read_bytes())
    errors: list[Any] = []
    if (
        hashlib.sha256(fixture.read_bytes()).hexdigest()
        != bundle["pre_comparison_transcription_sha256"]
        or original["records"] != bundle["records"]
    ):
        errors.append("pre_comparison_transcription_changed")
    months = {
        (r[1], r[2], r[3]): r
        for r in load_source(
            ROOT / "src/fatebridge/data/sukuyo_japanese_historical_v1.json"
        ).data["months"]
    }
    checks = []
    shifts = []
    for row in original["records"]:
        key = row["lunar_year_author_assignment"], row["month"], row["leap"]
        month = months[key]
        shifts.append(
            row["author_suggested_position"]["day"] - row["original_position"]["day"]
        )
        for role in ("original_position", "author_suggested_position"):
            position = row[role]
            civil = date.fromordinal(month[0] + position["day"] - 1).isoformat()
            calendar = calendar_mansion(
                civil, zone="+09:00", calendar_basis="japanese_naoj_historical_utc09"
            )
            reference = calendar["calendar_reference"]
            check = {
                "record_id": row["id"],
                "source_position_role": role,
                "source_day_ganzhi_kana": position["day_ganzhi_kana"],
                "source_day_ganzhi_normalized": position["day_ganzhi_normalized"],
                "proleptic_gregorian_label": civil,
                "computed_day_ganzhi": reference["day_ganzhi_reference"]["name"],
                "computed_lunar_fields": [
                    calendar[k]
                    for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
                ],
                "current_role_preserved": reference["manuscript_daily_annotations"][
                    "records"
                ][0]["current_date_role"]
                == role,
            }
            check["date_heading_ganzhi_agrees"] = (
                check["computed_day_ganzhi"] == position["day_ganzhi_normalized"]
            )
            check["input_date_unchanged"] = calendar["calendar_date"] == civil
            if not all(
                check[k]
                for k in (
                    "current_role_preserved",
                    "date_heading_ganzhi_agrees",
                    "input_date_unchanged",
                )
            ):
                errors.append(check)
            checks.append(check)
    artifact_checks = []
    if capture is not None:
        term = bundle["term_reference"]
        book = term["rekirin_primary_reference"]
        items = [
            ("rekirin-manifest.json", book["manifest_sha256"]),
            ("ndl-lower-notes.html", term["ndl_reference"]["response_sha256"]),
            ("baba-2017.pdf", term["baba_research_reference"]["pdf_sha256"]),
            (
                "T21n1299-2026R2.xml",
                term["t1299_edition_reference"]["selected_file_sha256"],
            ),
            (
                "T21n1299-2025R1.xml",
                term["t1299_edition_reference"]["control_file_sha256"],
            ),
            *[(r["path"], r["sha256"]) for r in book["selected_images"]],
        ]
        for relative, expected in items:
            actual = hashlib.sha256((capture / relative).read_bytes()).hexdigest()
            artifact_checks.append(
                {"path": relative, "expected_sha256": expected, "actual_sha256": actual}
            )
            if actual != expected:
                errors.append(["captured_artifact_hash_mismatch", relative])
    return {
        "source_bundle_sha256": source.sha256,
        "pre_comparison_transcription_sha256": bundle[
            "pre_comparison_transcription_sha256"
        ],
        "source_annotations": len(original["records"]),
        "related_date_headings": checks,
        "author_suggested_day_shifts": shifts,
        "single_global_day_shift_supported": len(set(shifts)) == 1,
        "source_artifact_hash_checks": artifact_checks,
        "acceptance": bundle["acceptance"],
        "scope": "Four correlated date headings from two author-transcribed annotations. Hash checks identify retained artifacts; they do not independently read glyphs or prove original-scroll positions. No ancient day-boundary, leap-priority, all-recension or empirical acceptance.",
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_daily_annotations(args.capture)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
