"""Audit a complete Yuanjia-era cohort without replacing Wang's calendar."""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.validation.taiyi_epoch import decode_day_counter
from fatebridge.validation.yuanjia_calendar import yuanjia_mean_year

if TYPE_CHECKING or __package__:
    from scripts.audit_taiyi_day_epoch import gregorian_from_jdn, julian_jdn
else:
    from audit_taiyi_day_epoch import gregorian_from_jdn, julian_jdn

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v35"
FREEZE_SHA256 = "e24226d89c43f82c39d8b57ff6f9264ef449bfcf2c9f88828533d1704e36aa2e"


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"V35 source object required: {path.name}")
    return result


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V35 pinned source freeze changed")
    frozen = _json(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V35 source or prior evidence changed: {name}")
    return frozen


def _fraction(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    reading = _json(corpus / "readings.json")
    source = _json(corpus / "historical-months-initial.json")
    rows = source["months"]
    if len(rows) != 63 or rows[-1].get("role") != "exclusive_end_sentinel":
        raise ValueError("V35 requires all63 firsts and the506 sentinel")
    source_controls = []
    for i, row in enumerate(rows):
        jdn = julian_jdn(row["julian_start"])
        length = (
            julian_jdn(rows[i + 1]["julian_start"]) - jdn if i + 1 < len(rows) else None
        )
        source_controls.append(
            {
                "source": row,
                "gregorian": gregorian_from_jdn(jdn).isoformat(),
                "month_days": length,
                "julian_day_cycle_matches": (jdn + 49) % 60
                == row["printed_cycle_base"],
                "julian_week_counter_matches": jdn % 7 == row["printed_week_base"],
                "length_is29_or30": length in (29, 30, None),
            }
        )
    if not all(c["length_is29_or30"] for c in source_controls):
        raise ValueError(
            "V35 transcribed consecutive firsts are not valid month lengths"
        )
    anchor = reading["year_anchor"]
    anchor_actual = yuanjia_mean_year(
        anchor["elapsed_years_from_upper_epoch"], middle_term_assignment="civil_day"
    )
    series = []
    for assignment in reading["predeclared_comparisons"][
        "middle_term_assignment_hypotheses"
    ]:
        months, days, years = [], [], []
        for year in reading["predeclared_comparisons"]["complete_source_years"]:
            elapsed = (
                anchor["elapsed_years_from_upper_epoch"] + year - anchor["ce_year"]
            )
            result = yuanjia_mean_year(elapsed, middle_term_assignment=assignment)
            selected = [
                c for c in source_controls[:-1] if c["source"]["lunar_year"] == year
            ]
            years.append(
                {
                    "year": year,
                    "printed_month_count": len(selected),
                    "calculated": result,
                    "month_counts_match": len(selected) == result["month_count"],
                }
            )
            for i, control in enumerate(selected):
                printed = control["source"]
                actual = result["records"][i] if i < len(result["records"]) else None
                expected_label = decode_day_counter(
                    printed["printed_cycle_base"],
                    encoding="completed_days",
                    epoch_ganzhi="甲子",
                )["day_ganzhi"]
                month_matches = actual is not None and (
                    actual["month"],
                    actual["is_leap_month"],
                ) == (printed["month"], printed["is_leap_month"])
                months.append(
                    {
                        "source": printed,
                        "reference_month_days": control["month_days"],
                        "reference_first_ganzhi": expected_label,
                        "actual": actual,
                        "first_ganzhi_matches": actual is not None
                        and actual["first_ganzhi"] == expected_label,
                        "month_length_matches": actual is not None
                        and actual["next_month_days"] == control["month_days"],
                        "month_identity_matches": month_matches,
                    }
                )
                for day in range(1, control["month_days"] + 1):
                    expected = decode_day_counter(
                        printed["printed_cycle_base"] + day - 1,
                        encoding="completed_days",
                        epoch_ganzhi="甲子",
                    )["day_ganzhi"]
                    label = (
                        decode_day_counter(
                            actual["day_within_ji"] + day - 1,
                            encoding="completed_days",
                            epoch_ganzhi=result["ji_ganzhi"],
                        )["day_ganzhi"]
                        if actual is not None
                        else None
                    )
                    exists = actual is not None and day <= actual["next_month_days"]
                    days.append(
                        {
                            "year": year,
                            "month": printed["month"],
                            "is_leap_month": printed["is_leap_month"],
                            "day": day,
                            "expected_ganzhi": expected,
                            "actual_ganzhi": label,
                            "actual_month": actual["month"] if actual else None,
                            "actual_is_leap_month": (
                                actual["is_leap_month"] if actual else None
                            ),
                            "ordinal_exists": exists,
                            "day_label_matches": label == expected,
                            "month_identity_matches": month_matches,
                            "full_lunar_date_matches": exists
                            and label == expected
                            and month_matches,
                        }
                    )
        sentinel = decode_day_counter(
            rows[-1]["printed_cycle_base"],
            encoding="completed_days",
            epoch_ganzhi="甲子",
        )["day_ganzhi"]
        sentinel_matches = (
            years[-1]["calculated"]["next_year_first"]["first_ganzhi"] == sentinel
        )
        series.append(
            {
                "middle_term_assignment": assignment,
                "years": years,
                "months": months,
                "days": days,
                "month_firsts_required": 63,
                "matching_firsts_including_sentinel": sum(
                    r["first_ganzhi_matches"] for r in months
                )
                + int(sentinel_matches),
                "sentinel_ganzhi_matches": sentinel_matches,
                "month_lengths_required": 62,
                "matching_month_lengths": sum(
                    r["month_length_matches"] for r in months
                ),
                "matching_month_identities": sum(
                    r["month_identity_matches"] for r in months
                ),
                "required_days": len(days),
                "matching_day_labels": sum(r["day_label_matches"] for r in days),
                "matching_complete_lunar_dates": sum(
                    r["full_lunar_date_matches"] for r in days
                ),
                "all_observed_months_and_days_match": sentinel_matches
                and all(r["month_counts_match"] for r in years)
                and all(
                    r["first_ganzhi_matches"]
                    and r["month_length_matches"]
                    and r["month_identity_matches"]
                    for r in months
                )
                and all(r["full_lunar_date_matches"] for r in days),
                "absolute_julian_epoch_proved": False,
                "source_assignment_selected_by_fit": False,
            }
        )
    old_path = root / "docs/validation/taiyi-jinjing-v34/report.json"
    old = _json(old_path)
    return {
        "source_freeze_sha256": FREEZE_SHA256,
        "prior_pinned_files": len(frozen["prior_sources"]),
        "source_calendar_controls": source_controls,
        "source_calendar_reconstruction_checks_match": all(
            c["julian_day_cycle_matches"] and c["julian_week_counter_matches"]
            for c in source_controls
        ),
        "source_anchor_check": {
            "actual_elapsed_years_within_ji": anchor_actual["elapsed_years_within_ji"],
            "expected_elapsed_years_within_ji": reading["within_ji_anchor"][
                "elapsed_years_within_ji"
            ],
            "actual_ji_ganzhi": anchor_actual["ji_ganzhi"],
            "expected_ji_ganzhi": reading["within_ji_anchor"]["ji_ganzhi"],
        },
        "yuanjia_calendar_series": series,
        "mean_month_comparison": {
            "ming_wang_days": _fraction(Fraction(1447, 49)),
            "yuanjia_days": _fraction(Fraction(22207, 752)),
            "wang_minus_yuanjia_days": _fraction(
                Fraction(1447, 49) - Fraction(22207, 752)
            ),
            "equal_calendar_or_epoch_identity_proved": False,
        },
        "previous_v34_evidence": {
            "path": str(old_path.relative_to(root)),
            "sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
            "all48_candidates_and96_counter_comparisons_retained_in_pinned_report": True,
            "original_observed_joint_matches": old["original_observed_joint_matches"],
            "xing_observed_joint_matches": old["xing_observed_joint_matches"],
            "old326_labels325_valid_dates_and_all_board_conflicts_retained": True,
        },
        "new_independent_taiyi_cases": 0,
        "new_complete_dated_classical_cases_passed": 0,
        "new_public_calendar_installed": False,
        "wang_constants_or_original_day_changed": False,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": "A separately named Yuanjia source algorithm and complete501-505 printed cohort. Calendar identities, qi assignment and any failures remain explicit; source-phase agreement cannot certify Wang's Taiyi case or absolute epoch.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    else:
        print(raw)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
