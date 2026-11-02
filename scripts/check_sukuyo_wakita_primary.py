"""Check selected printed clauses and preserve, rather than excuse, precision gaps."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo_weekday import (
    CALIBRATION_SOURCE,
    PRINTED_CHAPTER_SOURCE,
    SOURCE,
    classical_calibration_precision,
    classical_source_year_count,
)

FIXTURE = ROOT / "tests/fixtures/sukuyo-wakita-weekday-primary.json"
PRECISION_FIXTURE = ROOT / "tests/fixtures/sukuyo-calibration-precision-primary.json"


def verify_printed_chapter(capture_dir: Path | None = None) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_bytes())
    precision_fixture = json.loads(PRECISION_FIXTURE.read_bytes())
    printed = json.loads(PRINTED_CHAPTER_SOURCE.read_bytes())
    calibration = json.loads(CALIBRATION_SOURCE.read_bytes())
    if printed != fixture["source"] or calibration != precision_fixture["source"]:
        raise ValueError("Selected printed/calibration source changed")
    checked = []
    if capture_dir is not None:
        for row in fixture["captured_pages"] + precision_fixture["captured_pages"]:
            if (
                hashlib.sha256((capture_dir / row["file"]).read_bytes()).hexdigest()
                != row["sha256"]
            ):
                raise ValueError("Primary image fingerprint changed")
            checked.append(row["file"])
        if (
            hashlib.sha256(
                (capture_dir / "ndl-817827-manifest.json").read_bytes()
            ).hexdigest()
            != printed["manifest_sha256"]
        ):
            raise ValueError("Printed edition manifest changed")
    manuscript = json.loads(SOURCE.read_bytes())["general_formula"]
    errors: list[str] = []
    comparison = {
        key: {"printed_1897": value, "selected_T30107": manuscript["constants"][key]}
        for key, value in printed["formula_constants"].items()
    }
    errors.extend(
        key
        for key, row in comparison.items()
        if row["printed_1897"] != row["selected_T30107"]
    )
    example = fixture["separate_late_T30107_year_example"]
    year = classical_source_year_count(example["year_number"])
    if year["elapsed_years"] != example["elapsed_years"]:
        errors.append("separate_late_year_count")
    may = manuscript["may_fifth_example"]
    if (
        may["elapsed_months"] != printed["entered_month_example"]["entered_months"]
        or may["elapsed_days"] != printed["entered_month_example"]["elapsed_days"]
    ):
        errors.append("entered_month_day_counts")
    trace = classical_calibration_precision()
    return {
        "format": "sukuyo_wakita_selected_primary_check_v1",
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "precision_fixture_sha256": hashlib.sha256(
            PRECISION_FIXTURE.read_bytes()
        ).hexdigest(),
        "runtime_printed_source_sha256": hashlib.sha256(
            PRINTED_CHAPTER_SOURCE.read_bytes()
        ).hexdigest(),
        "runtime_calibration_source_sha256": hashlib.sha256(
            CALIBRATION_SOURCE.read_bytes()
        ).hexdigest(),
        "implementation_or_selected_source_errors": errors,
        "selected_formula_constant_comparison": comparison,
        "separate_late_year_example": {"printed": example, "computed": year},
        "calibration_precision": trace,
        "source_arithmetic_consistent_at_selected_precision": not trace[
            "selected_precision_discrepancies"
        ],
        "full_image_captures_hash_checked": checked,
        "late_print_and_manuscript_are_independent_observations": False,
        "independent_transcription_accepted": False,
        "whole_book_or_variant_apparatus_collated": False,
        "civil_epoch_or_host_calendar_mapping_accepted": False,
        "eight_hour_order_established": False,
        "three_axis_completion_supported": False,
        "scope": printed["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_printed_chapter(args.capture_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    # Success means the checker ran and found no implementation/source-binding
    # regression. The printed arithmetic discrepancy remains explicit above.
    return bool(report["implementation_or_selected_source_errors"])


if __name__ == "__main__":
    raise SystemExit(main())
