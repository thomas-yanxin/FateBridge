"""A named fixed-qi source year, bounded by two regular first-month starts."""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_intercalation import TERMS, gujin_fixed_qice_months
from fatebridge.core.guolao_lunar_velocity import gujin_table_conjunction


def gujin_fixed_qice_year(
    zhongji_days: Fraction, *, conjunction_method: str = "floor_table"
) -> dict[str, Any]:
    """Continue the same fixed printed qi series, not an independently reset year.

    The winter-to-winter cycle stops before the current year's last two months.
    Compute only the necessary tail until the next regular first month, leaving
    gaps and conflicting qi unresolved. No modern dates or native chart changes.
    """
    from fatebridge.core.guolao_cumulative_table import gujin_literal_conjunction
    from fatebridge.core.guolao_day_rate import gujin_day_rate_conjunction

    base = (
        gujin_fixed_qice_months(zhongji_days)
        if conjunction_method == "floor_table"
        else gujin_fixed_qice_months(
            zhongji_days, conjunction_method=conjunction_method
        )
    )
    conjunction = (
        gujin_table_conjunction
        if conjunction_method == "floor_table"
        else (
            gujin_day_rate_conjunction
            if conjunction_method == "day_rate"
            else gujin_literal_conjunction
        )
    )
    return _fixed_qice_year_from_conjunctions(zhongji_days, base, conjunction)


def _fixed_qice_year_from_conjunctions(
    zhongji_days: Fraction,
    base: dict[str, Any],
    conjunction: Callable[[Fraction, int], dict[str, Any]],
) -> dict[str, Any]:
    """Continue the supplied branch using the same year-assignment rules."""
    assignment = base["month_assignment"]
    result: dict[str, Any] = {
        "model_id": "gujin_named_fixed_qice_calendar_year_v1",
        "profile_id": base["profile_id"],
        "status": "partial_calendar_year",
        "reason": None,
        "window_policy": "regular_month_one_start_to_next_regular_month_one_start",
        "qi_continuation_policy": "same_zhongji_fixed_printed_qice_not_independently_reset_next_winter",
        "months": [],
        "month_count": None,
        "total_days": None,
        "next_regular_first_month": None,
        "first_winter_cycle": base,
        "extra_conjunction_candidates": [],
        "complete_named_year_assigned": False,
        "complete_historical_calendar_accepted": False,
        "modern_epoch_calibrated": False,
        "modern_lunar_dates": None,
        "used_in_native_birth_chart": False,
    }
    if assignment["status"] != "assigned_under_explicit_civil_mean_qi_policy":
        result["reason"] = "first_winter_cycle_unresolved"
        return result
    rows = assignment["months"]
    first = next(
        i
        for i, row in enumerate(rows)
        if row["month_number"] == 1 and not row["is_leap_month"]
    )
    year_rows = [dict(row) for row in rows[first:]]
    result["months"] = year_rows
    candidates = list(base["conjunction_candidates"])
    extra = [conjunction(zhongji_days, i) for i in range(15, 18)]
    result["extra_conjunction_candidates"] = extra
    candidates.extend(extra)
    winter = Fraction(base["winter_source_day_counter_exact"])
    qice = Fraction(base["qice_days_exact"])
    principal_terms = tuple(winter + i * 2 * qice for i in range(15))
    expected_qi = 12
    for index in range(assignment["end_boundary_index"], len(candidates) - 1):
        current, following = candidates[index : index + 2]
        a, b = (
            c["research_conjunction_offset_from_winter_days_exact"]
            for c in (current, following)
        )
        if a is None or b is None:
            result["reason"] = "missing_required_year_tail_conjunction"
            return result
        start_time, stop_time = winter + Fraction(a), winter + Fraction(b)
        start, stop = start_time // 1, stop_time // 1
        if stop - start not in (29, 30):
            result["reason"] = "year_tail_month_length_outside_29_or_30"
            return result
        qi = [i for i in range(12, 15) if start <= principal_terms[i] // 1 < stop]
        if len(qi) > 1 or (qi and qi[0] != expected_qi):
            result["reason"] = "year_tail_principal_term_sequence_conflict"
            return result
        number = (expected_qi + 10) % 12 + 1 if qi else (expected_qi + 9) % 12 + 1
        instant_qi = [
            i for i in range(12, 15) if start_time <= principal_terms[i] < stop_time
        ]
        day = start % 60
        row = {
            "lunation_index": index,
            "start_source_day_integer": start,
            "next_start_source_day_integer": stop,
            "length_days": stop - start,
            "principal_term_indices": qi,
            "principal_terms": [TERMS[(2 * i) % 24] for i in qi],
            "instant_interval_principal_term_indices_diagnostic": instant_qi,
            "civil_and_instant_membership_differ": qi != instant_qi,
            "month_number": number,
            "is_leap_month": not qi,
            "conjunction_offset_from_winter_days_exact": a,
            "conjunction_day_cycle_exact": current[
                "research_conjunction_day_cycle_exact"
            ],
            "sexagenary_start_day": STEMS[day % 10] + BRANCHES[day % 12],
        }
        if qi:
            expected_qi += 1
        if number == 1 and qi:
            if (
                len(year_rows) not in (12, 13)
                or [m["month_number"] for m in year_rows if not m["is_leap_month"]]
                != list(range(1, 13))
                or any(
                    a["next_start_source_day_integer"] != b["start_source_day_integer"]
                    for a, b in zip(year_rows, year_rows[1:])
                )
            ):
                result["reason"] = "calendar_year_month_sequence_conflict"
                return result
            result.update(
                status="complete_under_named_fixed_qice_policy",
                month_count=len(year_rows),
                total_days=start - year_rows[0]["start_source_day_integer"],
                next_regular_first_month=row,
                complete_named_year_assigned=True,
            )
            return result
        year_rows.append(row)
    result["reason"] = "next_regular_first_month_not_bracketed"
    return result
