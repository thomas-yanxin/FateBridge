"""Civil-month assignment for an explicitly fixed printed mean-qi profile.

This is a source-calendar research layer. It does not convert a modern date,
adjudicate historical rounding or replace the native Guolao calendar.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_four_extras import four_extras_source_days
from fatebridge.core.guolao_lunar_velocity import gujin_table_conjunction

DATA = Path(__file__).resolve().parents[1] / "data/guolao/gujin-intercalation-v1.json"
PROFILE = "gujin36_37_45_fixed_qice_civil_months_research"
TERMS = (
    "冬至",
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "驚蟄",
    "春分",
    "清明",
    "穀雨",
    "立夏",
    "小滿",
    "芒種",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "處暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
)


def _profile() -> tuple[dict[str, Any], str]:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    if data["profile_id"] != PROFILE or tuple(
        Fraction(data[k])
        for k in ["qice_days", "month_days", "runying_days", "qiying_days"]
    ) != (
        Fraction("15.2184375"),
        Fraction("29.530593"),
        Fraction("20.205"),
        Fraction("55.06"),
    ):
        raise ValueError("具名气策、朔实与诸应不符，不自动混用或缩放")
    return data, hashlib.sha256(raw).hexdigest()


def assign_civil_sui(
    conjunctions: tuple[Fraction | None, ...],
    principal_terms: tuple[Fraction, ...],
) -> dict[str, Any]:
    """Assign one winter-to-winter cycle using civil days, with exact inputs.

    The 13 supplied principal terms include both winter solstices. A missing
    conjunction outside the required brackets is harmless; a missing required
    boundary, inconsistent term sequence or anomalous month stays unresolved.
    Inputs are unwrapped source day counters, never cycle residues or JDs.
    """
    if not isinstance(conjunctions, tuple) or not isinstance(principal_terms, tuple):
        raise TypeError("须提供原历日数元组，不接收隐式排序或可变序列")
    if len(conjunctions) < 3 or len(principal_terms) != 13:
        raise ValueError("须有足够邻朔和含两端冬至的13个中气")
    if any(t is not None and not isinstance(t, Fraction) for t in conjunctions) or any(
        not isinstance(t, Fraction) for t in principal_terms
    ):
        raise TypeError("朔气须为Fraction原历日数，缺朔只可显式为None")
    known = [t for t in conjunctions if t is not None]
    if any(a >= b for a, b in zip(known, known[1:])) or any(
        a >= b for a, b in zip(principal_terms, principal_terms[1:])
    ):
        raise ValueError("朔气必须按未取模日数严格递增，不自动排序或展开60日余数")
    days = [t // 1 if t is not None else None for t in conjunctions]
    qi_days = [t // 1 for t in principal_terms]
    result: dict[str, Any] = {
        "status": "unresolved",
        "reason": None,
        "months": [],
        "month_count": None,
        "leap_month_number": None,
        "boundary_policy": "civil_midnights_start_inclusive_next_start_exclusive",
        "same_day_qi_before_conjunction_belongs_to_new_month": True,
        "missing_conjunction_indices": [
            i for i, t in enumerate(conjunctions) if t is None
        ],
        "start_boundary_index": None,
        "end_boundary_index": None,
    }

    def bracket(day: int) -> int | None:
        found = [
            i
            for i, (a, b) in enumerate(zip(days, days[1:]))
            if a is not None and b is not None and a <= day < b
        ]
        return found[0] if len(found) == 1 else None

    first, last = bracket(qi_days[0]), bracket(qi_days[-1])
    result.update(start_boundary_index=first, end_boundary_index=last)
    if first is None or last is None:
        result["reason"] = (
            "winter_civil_day_not_bracketed_by_known_adjacent_conjunctions"
        )
        return result
    count = last - first
    result["month_count"] = count
    if count not in (12, 13):
        result["reason"] = "winter_cycle_has_neither_12_nor_13_months"
        return result
    if any(t is None for t in conjunctions[first : last + 1]):
        result["reason"] = "missing_required_conjunction_boundary"
        return result
    rows: list[dict[str, Any]] = []
    for i in range(first, last):
        start, stop = days[i], days[i + 1]
        assert start is not None and stop is not None
        indices = [j for j, t in enumerate(qi_days[:-1]) if start <= t < stop]
        a, b = conjunctions[i], conjunctions[i + 1]
        assert a is not None and b is not None
        instant_indices = [j for j, t in enumerate(principal_terms[:-1]) if a <= t < b]
        rows.append(
            {
                "boundary_index": i,
                "start_source_day_integer": start,
                "next_start_source_day_integer": stop,
                "length_days": stop - start,
                "principal_term_indices": indices,
                "instant_interval_principal_term_indices_diagnostic": instant_indices,
                "civil_and_instant_membership_differ": indices != instant_indices,
                "month_number": None,
                "is_leap_month": None,
            }
        )
    result["months"] = rows
    if any(row["length_days"] not in (29, 30) for row in rows):
        result["reason"] = "source_month_length_outside_29_or_30_not_repaired"
        return result
    empty = [i for i, row in enumerate(rows) if not row["principal_term_indices"]]
    if len(empty) != count - 12 or any(
        len(row["principal_term_indices"]) > 1 for row in rows
    ):
        result["reason"] = "principal_term_pattern_not_unique_for_this_mean_qi_policy"
        return result
    expected = 11
    for row in rows:
        indices = row["principal_term_indices"]
        if indices:
            number = (indices[0] + 10) % 12 + 1
            if number != expected:
                result["reason"] = "principal_term_month_sequence_conflict"
                return result
            expected = number % 12 + 1
            row.update(month_number=number, is_leap_month=False)
        else:
            number = (expected - 2) % 12 + 1
            row.update(month_number=number, is_leap_month=True)
            result["leap_month_number"] = number
    result.update(status="assigned_under_explicit_civil_mean_qi_policy", reason=None)
    return result


def gujin_fixed_qice_months(
    zhongji_days: Fraction, *, conjunction_method: str = "floor_table"
) -> dict[str, Any]:
    """Keep the printed qi interval fixed; never silently century-rescale it."""
    if not isinstance(zhongji_days, Fraction):
        raise TypeError("中积须为Fraction原历日数，不接收现代JD浮点值")
    if zhongji_days < 0:
        raise ValueError("这里只重建下算，上考不借负中积套用")
    from fatebridge.core.guolao_cumulative_table import (
        CALENDAR_PROFILE as LITERAL_CALENDAR_PROFILE,
    )
    from fatebridge.core.guolao_cumulative_table import gujin_literal_conjunction
    from fatebridge.core.guolao_day_rate import (
        CALENDAR_PROFILE,
        gujin_day_rate_conjunction,
        validate_method,
    )

    validate_method(conjunction_method)
    conjunction = (
        gujin_table_conjunction
        if conjunction_method == "floor_table"
        else (
            gujin_day_rate_conjunction
            if conjunction_method == "day_rate"
            else gujin_literal_conjunction
        )
    )
    profile_id = (
        PROFILE
        if conjunction_method == "floor_table"
        else (
            CALENDAR_PROFILE
            if conjunction_method == "day_rate"
            else LITERAL_CALENDAR_PROFILE
        )
    )
    return _fixed_qice_months_from_conjunctions(zhongji_days, profile_id, conjunction)


def _fixed_qice_months_from_conjunctions(
    zhongji_days: Fraction,
    profile_id: str,
    conjunction: Callable[[Fraction, int], dict[str, Any]],
) -> dict[str, Any]:
    """Assign the declared conjunction branch without selecting it by fit."""
    p, digest = _profile()
    winter = zhongji_days + Fraction(p["qiying_days"])
    qice = Fraction(p["qice_days"])
    month = Fraction(p["month_days"])
    runyu = (zhongji_days + Fraction(p["runying_days"])) % month
    month_run = 2 * qice - month
    # This estimate is not the final leap-month answer.
    estimate = (month - runyu) // month_run
    empty_index = -((runyu - month) // month_run)
    mean_has_leap = runyu >= month - 12 * month_run
    candidates = [conjunction(zhongji_days, i) for i in range(15)]
    offsets = [
        c["research_conjunction_offset_from_winter_days_exact"] for c in candidates
    ]
    instants = tuple(winter + Fraction(o) if o is not None else None for o in offsets)
    terms = [
        {
            "term_index": i,
            "name": TERMS[i],
            "is_principal_term": i % 2 == 0,
            "offset_from_winter_days_exact": str(i * qice),
            "source_day_counter_exact": str(winter + i * qice),
            "civil_day_integer": (winter + i * qice) // 1,
            "day_cycle_exact": str((winter + i * qice) % 60),
        }
        for i in range(25)
    ]
    assignment = assign_civil_sui(
        instants, tuple(winter + 2 * i * qice for i in range(13))
    )
    for row in assignment["months"]:
        c = candidates[row["boundary_index"]]
        row["lunation_index"] = row.pop("boundary_index")
        row["conjunction_offset_from_winter_days_exact"] = c[
            "research_conjunction_offset_from_winter_days_exact"
        ]
        row["conjunction_day_cycle_exact"] = c["research_conjunction_day_cycle_exact"]
        day = row["start_source_day_integer"] % 60
        row["sexagenary_start_day"] = STEMS[day % 10] + BRANCHES[day % 12]
        row["principal_terms"] = [TERMS[2 * i] for i in row["principal_term_indices"]]
    return {
        "model_id": "gujin_fixed_qice_month_assignment_v1",
        "profile_id": profile_id,
        "source_data_sha256": digest,
        "source_provenance": p["sources"],
        "zhongji_days_exact": str(zhongji_days),
        "winter_source_day_counter_exact": str(winter),
        "qice_days_exact": str(qice),
        "fixed_term_cycle_days_exact": str(24 * qice),
        "runyu_days_exact": str(runyu),
        "month_run_days_exact": str(month_run),
        "mean_leap_estimate": {
            "has_leap_by_printed_run_limit": mean_has_leap,
            "quotient_of_month_minus_runyu_by_month_run": estimate,
            "candidate_empty_lunation_index": empty_index if mean_has_leap else None,
            "candidate_leap_month_number": (
                (empty_index + 9) % 12 + 1 if mean_has_leap else None
            ),
            "mean_boundary_policy": "principal_qi_at_exact_mean_conjunction_belongs_to_new_month",
            "accepted_as_final_month": False,
        },
        "solar_terms": terms,
        "month_assignment": assignment,
        "conjunction_candidates": candidates,
        "civil_policy_historical_acceptance": False,
        "complete_source_calendar_accepted": False,
        "modern_epoch_calibrated": False,
        "modern_lunar_date": None,
        "used_in_native_birth_chart": False,
        "limitations": p["limitations"],
    }


def gujin_four_extras_calendar(zhongji_days: Fraction) -> dict[str, Any]:
    """Find all four entry dates in the assigned cycle, never in a mean slot."""
    calendar = gujin_fixed_qice_months(zhongji_days)
    events = four_extras_source_days(zhongji_days)
    assignment = calendar["month_assignment"]
    winter = Fraction(calendar["winter_source_day_counter_exact"])
    factors = {}
    for key, event in events["factors"].items():
        total = winter + Fraction(event["days_until_next_entry_exact"])
        matches = [
            row
            for row in assignment["months"]
            if assignment["status"] == "assigned_under_explicit_civil_mean_qi_policy"
            and row["start_source_day_integer"]
            <= total // 1
            < row["next_start_source_day_integer"]
        ]
        date = None
        if len(matches) == 1:
            row = matches[0]
            date = {
                "month_number": row["month_number"],
                "is_leap_month": row["is_leap_month"],
                "day": total // 1 - row["start_source_day_integer"] + 1,
                "lunation_index": row["lunation_index"],
            }
        factors[key] = {
            "event_source_day_counter_exact": str(total),
            "source_calendar_date_under_named_policy": date,
            "status": (
                "assigned_research_date"
                if date is not None
                else "outside_or_unresolved_cycle"
            ),
            "modern_lunar_date": None,
        }
    return {"calendar": calendar, "factors": factors}
