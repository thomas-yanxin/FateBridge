"""Selected T30107 integer formula and a separate printed mean-day example."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo_weekday import SOURCE, classical_weekday_arithmetic

FIXTURE = ROOT / "tests/data/sukuyo-weekday-arithmetic-primary.json"


def verify_arithmetic(capture_dir: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    source = json.loads(SOURCE.read_bytes())
    if source["general_formula"] != fixture["general_formula"]:
        raise ValueError("Selected manuscript clauses or constants changed")
    checked_captures = []
    if capture_dir is not None:
        for row in fixture["captured_pages"]:
            raw = (capture_dir / row["file"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("Manuscript image fingerprint changed")
            checked_captures.append(row["file"])
        manifest = capture_dir / "utokyo-T30107-manifest.json"
        if (
            hashlib.sha256(manifest.read_bytes()).hexdigest()
            != fixture["manifest_sha256"]
        ):
            raise ValueError("Manuscript manifest changed")
    example = fixture["printed_recalculation"]
    result = classical_weekday_arithmetic(example["elapsed_years"], 0, 0)
    trace = result["trace"]
    printed = {
        key: {"printed": expected, "computed": trace[key]}
        for key, expected in example["printed_integer_steps"].items()
    }
    errors = [key for key, row in printed.items() if row["printed"] != row["computed"]]
    separate_numerator = trace["nominal_days"] * 11
    if separate_numerator != example["printed_unbiased_numerator"]:
        errors.append("separate_printed_unbiased_numerator")
    counterexamples = []
    rational_errors = []
    case_count = 0
    # One full declared 19-year intercalation cycle, with three day counts.
    # This is an algebraic cross-check, not 741 observed historical dates.
    for years in range(19):
        for months in range(13):
            for days in (0, 1, 30):
                case_count += 1
                count = years * 12 + months
                leaps = Fraction(count * 7, 228).__floor__()
                nominal = (count + leaps) * 30 + days
                expected = nominal - Fraction(nominal * 11 + 500, 703).__floor__()
                actual = classical_weekday_arithmetic(years, months, days)["trace"]
                if expected != actual["accumulated_days"]:
                    rational_errors.append([years, months, days])
                wrong_leaps = Fraction(years * 12 * 7, 228).__floor__()
                if wrong_leaps != leaps and days == 1:
                    wrong_nominal = (count + wrong_leaps) * 30 + days
                    wrong_days = (
                        wrong_nominal
                        - Fraction(wrong_nominal * 11 + 500, 703).__floor__()
                    )
                    counterexamples.append(
                        {
                            "elapsed_counts": [years, months, days],
                            "source_order_accumulated_days": expected,
                            "wrong_post_intercalation_months_accumulated_days": wrong_days,
                            "difference_days": expected - wrong_days,
                        }
                    )
    return {
        "format": "sukuyo_t30107_weekday_arithmetic_check_v1",
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "runtime_source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "printed_integer_prefix_controls": printed,
        "printed_prefix_errors": errors,
        "separate_recalculation": {
            "printed_numerator_without_bias": separate_numerator,
            "general_numerator_with_bias": trace["omission_numerator"],
            "general_omitted_integer_days": trace["omitted_days"],
            "general_omission_remainder": trace["omission_remainder"],
            "same_full_algorithm_claimed": False,
            "later_secular_correction_implemented": False,
        },
        "rational_algebra_cases": case_count,
        "rational_algebra_errors": rational_errors,
        "post_intercalation_month_addition_counterexamples": counterexamples,
        "full_image_captures_hash_checked": checked_captures,
        "independent_transcription_or_scholarly_acceptance": False,
        "civil_date_or_historical_epoch_conversion_accepted": False,
        "primary_calendar_changed": False,
        "eight_hour_sequence_established": False,
        "scope": fixture["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_arithmetic(args.capture_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return bool(report["printed_prefix_errors"] or report["rational_algebra_errors"])


if __name__ == "__main__":
    raise SystemExit(main())
