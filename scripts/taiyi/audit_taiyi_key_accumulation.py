"""Collate the Key sequel's worked arithmetic without replacing Wang's epoch."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.validation.taiyi_epoch import (
    accumulation_hypothesis,
    decode_day_counter,
    sexagenary_hypothesis,
)
from fatebridge.validation.wang_mean_calendar import wang_mean_window
from scripts.taiyi.audit_taiyi_day_epoch import gregorian_from_jdn, julian_jdn
from scripts.taiyi.audit_taiyi_wang_mean import select_identity

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_key_accumulation_v39"
FREEZE_SHA256 = "5fcc0f41845ae5a6fd15a6ded5be5bb02850d300ff46ab5751b2e124f9af9a53"


def _json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("V39 source JSON object required")
    return obj


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V39 pinned source freeze changed")
    frozen = _json(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V39 source or prior evidence changed: {name}")
    return frozen


def grouped_myriads(groups: list[int]) -> int:
    """Evaluate explicit source groups, without editing any Chinese characters."""
    if not groups or any(type(v) is not int or not 0 <= v < 10000 for v in groups):
        raise ValueError("Explicit nonempty base10000 integer groups required")
    value = 0
    for group in groups:
        value = value * 10000 + group
    return value


def worked_trace(year_count: int) -> dict[str, Any]:
    result = accumulation_hypothesis(
        year_accumulation=year_count,
        chapter_years=657,
        chapter_months=8126,
        month_numerator=1447,
        day_denominator=49,
        month_offset=6,
        day_offset=0,
    )
    return {
        "completed_year_count": year_count,
        "twelve_month_product": year_count * 12,
        "twelve_month_offset_total": year_count * 12 + 6,
        "chapter_product": year_count * 8126,
        "accumulated_lunations": result["completed_months"],
        "chapter_remainder": result["chapter_remainder"],
        "chapter_remainder_denominator": 657,
        "counted_lunations_with_six_months": result["counted_months"],
        "month_product": int(result["counted_months"]) * 1447,
        "day_quotient": result["completed_days"],
        "day_small_remainder": result["day_remainder"],
        "day_denominator": 49,
        "scope": "Two distinct month counters. Quotients and remainders retain units; original source labels 分/日 are not silently rewritten.",
    }


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    reading = _json(corpus / "readings.json")
    observed, axes = reading["observed"], reading["predeclared"]
    group_controls = [
        {
            **r,
            "actual": grouped_myriads(r["groups"]),
            "matches": grouped_myriads(r["groups"]) == r["value"],
        }
        for r in reading["myriad_group_readings"]
    ]
    traces = []
    for shift in (0, 1):
        arithmetic = worked_trace(observed["completed_year_count"] + shift)
        fields = [k for k in arithmetic if k in observed]
        observations = [
            {
                "field": k,
                "expected": observed[k],
                "actual": arithmetic[k],
                "matches": arithmetic[k] == observed[k],
            }
            for k in fields
        ]
        remainder_readings = [
            {
                "divisor": divisor,
                "month_remainder": arithmetic["twelve_month_offset_total"] % divisor,
                "month_matches_printed30": arithmetic["twelve_month_offset_total"]
                % divisor
                == observed["printed_month_remainder"],
                "day_remainder": arithmetic["day_quotient"] % divisor,
                "day_matches_printed56": arithmetic["day_quotient"] % divisor
                == observed["printed_day_remainder"],
                "source_divisor_adjudicated": False,
            }
            for divisor in axes["remainder_divisors"]
        ]
        encodings = []
        for month_origin in axes["counter_origins"]:
            for day_origin in axes["counter_origins"]:
                month_name = sexagenary_hypothesis(
                    arithmetic["twelve_month_offset_total"], jiazi_origin=month_origin
                )
                day_name = sexagenary_hypothesis(
                    arithmetic["day_quotient"], jiazi_origin=day_origin
                )
                encodings.append(
                    {
                        "month_jiazi_origin": month_origin,
                        "day_jiazi_origin": day_origin,
                        "month_ganzhi": month_name,
                        "day_ganzhi": day_name,
                        "month_token_matches": month_name == observed["month_ganzhi"],
                        "day_token_matches": day_name == observed["day_ganzhi"],
                        "both_match": month_name == observed["month_ganzhi"]
                        and day_name == observed["day_ganzhi"],
                        "universal_encoding_selected": False,
                    }
                )
        traces.append(
            {
                "year_shift_from_observed": shift,
                "actual": arithmetic,
                "printed_numeric_observations": observations,
                "matching_numeric_fields": sum(r["matches"] for r in observations),
                "remainder_readings": remainder_readings,
                "counter_encodings": encodings,
            }
        )
    source = _json(corpus / "historical-months-initial.json")["months"]
    if len(source) != 14 or source[-1].get("role") != "exclusive_end_sentinel":
        raise ValueError("V39 requires all14 firsts of full1561 plus1562 sentinel")
    controls, days_count = [], 0
    for i, row in enumerate(source):
        jdn = julian_jdn(row["julian_start"])
        length = julian_jdn(source[i + 1]["julian_start"]) - jdn if i < 13 else None
        if length is not None:
            days_count += length
        controls.append(
            {
                "source": row,
                "jdn": jdn,
                "gregorian_start": gregorian_from_jdn(jdn).isoformat(),
                "month_days": length,
                "cycle_matches": (jdn + 49) % 60 == row["printed_cycle_base"],
                "week_matches": jdn % 7 == row["printed_week_base"],
                "length29_or30": length in (29, 30, None),
            }
        )
    calendar_controls_pass = all(
        r["cycle_matches"] and r["week_matches"] and r["length29_or30"]
        for r in controls
    )
    if not calendar_controls_pass:
        raise ValueError(
            "V39 newly transcribed printed calendar failed independent JDN checks"
        )
    series = []
    for shift in axes["moon_year_shifts"]:
        for assignment in axes["middle_term_assignments"]:
            for encoding in axes["initial_quotient_encodings"]:
                windows = [
                    wang_mean_window(
                        y,
                        moon_year_shift=shift,
                        middle_term_assignment=assignment,
                        initial_quotient_encoding=encoding,
                    )
                    for y in axes["winter_window_years"]
                ]
                records = [r for w in windows for r in w["records"]]
                months, days = [], []
                for control in controls:
                    row = control["source"]
                    actual = select_identity(records, row)
                    expected = decode_day_counter(
                        row["printed_cycle_base"],
                        encoding="completed_days",
                        epoch_ganzhi="甲子",
                    )["day_ganzhi"]
                    length = control["month_days"]
                    months.append(
                        {
                            "source": row,
                            "expected_first": expected,
                            "expected_month_days": length,
                            "actual": actual,
                            "identity_available": actual is not None,
                            "first_matches": actual is not None
                            and actual["counter_view"]["day_ganzhi"] == expected,
                            "length_matches": (
                                actual is not None
                                and actual["next_month_days"] == length
                                if length is not None
                                else None
                            ),
                        }
                    )
                    for day in range(1, (length or 0) + 1):
                        expected_day = decode_day_counter(
                            row["printed_cycle_base"] + day - 1,
                            encoding="completed_days",
                            epoch_ganzhi="甲子",
                        )["day_ganzhi"]
                        candidate = (
                            decode_day_counter(
                                actual["raw_quotient"] + day - 1,
                                encoding=encoding,
                                epoch_ganzhi="甲子",
                            )
                            if actual is not None
                            else None
                        )
                        exists = day <= actual["next_month_days"] if actual else None
                        matches = (
                            candidate is not None
                            and candidate["day_ganzhi"] == expected_day
                        )
                        days.append(
                            {
                                "year": row["lunar_year"],
                                "month": row["month"],
                                "is_leap_month": row["is_leap_month"],
                                "day": day,
                                "expected_ganzhi": expected_day,
                                "actual_day_ganzhi": (
                                    candidate["day_ganzhi"] if candidate else None
                                ),
                                "ordinal_exists": exists,
                                "label_matches": matches,
                                "full_date_matches": exists is True and matches,
                            }
                        )
                series.append(
                    {
                        "moon_year_shift": shift,
                        "middle_term_assignment": assignment,
                        "initial_quotient_encoding": encoding,
                        "windows": windows,
                        "source_months": months,
                        "source_days": days,
                        "matching_firsts": sum(r["first_matches"] for r in months),
                        "available_month_identities": sum(
                            r["identity_available"] for r in months
                        ),
                        "matching_lengths": sum(
                            r["length_matches"] is True for r in months
                        ),
                        "matching_day_labels": sum(r["label_matches"] for r in days),
                        "matching_full_dates": sum(
                            r["full_date_matches"] for r in days
                        ),
                        "full_observed_year_matches": all(
                            r["first_matches"] for r in months
                        )
                        and all(r["length_matches"] is True for r in months[:-1])
                        and all(r["full_date_matches"] for r in days),
                    }
                )
    adapters = []
    for month in (5, 6):
        for profile in ("jinjing_month_jie_360_v1", "key_month_tianzheng_jie_v1"):
            payload = {
                "analysis_year": 1561,
                "analysis_month": month,
                "analysis_day": 15,
                "analysis_hour": 12,
                "analysis_timezone": "+08:00",
                "use_true_solar_time": False,
                "calculation_mode": "month",
                "month_profile": profile,
            }
            value = calculate_taiyi_analysis(**payload)
            if "taiyi" not in value:
                raise ValueError(
                    f"V39 representative public adapter returned error: {value}"
                )
            board = value["taiyi"]
            adapters.append(
                {
                    "input": payload,
                    "civil_clock": board["calendar_rules"]["civil_datetime"],
                    "actual_origin": board["calendar_rules"]["month_origin"],
                    "actual_accumulation": board["core_board"]["accumulation"],
                    "relation_to_source": "Representative Jie-clock software observation; not a recovered source month boundary or a pass/fail assertion that different epochs must equal.",
                }
            )
    source_month = next(
        r
        for r in controls
        if r["source"]["month"] == 4 and not r["source"]["is_leap_month"]
    )
    source_next = next(
        r
        for r in controls
        if r["source"]["month"] == 5 and not r["source"]["is_leap_month"]
    )
    clock_jdn = date(1561, 5, 15).toordinal() + 1721425
    overlap = source_month["jdn"] <= clock_jdn < source_next["jdn"]
    for adapter in adapters:
        comparable = adapter["input"]["analysis_month"] == 5 and overlap
        adapter["source_month4_overlap_verified"] = comparable
        adapter["raw_difference_from_source_month_counter"] = (
            adapter["actual_accumulation"] - observed["twelve_month_offset_total"]
            if comparable
            else None
        )
        adapter["cycle360_matches_source_month_counter"] = (
            adapter["actual_accumulation"] % 360
            == observed["twelve_month_offset_total"] % 360
            if comparable
            else None
        )
        adapter["absolute_epoch_identity_inferred_from_cycle_match"] = False
    prior = {
        name: {
            "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
            "whole_goal_complete": _json(root / name)["whole_goal_complete"],
            "old_failure_fields_retained": True,
        }
        for name in axes["previous_evidence_retained"]
    }
    may = next(
        r
        for r in controls
        if r["source"]["month"] == 5 and r["source"]["is_leap_month"] is False
    )
    may_ganzhi = decode_day_counter(
        may["source"]["printed_cycle_base"],
        encoding="completed_days",
        epoch_ganzhi="甲子",
    )["day_ganzhi"]
    return {
        "source_freeze_sha256": FREEZE_SHA256,
        "frozen_files": len(frozen["files"]),
        "prior_pinned_files": len(frozen["prior_sources"]),
        "grouped_myriad_controls": group_controls,
        "worked_arithmetic_hypotheses": traces,
        "full_printed_calendar_controls": controls,
        "calendar_controls_pass": calendar_controls_pass,
        "source_firsts": 14,
        "source_month_lengths": 13,
        "source_days": days_count,
        "may1_printed_calendar_ganzhi": may_ganzhi,
        "may1_printed_calendar_matches_key_token": may_ganzhi == observed["day_ganzhi"],
        "conditional_full_year_series": series,
        "public_month_adapter_observations": adapters,
        "any_series_matches_full_observed_year": any(
            s["full_observed_year_matches"] for s in series
        ),
        "previous_evidence": prior,
        "new_complete_dated_taiyi_boards_passed": 0,
        "new_model_invocations": 0,
        "universal_day_or_month_counter_encoding_adjudicated": False,
        "wang_and_key_absolute_epoch_identity_adjudicated": False,
        "new_public_provider_or_formula_change": True,
        "public_default_month_year_basis_corrected": True,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_interpretation_fidelity_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": "One newly collated Key appendix arithmetic chain and an independently transcribed complete1561 calendar year. It constrains this passage's year/count representations without selecting a universal Wang epoch or replacing all prior failures.",
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
            {
                k: result[k]
                for k in (
                    "source_firsts",
                    "source_month_lengths",
                    "source_days",
                    "calendar_controls_pass",
                    "may1_printed_calendar_matches_key_token",
                    "any_series_matches_full_observed_year",
                    "whole_goal_complete",
                )
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
