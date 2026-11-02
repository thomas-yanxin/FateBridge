"""Compare a named calculation to readable, source-transcribed calendar facts.

Missing reference characters and unavailable calculations remain distinct.
Agreement here never certifies a complete historical system or predictions.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_calendar_year import gujin_fixed_qice_year
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_year_labels import shoushi_year_context

DATA = (
    Path(__file__).resolve().parents[1]
    / "data/guolao/official-calendar-reference-v1.json"
)


def compare_official_calendar(
    reference_id: str, *, conjunction_method: str = "floor_table"
) -> dict[str, Any]:
    raw = DATA.read_bytes()
    sources = json.loads(raw)
    matches = [
        case for case in sources["cases"] if case["reference_id"] == reference_id
    ]
    if len(matches) != 1:
        raise ValueError("须明确选择一个已转录历书，不按吻合程度另选历元或参数")
    reference = matches[0]
    context = shoushi_year_context(source_year=reference["source_year"])
    middle = shoushi_winter_cycle(context["elapsed_years"]).zhongji_days
    calendar = (
        gujin_fixed_qice_year(middle)
        if conjunction_method == "floor_table"
        else gujin_fixed_qice_year(middle, conjunction_method=conjunction_method)
    )
    comparisons = []
    counts = {
        "matches": 0,
        "mismatches": 0,
        "computed_unavailable": 0,
        "reference_unreadable_or_unprovided": 0,
    }

    def compare(
        locator: dict[str, Any], field: str, expected: Any, actual: Any
    ) -> None:
        status = (
            "reference_unreadable_or_unprovided"
            if expected is None
            else (
                "computed_unavailable"
                if actual is None
                else "matches" if actual == expected else "mismatches"
            )
        )
        counts[status] += 1
        comparisons.append(
            {
                "locator": locator,
                "field": field,
                "reference": expected,
                "computed": actual,
                "status": status,
            }
        )

    available = calendar["complete_named_year_assigned"]
    for month in reference["months"]:
        key = month["month_number"], month["is_leap_month"]
        found = [
            row
            for row in calendar["months"]
            if (row["month_number"], row["is_leap_month"]) == key
        ]
        row = found[0] if len(found) == 1 else {}
        for field in ["length_days", "sexagenary_start_day"]:
            compare(
                {"month_number": key[0], "is_leap_month": key[1], **month["locator"]},
                field,
                month[field],
                row.get(field),
            )
    for field, source_key in [
        ("month_count", "calendar_month_count"),
        ("total_days", "calendar_total_days"),
    ]:
        compare(
            {"scope": "printed_year_summary"},
            field,
            reference[source_key],
            calendar[field] if available else None,
        )
    return {
        "model_id": "guolao_official_calendar_reference_comparison_v1",
        "reference_id": reference_id,
        "reference_data_sha256": hashlib.sha256(raw).hexdigest(),
        "reference": reference,
        "source_year_context": context,
        "zhongji_days_exact": str(middle),
        "calendar": calendar,
        "comparisons": comparisons,
        "counts": counts,
        "status": (
            "reference_mismatches_present"
            if counts["mismatches"]
            else (
                "required_calculation_unavailable"
                if counts["computed_unavailable"]
                else (
                    "agreement_on_readable_reference_fields_only"
                    if counts["matches"]
                    else "no_readable_reference_fields"
                )
            )
        ),
        "missing_reference_fields_counted_as_matches": False,
        "parameters_selected_by_reference_fit": False,
        "pre_registered_holdout": False,
        "complete_historical_calendar_accepted": False,
        "real_world_prediction_validated": False,
    }


def audit_named_year_grid(
    start: int, stop: int, *, conjunction_method: str = "floor_table"
) -> dict[str, Any]:
    """An exhaustive declared integer range, measuring internal coverage only."""
    if type(start) is not int or type(stop) is not int:
        raise TypeError("距算范围须为整数，不接收布尔或浮点近似")
    if start < 0 or stop <= start:
        raise ValueError("距算范围须非负且前含后不含，不自动互换端点")
    rows = []
    for elapsed in range(start, stop):
        middle = shoushi_winter_cycle(elapsed).zhongji_days
        calendar = (
            gujin_fixed_qice_year(middle)
            if conjunction_method == "floor_table"
            else gujin_fixed_qice_year(middle, conjunction_method=conjunction_method)
        )
        cycle = calendar["first_winter_cycle"]
        missing = []
        for candidate in cycle["conjunction_candidates"]:
            if candidate["research_conjunction_offset_from_winter_days_exact"] is None:
                missing.append(
                    {
                        "lunation_index": candidate["lunation_index"],
                        "velocity_status": candidate["lunar_velocity"]["status"],
                        "whole_limit_index": candidate["lunar_velocity"][
                            "whole_limit_index"
                        ],
                        "anomaly_phase_days_exact": candidate["lunar_velocity"][
                            "anomaly_phase_days_exact"
                        ],
                        "angular_argument_in_printed_limits": candidate[
                            "angular_components"
                        ]["lunar"]["argument_within_printed_limits"],
                    }
                )
        rows.append(
            {
                "elapsed_years": elapsed,
                "zhongji_days_exact": str(middle),
                "status": calendar["status"],
                "reason": calendar["reason"],
                "first_cycle_reason": cycle["month_assignment"]["reason"],
                "month_count": calendar["month_count"],
                "total_days": calendar["total_days"],
                "missing_first_cycle_conjunction_diagnostics": missing,
                **(
                    {
                        "missing_year_tail_conjunction_diagnostics": [
                            {
                                "lunation_index": c["lunation_index"],
                                "velocity_status": c["lunar_velocity"]["status"],
                                "whole_limit_index": c["lunar_velocity"][
                                    "whole_limit_index"
                                ],
                                "anomaly_phase_days_exact": c["lunar_velocity"][
                                    "anomaly_phase_days_exact"
                                ],
                                "conflicting_reversed_interval_indices": c[
                                    "angular_components"
                                ]["lunar"]["conflicting_reversed_interval_indices"],
                            }
                            for c in calendar["extra_conjunction_candidates"]
                            if c["research_conjunction_offset_from_winter_days_exact"]
                            is None
                        ]
                    }
                    if conjunction_method != "floor_table"
                    else {}
                ),
            }
        )
    return {
        "model_id": "guolao_named_calendar_year_internal_grid_v1",
        **(
            {"conjunction_method": conjunction_method}
            if conjunction_method != "floor_table"
            else {}
        ),
        "status": "internal_coverage_only_not_external_accuracy",
        "elapsed_range_start_inclusive": start,
        "elapsed_range_stop_exclusive": stop,
        "input_years": stop - start,
        "input_years_dropped": 0,
        "counts": dict(Counter(r["status"] for r in rows)),
        "unresolved": [
            r for r in rows if r["status"] != "complete_under_named_fixed_qice_policy"
        ],
        "rows": rows,
        "complete_historical_calendar_accepted": False,
        "real_world_prediction_validated": False,
    }


def compare_named_calendar_methods(start: int, stop: int) -> dict[str, Any]:
    """Compare all declared years without selecting a method by its outcome."""
    return _compare_fixed_methods(start, stop, literal=False)


def compare_literal_calendar_methods(start: int, stop: int) -> dict[str, Any]:
    """Compare the prior integer reconstruction with literal cumulative/increment cells."""
    return _compare_fixed_methods(start, stop, literal=True)


def _compare_fixed_methods(start: int, stop: int, *, literal: bool) -> dict[str, Any]:
    if type(start) is not int or type(stop) is not int:
        raise TypeError("距算范围须为整数")
    if start < 0 or stop <= start:
        raise ValueError("距算范围须非负且前含后不含")
    rows: list[dict[str, Any]] = []
    left, right = (
        ("day_rate", "literal_table") if literal else ("floor_table", "day_rate")
    )
    for elapsed in range(start, stop):
        middle = shoushi_winter_cycle(elapsed).zhongji_days
        old = (
            gujin_fixed_qice_year(middle, conjunction_method=left)
            if literal
            else gujin_fixed_qice_year(middle)
        )
        new = gujin_fixed_qice_year(middle, conjunction_method=right)

        def facts(calendar: dict[str, Any]) -> list[dict[str, Any]] | None:
            if not calendar["complete_named_year_assigned"]:
                return None
            return [
                {
                    key: month[key]
                    for key in [
                        "month_number",
                        "is_leap_month",
                        "length_days",
                        "sexagenary_start_day",
                    ]
                }
                for month in calendar["months"]
            ]

        a, b = facts(old), facts(new)
        correction_rows = []
        if literal:

            def candidates(calendar: dict[str, Any]) -> dict[int, dict[str, Any]]:
                return {
                    c["lunation_index"]: c
                    for c in [
                        *calendar["first_winter_cycle"]["conjunction_candidates"],
                        *calendar["extra_conjunction_candidates"],
                    ]
                }

            old_candidates, new_candidates = candidates(old), candidates(new)
            for q in range(18):
                old_case, new_case = old_candidates.get(q), new_candidates.get(q)
                old_value = old_case["time_correction_days_exact"] if old_case else None
                new_value = new_case["time_correction_days_exact"] if new_case else None
                status = (
                    "not_requested_by_year_builder"
                    if old_case is None or new_case is None
                    else (
                        "source_value_unavailable"
                        if old_value is None or new_value is None
                        else "compared"
                    )
                )
                correction_rows.append(
                    {
                        "lunation_index": q,
                        "day_rate_correction_days_exact": old_value,
                        "literal_table_correction_days_exact": new_value,
                        "literal_minus_integer_correction_days_exact": (
                            str(Fraction(new_value) - Fraction(old_value))
                            if new_value is not None and old_value is not None
                            else None
                        ),
                        "comparison_status": status,
                    }
                )
        rows.append(
            {
                "elapsed_years": elapsed,
                left + "_status": old["status"],
                right + "_status": new["status"],
                left + "_calendar_facts": a,
                right + "_calendar_facts": b,
                "both_complete": a is not None and b is not None,
                "calendar_facts_agree": (
                    a == b if a is not None and b is not None else None
                ),
                **(
                    {"conjunction_correction_comparisons": correction_rows}
                    if literal
                    else {}
                ),
            }
        )
    return {
        "model_id": (
            "guolao_literal_vs_integer_calendar_comparison_v1"
            if literal
            else "guolao_named_calendar_method_comparison_v1"
        ),
        "elapsed_range_start_inclusive": start,
        "elapsed_range_stop_exclusive": stop,
        "input_years": stop - start,
        "input_years_dropped": 0,
        "both_complete_years": sum(r["both_complete"] for r in rows),
        "years_with_different_calendar_facts": sum(
            r["calendar_facts_agree"] is False for r in rows
        ),
        "unresolved_years_by_method": {
            method: [
                r["elapsed_years"]
                for r in rows
                if r[method + "_calendar_facts"] is None
            ]
            for method in [left, right]
        },
        "rows": rows,
        "methods_selected_by_year_or_reference_fit": False,
        "method_disagreement_is_external_accuracy_evidence": False,
        "real_world_prediction_validated": False,
        **(_literal_correction_summary(rows) if literal else {}),
    }


def _literal_correction_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positions = [p for r in rows for p in r["conjunction_correction_comparisons"]]
    values = [
        Fraction(p["literal_minus_integer_correction_days_exact"])
        for p in positions
        if p["comparison_status"] == "compared"
    ]
    return {
        "conjunction_comparison_scope": "indices0_through17_per_year_including_missing_and_unrequested_positions",
        "conjunction_comparison_positions": len(positions),
        "conjunction_comparison_status_counts": dict(
            Counter(p["comparison_status"] for p in positions)
        ),
        "conjunction_corrections_changed": sum(v != 0 for v in values),
        "maximum_absolute_correction_change_source_days_exact": (
            str(max(map(abs, values))) if values else None
        ),
        "missing_or_unrequested_corrections_counted_as_agreement": False,
        "correction_change_certifies_improved_absolute_accuracy": False,
    }
