"""Check selected later products and retain a manuscript quotient discrepancy.

The final weekday is a one-date comparison under the named NAOJ reference.
Neither this comparison nor the decimal products admit a historical epoch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core import sukuyo_historical_calendar
from fatebridge.core.sukuyo_weekday import (
    RECALCULATION_SOURCE,
    civil_weekday,
    classical_mean_cycle_arithmetic,
    classical_solar_recalculation,
)

FIXTURE = ROOT / "tests/data/sukuyo-weekday-recalculation-primary.json"


def verify_recalculation(capture_dir: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    if json.loads(RECALCULATION_SOURCE.read_bytes()) != fixture["source"]:
        raise ValueError("Selected recalculation source changed")
    captures = []
    if capture_dir is not None:
        for row in fixture["captured_pages"]:
            if (
                hashlib.sha256((capture_dir / row["file"]).read_bytes()).hexdigest()
                != row["sha256"]
            ):
                raise ValueError("Manuscript image fingerprint changed")
            captures.append(row["file"])
        if (
            hashlib.sha256(
                (capture_dir / "utokyo-T30107-manifest.json").read_bytes()
            ).hexdigest()
            != fixture["source"]["manifest_sha256"]
        ):
            raise ValueError("Manuscript manifest changed")
    mean_example = fixture["mean_example"]
    mean = classical_mean_cycle_arithmetic(mean_example["cycles"])
    solar_example = fixture["solar_example"]
    solar = classical_solar_recalculation(solar_example["elapsed_years"])
    controls = [
        {
            "field": field,
            "computed": result[field][rendering],
            "printed": expected,
            "comparison": rendering,
        }
        for result, field, rendering, expected in [
            (
                mean,
                "omission_days",
                "rounded_decimal_12",
                mean_example["omission_days_printed"],
            ),
            (
                mean,
                "mean_accumulated_days",
                "rounded_decimal_12",
                mean_example["middle_days_printed"],
            ),
            (
                solar,
                "baseline_accumulated_days",
                "truncated_decimal_12",
                solar_example["baseline_product_printed"],
            ),
            (
                solar,
                "recalibrated_accumulated_days",
                "truncated_decimal_12",
                solar_example["recalibrated_product_printed"],
            ),
        ]
    ]
    errors = [row["field"] for row in controls if row["computed"] != row["printed"]]
    if mean["nominal_days"] != mean_example["nominal_days"]:
        errors.append("nominal_days")
    # Independent source-table lookup by the text's lunar label, not by a date
    # selected to make the expected weekday fit.
    example = fixture["final_weekday_example"]
    year, month, day, leap = example["reference_lunar_fields"]
    historical = json.loads(sukuyo_historical_calendar.SOURCE.read_bytes())
    matching = [
        ordinal + day - 1
        for ordinal, y, m, is_leap, length in historical["months"]
        if (y, m, is_leap) == (year, month, leap) and day <= length
    ]
    if len(matching) != 1:
        raise ValueError("Printed lunar example has no unique NAOJ month label")
    civil = date.fromordinal(matching[0])
    weekday = civil_weekday(civil.isoformat(), "UTC+09:00")
    if weekday["luminary"] != example["printed_weekday"]:
        errors.append("one_lunar_label_weekday_control")
    accumulated = Fraction(example["printed_mean_accumulated_days"])
    quotient, remainder = divmod(accumulated, 7)
    candidate = example["quotient_reading"]
    candidate_delta = candidate["candidate_value"] - quotient
    return {
        "format": "sukuyo_t30107_selected_recalculation_check_v1",
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "runtime_source_sha256": hashlib.sha256(
            RECALCULATION_SOURCE.read_bytes()
        ).hexdigest(),
        "decimal_product_controls": controls,
        "errors": errors,
        "fractional_omission_uniform_truncation_claim_supported": False,
        "omission_truncation_would_be": mean["omission_days"]["truncated_decimal_12"],
        "final_quotient_candidate": {
            **candidate,
            "exact_floor_quotient_from_printed_accumulated_days": quotient,
            "exact_remainder_numerator": remainder.numerator,
            "exact_remainder_denominator": remainder.denominator,
            "candidate_minus_exact_quotient": candidate_delta,
            "status": (
                "retained_transcription_or_source_discrepancy"
                if candidate_delta
                else "matched"
            ),
            "source_text_rewritten": False,
            "independent_collation_complete": False,
        },
        "one_lunar_label_weekday_control": {
            "printed_lunar_fields": example["reference_lunar_fields"],
            "printed_luminary": example["printed_weekday"],
            "naoj_reference_date": civil.isoformat(),
            "civil_weekday": weekday,
            "naoj_bundle_sha256": hashlib.sha256(
                sukuyo_historical_calendar.SOURCE.read_bytes()
            ).hexdigest(),
            "date_reference": sukuyo_historical_calendar.date_reference(civil),
            "contemporary_observation_claimed": False,
            "source_mean_new_moon_equals_civil_midnight_claimed": False,
        },
        "full_image_captures_hash_checked": captures,
        "full_secular_correction_implemented": False,
        "original_tang_epoch_or_civil_conversion_accepted": False,
        "primary_calendar_changed": False,
        "eight_hour_sequence_established": False,
        "scope": fixture["source"]["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_recalculation(args.capture_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
