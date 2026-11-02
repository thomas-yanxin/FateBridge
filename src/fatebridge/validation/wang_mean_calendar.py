"""Conditional Ming Wang mean-calendar diagnostics, never a public provider.

The annual lift and its twelve equal middle-term steps are explicit algebraic
hypotheses. They do not emend the source's unresolved next-qi or leap clauses.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, TypedDict

from .taiyi_epoch import decode_day_counter

MIDDLE_TERMS = (
    "冬至",
    "大寒",
    "雨水",
    "春分",
    "穀雨",
    "小滿",
    "夏至",
    "大暑",
    "處暑",
    "秋分",
    "霜降",
    "小雪",
)


class _MiddleTerm(TypedDict):
    offset: int
    name: str
    phase: Fraction


def _ratio(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def phase_in_month(
    phase: Fraction, begin: Fraction, end: Fraction, *, assignment: str
) -> bool:
    """Use the declared half-open interval; never change it to obtain a fit."""
    if assignment not in ("civil_day", "exact_fraction"):
        raise ValueError("Explicit Wang middle-term assignment required")
    if any(not isinstance(v, Fraction) or v < 0 for v in (phase, begin, end)):
        raise ValueError("Nonnegative exact fractional Wang phases required")
    if begin >= end:
        raise ValueError("Wang phase interval must increase")
    if assignment == "civil_day":
        return int(begin) <= int(phase) < int(end)
    return begin <= phase < end


def wang_mean_window(
    nominal_ce_year: int,
    *,
    moon_year_shift: int,
    middle_term_assignment: str,
    initial_quotient_encoding: str,
) -> dict[str, Any]:
    """Trace a conditional Tianzheng11 window and every unresolved label.

    Missing winter containment or nonunique middle-term assignment leaves all
    month identities unknown. No positional or nearest-phase fallback exists.
    Both fixed quotient encodings preserve their coupled number/day-name view.
    """
    if type(nominal_ce_year) is not int or nominal_ce_year < 1:
        raise ValueError("Positive integral nominal Wang CE year required")
    if type(moon_year_shift) is not int or moon_year_shift not in (-1, 0):
        raise ValueError("Explicit Wang moon-year shift0 or-1 required")
    if middle_term_assignment not in ("civil_day", "exact_fraction"):
        raise ValueError("Explicit Wang middle-term assignment required")
    # Validate the representation even if the window has no identifiable months.
    decode_day_counter(1, encoding=initial_quotient_encoding, epoch_ganzhi="甲子")
    annual = 1937281 + nominal_ce_year - 724
    counted_years = annual + moon_year_shift
    initial, remainder = divmod(counted_years * 8126, 657)
    next_initial = (counted_years + 1) * 8126 // 657
    count = next_initial - initial
    moon_length = Fraction(1447, 49)
    year_length = 360 + Fraction(168842, 32193)
    identity = year_length == Fraction(8126 * 1447, 657 * 49)
    winter = (annual - 1) * year_length
    points = [(initial + i) * moon_length for i in range(count + 1)]
    terms: list[_MiddleTerm] = [
        {
            "offset": i,
            "name": MIDDLE_TERMS[i % 12],
            "phase": winter + i * year_length / 12,
        }
        for i in range(-1, 14)
    ]
    initial_contains_winter = phase_in_month(
        winter, points[0], points[1], assignment=middle_term_assignment
    )
    records: list[dict[str, Any]] = []
    for i, (begin, end) in enumerate(zip(points, points[1:])):
        selected = [
            t
            for t in terms
            if phase_in_month(t["phase"], begin, end, assignment=middle_term_assignment)
        ]
        value, small = divmod((initial + i) * 1447, 49)
        records.append(
            {
                "slot": i + 1,
                "accumulated_months": initial + i,
                "mean_moon_phase_raw": _ratio(begin),
                "raw_quotient": value,
                "small_remainder": small,
                "day_denominator": 49,
                "counter_view": decode_day_counter(
                    value, encoding=initial_quotient_encoding, epoch_ganzhi="甲子"
                ),
                "next_month_days": int(end) - int(begin),
                "middle_term_enumeration_complete": terms[0]["phase"] <= begin
                and end <= terms[-1]["phase"],
                "middle_terms": [
                    {
                        **{k: t[k] for k in ("offset", "name")},
                        "phase_raw": _ratio(t["phase"]),
                    }
                    for t in selected
                ],
            }
        )
    empty = [
        r["slot"]
        for r in records
        if r["middle_term_enumeration_complete"] and not r["middle_terms"]
    ]
    unknown_term_slots = [
        r["slot"] for r in records if not r["middle_term_enumeration_complete"]
    ]
    multiple = [r["slot"] for r in records if len(r["middle_terms"]) > 1]
    leap_slot = (
        empty[0]
        if count == 13 and len(empty) == 1 and empty[0] > 1 and not multiple
        else None
    )
    labels_known = (
        initial_contains_winter
        and identity
        and not unknown_term_slots
        and (
            (count == 12 and not empty and not multiple)
            or (count == 13 and leap_slot is not None)
        )
    )
    month, year = 10, nominal_ce_year - 1
    for row in records:
        leap = row["slot"] == leap_slot
        if not leap:
            month = month % 12 + 1
            if month == 1:
                year += 1
        row.update(
            {
                "lunar_year": year if labels_known else None,
                "month": month if labels_known else None,
                "is_leap_month": leap if labels_known else None,
                "conditional_identity_known": labels_known,
            }
        )
    leap_trace = []
    running = Fraction(remainder)
    for step in range(1, 14):
        before = running
        added = running + Fraction(2017, 100)
        carry = int(added // 657)
        running = added - carry * 657
        leap_trace.append(
            {
                "step": step,
                "before": _ratio(before),
                "added": _ratio(added),
                "chapter_carry": carry,
                "after": _ratio(running),
                "leap_month_label_adjudicated": False,
            }
        )
    return {
        "nominal_ce_year": nominal_ce_year,
        "annual_accumulation": annual,
        "moon_year_shift": moon_year_shift,
        "moon_counted_years": counted_years,
        "solstice_counted_years": annual - 1,
        "initial_quotient_encoding": initial_quotient_encoding,
        "middle_term_assignment": middle_term_assignment,
        "initial_accumulated_months": initial,
        "next_initial_accumulated_months": next_initial,
        "chapter_remainder": remainder,
        "chapter_remainder_denominator": 657,
        "chapter_remainder_unit": "mean_lunation_fraction; not lunar days",
        "window_month_count": count,
        "source_annual_identity_holds": identity,
        "year_length": _ratio(year_length),
        "moon_length": _ratio(moon_length),
        "middle_term_step_derived": _ratio(year_length / 12),
        "middle_term_step_is_transcribed_next_qi_clause": False,
        "lifted_winter_phase_raw": _ratio(winter),
        "winter_minus_initial_newmoon": _ratio(winter - points[0]),
        "initial_contains_winter": initial_contains_winter,
        "empty_middle_term_slots": empty,
        "unknown_middle_term_slots": unknown_term_slots,
        "term_enumeration_covers_window": not unknown_term_slots,
        "multiple_middle_term_slots": multiple,
        "conditional_leap_slot": leap_slot if labels_known else None,
        "conditional_month_identities_known": labels_known,
        "records": records,
        "printed_20_17_arithmetic": leap_trace,
        "printed_step_twelve_month_increment": _ratio(Fraction(2017, 100) * 12),
        "exact_chapter_twelve_month_excess": 8126 - 12 * 657,
        "source_leap_clause_adjudicated": False,
        "absolute_epoch_adjudicated": False,
        "production_profile_selected": False,
    }
