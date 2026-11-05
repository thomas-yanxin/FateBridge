"""Compare all selected Shogonji month headings, preserving missing/qualified notes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo import calendar_mansion
from fatebridge.core.sukuyo_shogonji import ALIASES, SOURCE
from fatebridge.core.sukuyo_sources import load_source

CALENDAR = "japanese_naoj_historical_utc09"


def _julian_ordinal(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083 - 1721425


def verify_headers(pdf_path: Path | None = None) -> dict[str, Any]:
    source = load_source(SOURCE)
    bundle = source.data
    fixture_path = ROOT / "tests/data/sukuyo-shogonji-headers.json"
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes)
    errors: list[Any] = []
    if (
        hashlib.sha256(fixture_bytes).hexdigest()
        != bundle["pre_comparison_transcription_sha256"]
        or fixture["records"] != bundle["records"]
    ):
        errors.append("pre_comparison_transcription_changed")
    kernel = load_source(
        ROOT / "src/fatebridge/data/sukuyo_japanese_historical_v1.json"
    )
    months = {(r[1], r[2], r[3]): r for r in kernel.data["months"]}
    records: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
    absent_differences: list[dict[str, Any]] = []
    leap_checks: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    month_counts: Counter[int] = Counter()
    year_lengths: Counter[int] = Counter()
    seen = set()
    for row in bundle["records"]:
        key = row["lunar_year"], row["month"], row["leap"]
        if key in seen or key not in months:
            errors.append(["duplicate_or_missing_month", key])
            continue
        seen.add(key)
        ordinal, year, month, leap, length = months[key]
        civil = date.fromordinal(ordinal)
        common = {"zone": "+09:00", "calendar_basis": CALENDAR}
        host = calendar_mansion(civil.isoformat(), **common)
        reference = host["calendar_reference"]
        states[row["marginal_status"]] += 1
        month_counts[year] += 1
        year_lengths[year] += row["length_days"]
        checks = {
            "length_agrees": length == row["length_days"],
            "ganzhi_agrees": reference["day_ganzhi_reference"]["name"]
            == row["day_one_ganzhi"],
            "weekday_agrees": (
                "月火水木金土日"[civil.weekday()]
                == row["marginal_weekday_normalized_candidate"]
                if row["marginal_weekday_normalized_candidate"] is not None
                else None
            ),
        }
        if any(value is False for value in checks.values()):
            errors.append(["calendar_disagreement", key, checks])
        observed = row["marginal_mansion_normalized_candidate"]
        normalized = observed.translate(ALIASES) if observed else None
        if normalized is not None and normalized != host["month_start_mansion"]:
            errors.append(["host_mansion_disagreement", key])
        halves = {
            half: calendar_mansion(
                civil.isoformat(),
                calendar_profile="hinoo_t1299_host27",
                calendar_day_part=half,
                **common,
            )["profile_calculation"]
            for half in ("first_half", "second_half")
        }
        half_results = {
            half: result["natal_su27"] or result["candidate_su27s"]
            for half, result in halves.items()
        }
        item = {
            **row,
            "proleptic_gregorian_month_first": civil.isoformat(),
            "calendar_checks": checks,
            "host_month_first_mansion": host["month_start_mansion"],
            "hinoo_half_results": half_results,
            "source_half_or_clock_recorded": False,
            "profile_rule_verified_by_annotation": False,
        }
        records.append(item)
        if len(set(map(str, half_results.values()))) > 1:
            (differences if normalized else absent_differences).append(item)
        if leap:
            assignment = halves["first_half"]["short_month_assignment"]
            precedence = assignment["leap_short_month_precedence"]
            leap_checks.append(
                {
                    "lunar_year": year,
                    "month": month,
                    "adjacent_month_first_half": precedence[
                        "adjacent_month_first_half"
                    ],
                    "repeat_true_month_first_half": precedence[
                        "repeat_true_month_first_half"
                    ],
                    "distinguishes_reconstruction_priority": precedence[
                        "adjacent_month_first_half"
                    ]
                    != precedence["repeat_true_month_first_half"],
                    "source_priority_established": False,
                }
            )
    if (
        dict(month_counts) != {1345: 12, 1346: 13, 1347: 12}
        or dict(year_lengths) != {1345: 355, 1346: 383, 1347: 354}
        or dict(states)
        != {
            "clear": 27,
            "absent_in_selected_header": 8,
            "kana_glyph_uncertain": 1,
            "displaced_stamp": 1,
        }
    ):
        errors.append("corpus_or_qualification_coverage_changed")
    style_checks = []
    # Author prose p233 explicitly labels these two dates Julian. This checks
    # date-label conversion only; eclipse astronomy is not reproduced.
    for year, month, day, lunar_month, lunar_day in (
        (1345, 9, 12, 8, 16),
        (1346, 2, 22, 2, 1),
    ):
        gregorian = date.fromordinal(_julian_ordinal(year, month, day))
        expected = date.fromordinal(months[year, lunar_month, False][0]) + timedelta(
            days=lunar_day - 1
        )
        if gregorian != expected:
            errors.append(["author_julian_label_disagreement", year])
        style_checks.append(
            {
                "author_julian_date": f"{year:04}-{month:02}-{day:02}",
                "proleptic_gregorian_date": gregorian.isoformat(),
                "agrees_with_selected_lunar_date": gregorian == expected,
                "eclipse_astronomy_reproduced": False,
            }
        )
    if pdf_path and (
        hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        != bundle["publisher_pdf_sha256"]
    ):
        raise ValueError("Publisher PDF bytes changed")
    return {
        "format": "sukuyo_shogonji_check_v1",
        "source_bundle_sha256": source.sha256,
        "kernel_bundle_sha256": kernel.sha256,
        "pre_comparison_transcription_sha256": hashlib.sha256(
            fixture_bytes
        ).hexdigest(),
        "publisher_pdf_sha256": bundle["publisher_pdf_sha256"],
        "publisher_pdf_identity_checked": pdf_path is not None,
        "month_headers_checked": len(records),
        "year_lengths": dict(year_lengths),
        "marginal_qualification_counts": dict(states),
        "observed_marginals_with_different_hinoo_halves": differences,
        "missing_marginals_with_different_hinoo_halves": absent_differences,
        "leap_priority_checks": leap_checks,
        "author_julian_date_label_checks": style_checks,
        "unresolved_era_header_variants": bundle["year_header_variants"],
        "author_placement_notes_retained": bundle["author_placement_notes"],
        "daily_annotations_transcribed": False,
        "manuscripts_independently_collated": False,
        "source_transcription_blind_to_profile_theory": False,
        "calendar_publishers_may_share_underlying_historical_material": True,
        "ancient_clock_or_rule_priority_admitted": False,
        "real_prediction_samples": 0,
        "records": records,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_headers(args.pdf_path)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
