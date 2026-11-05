"""Audit conditional Wang mean-calendar windows; no source selected by fit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.validation.taiyi_epoch import (
    decode_day_counter,
    lunar_day_counter_views,
)
from fatebridge.validation.wang_mean_calendar import wang_mean_window
from scripts.taiyi.audit_taiyi_day_epoch import julian_jdn

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_wang_mean_v38"
FREEZE_SHA256 = "9730f946a3e735c1b702f8502460a9af52ab005c0202aab5f75b1a7d2b63ad8c"


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("V38 frozen JSON object required")
    return result


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V38 pinned source freeze changed")
    frozen = _json(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V38 source or previous evidence changed: {name}")
    return frozen


def select_identity(
    records: list[dict[str, Any]], source: dict[str, Any]
) -> dict[str, Any] | None:
    """Unknown/ambiguous identity never falls back to an ordinal or name fit."""
    keys = ("lunar_year", "month", "is_leap_month")
    selected = [
        r
        for r in records
        if r["conditional_identity_known"] and all(r[k] == source[k] for k in keys)
    ]
    return selected[0] if len(selected) == 1 else None


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    reading = _json(corpus / "readings.json")
    axes = reading["predeclared"]
    source = _json(
        root / "tests/fixtures/taiyi_jinjing_v35/historical-months-initial.json"
    )["months"]
    if len(source) != 63 or source[-1].get("role") != "exclusive_end_sentinel":
        raise ValueError("V38 must preserve the complete63-first cohort")
    lengths = [
        julian_jdn(b["julian_start"]) - julian_jdn(a["julian_start"])
        for a, b in zip(source, source[1:])
    ]
    if (
        len(lengths) != 62
        or sum(lengths) != 1831
        or any(d not in (29, 30) for d in lengths)
    ):
        raise ValueError("V38 full source month/day cohort changed")
    series = []
    for shift in axes["moon_year_shifts"]:
        for assignment in axes["middle_term_assignment"]:
            for encoding in axes["initial_quotient_encodings"]:
                windows = [
                    wang_mean_window(
                        year,
                        moon_year_shift=shift,
                        middle_term_assignment=assignment,
                        initial_quotient_encoding=encoding,
                    )
                    for year in axes["window_ce_years"]
                ]
                all_records = [r for w in windows for r in w["records"]]
                comparisons, days = [], []
                for i, row in enumerate(source):
                    actual = select_identity(all_records, row)
                    expected = decode_day_counter(
                        row["printed_cycle_base"],
                        encoding="completed_days",
                        epoch_ganzhi="甲子",
                    )["day_ganzhi"]
                    length = lengths[i] if i < len(lengths) else None
                    first_matches = (
                        actual is not None
                        and actual["counter_view"]["day_ganzhi"] == expected
                    )
                    comparisons.append(
                        {
                            "source": row,
                            "expected_first_ganzhi": expected,
                            "expected_month_days": length,
                            "actual": actual,
                            "month_identity_available": actual is not None,
                            "first_ganzhi_matches": first_matches,
                            "month_length_matches": (
                                actual is not None
                                and actual["next_month_days"] == length
                                if length is not None
                                else None
                            ),
                        }
                    )
                    for ordinal in range(1, (length or 0) + 1):
                        expected_day = decode_day_counter(
                            row["printed_cycle_base"] + ordinal - 1,
                            encoding="completed_days",
                            epoch_ganzhi="甲子",
                        )["day_ganzhi"]
                        candidate = (
                            lunar_day_counter_views(
                                actual["raw_quotient"],
                                ordinal,
                                month_start_encoding=encoding,
                                epoch_ganzhi="甲子",
                            )
                            if actual is not None
                            else None
                        )
                        exists = (
                            ordinal <= actual["next_month_days"]
                            if actual is not None
                            else None
                        )
                        match = (
                            candidate is not None
                            and candidate["day_ganzhi"] == expected_day
                        )
                        days.append(
                            {
                                "year": row["lunar_year"],
                                "month": row["month"],
                                "is_leap_month": row["is_leap_month"],
                                "day": ordinal,
                                "expected_ganzhi": expected_day,
                                "actual": (
                                    {
                                        k: candidate[k]
                                        for k in (
                                            "completed_days",
                                            "one_based_day_number",
                                            "day_ganzhi",
                                            "both_views_preserve_same_day",
                                        )
                                    }
                                    if candidate is not None
                                    else None
                                ),
                                "ordinal_exists": exists,
                                "day_label_matches": match,
                                "full_lunar_date_matches": exists is True and match,
                            }
                        )
                target_source = {"lunar_year": 504, "month": 6, "is_leap_month": False}
                target = select_identity(all_records, target_source)
                target_views = (
                    lunar_day_counter_views(
                        target["raw_quotient"],
                        8,
                        month_start_encoding=encoding,
                        epoch_ganzhi="甲子",
                    )
                    if target is not None
                    else None
                )
                series.append(
                    {
                        "moon_year_shift": shift,
                        "middle_term_assignment": assignment,
                        "initial_quotient_encoding": encoding,
                        "windows": windows,
                        "source_month_comparisons": comparisons,
                        "source_days": days,
                        "required_firsts": 63,
                        "required_lengths": 62,
                        "required_days": 1831,
                        "available_month_identities": sum(
                            r["month_identity_available"] for r in comparisons
                        ),
                        "matching_first_ganzhi": sum(
                            r["first_ganzhi_matches"] for r in comparisons
                        ),
                        "matching_month_lengths": sum(
                            r["month_length_matches"] is True for r in comparisons
                        ),
                        "matching_day_labels": sum(
                            r["day_label_matches"] for r in days
                        ),
                        "matching_complete_lunar_dates": sum(
                            r["full_lunar_date_matches"] for r in days
                        ),
                        "whole_observed_cohort_matches": all(
                            r["first_ganzhi_matches"] for r in comparisons
                        )
                        and all(
                            r["month_length_matches"] is True for r in comparisons[:-1]
                        )
                        and all(r["full_lunar_date_matches"] for r in days),
                        "target_day8": target_views,
                        "target_given_number_and_day_match": target_views is not None
                        and target_views["one_based_day_number"] == 707501061
                        and target_views["day_ganzhi"] == "甲申",
                        "conditional_leaps": [
                            {
                                "window_year": w["nominal_ce_year"],
                                "labels_known": w["conditional_month_identities_known"],
                                "leaps": [
                                    {
                                        k: r[k]
                                        for k in (
                                            "lunar_year",
                                            "month",
                                            "is_leap_month",
                                            "slot",
                                        )
                                    }
                                    for r in w["records"]
                                    if r["is_leap_month"] is True
                                ],
                            }
                            for w in windows
                        ],
                    }
                )
    prior = {}
    for name in axes["retain_full_old_reports"]:
        old = _json(root / name)
        prior[name] = {
            "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
            "whole_calendar_acceptance_passed": old["whole_calendar_acceptance_passed"],
            "whole_goal_complete": old["whole_goal_complete"],
            "old_fields_and_failures_retained": True,
        }
    return {
        "source_freeze_sha256": FREEZE_SHA256,
        "prior_pinned_files": len(frozen["prior_sources"]),
        "new_source_files": len(frozen["files"]),
        "conditional_series": series,
        "all_eight_predeclared_series_retained": len(series) == 8,
        "any_series_matches_all_observed_dates": any(
            s["whole_observed_cohort_matches"] for s in series
        ),
        "any_series_matches_original_day8_integer_and_label": any(
            s["target_given_number_and_day_match"] for s in series
        ),
        "previous_evidence": prior,
        "source_leap_or_next_qi_clause_emended": False,
        "calendar_selected_by_fit": False,
        "new_public_calendar_installed": False,
        "new_complete_dated_taiyi_cases_passed": 0,
        "new_independent_source_observations": 0,
        "new_model_invocations": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_interpretation_fidelity_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": "Conditional Ming Wang full-window diagnostic with unknown month identities kept. Six winter windows cover the old five-year63-first/62-month1831-day cohort. Algebraic qi steps, source year shifts and counter encodings remain hypotheses; none is selected, installed or counted as a new ancient case.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "conditional_series"},
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
