"""Exact Yuanjia mean-moon diagnostics, separate from Wang's Taiyi calendar.

Songshu13 supplies the constants and443 elapsed-year anchors. This module
does not supply an absolute Julian epoch or a public calendar provider.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from .taiyi_epoch import decode_day_counter

JI_NAMES = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
MIDDLE_TERMS = (
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
    "冬至",
    "大寒",
)


def _fraction(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def yuanjia_mean_year(
    elapsed_years: int, *, middle_term_assignment: str
) -> dict[str, Any]:
    """Keep both declared qi-assignment readings; never select one by fit.

    The printed chapter quotient is retained without equating its count to
    an adjudicated leap-month label. Unique empty months supply a conditional
    label under the requested qi-assignment reading, including known failures.
    """
    if type(elapsed_years) is not int or elapsed_years < 0:
        raise ValueError("Yuanjia requires nonnegative integral elapsed years")
    if middle_term_assignment not in ("civil_day", "exact_fraction"):
        raise ValueError("Explicit Yuanjia middle-term assignment required")
    yuan, within_yuan = divmod(elapsed_years, 3648)
    ji_index, within_ji = divmod(within_yuan, 608)
    initial_months, leap_remainder = divmod(within_ji * 235, 19)
    next_months = (within_ji + 1) * 235 // 19
    month_count = next_months - initial_months
    leap_year = leap_remainder >= 12
    if month_count != 12 + int(leap_year):
        raise ValueError("Yuanjia chapter count and leap-year threshold disagree")
    moon_length = Fraction(22207, 752)
    year_length = Fraction(222070, 608)
    # The source's1595/304 phase has360 complete days removed per year.
    rainwater = within_ji * year_length
    terms: list[dict[str, Any]] = [
        {
            "offset": i,
            "name": MIDDLE_TERMS[i % 12],
            "phase": rainwater + i * year_length / 12,
        }
        for i in range(-1, 14)
    ]
    moon_points = [(initial_months + i) * moon_length for i in range(month_count + 1)]
    phase_rows: list[dict[str, Any]] = []
    for i in range(month_count):
        begin, end = moon_points[i : i + 2]
        small = (begin - int(begin)) * 752
        if small.denominator != 1:
            raise ValueError("Yuanjia mean moon lost its integral small remainder")
        selected = [
            t
            for t in terms
            if (
                int(begin) <= int(t["phase"]) < int(end)
                if middle_term_assignment == "civil_day"
                else begin <= t["phase"] < end
            )
        ]
        phase_rows.append(
            {
                "ordinal_slot": i + 1,
                "day_within_ji": int(begin),
                "small_remainder": small.numerator,
                "day_denominator": 752,
                "mean_moon_phase": _fraction(begin),
                "next_month_days": int(end) - int(begin),
                "large_from_printed353_threshold": small >= 353,
                "first_ganzhi": decode_day_counter(
                    int(begin),
                    encoding="completed_days",
                    epoch_ganzhi=JI_NAMES[ji_index],
                )["day_ganzhi"],
                "middle_terms": [
                    {
                        "offset": t["offset"],
                        "name": t["name"],
                        "phase": _fraction(t["phase"]),
                    }
                    for t in selected
                ],
            }
        )
    empty_slots = [r["ordinal_slot"] for r in phase_rows if not r["middle_terms"]]
    leap_slot = (
        empty_slots[0]
        if leap_year and len(empty_slots) == 1 and empty_slots[0] > 1
        else None
    )
    regular_number = 0
    for row in phase_rows:
        is_leap = row["ordinal_slot"] == leap_slot
        if not is_leap:
            regular_number += 1
        row["month"] = regular_number if not leap_year or leap_slot else None
        row["is_leap_month"] = is_leap if not leap_year or leap_slot else None
    last = moon_points[-1]
    return {
        "elapsed_years": elapsed_years,
        "complete_yuan": yuan,
        "ji_index_one_based": ji_index + 1,
        "ji_ganzhi": JI_NAMES[ji_index],
        "elapsed_years_within_ji": within_ji,
        "initial_accumulated_months": initial_months,
        "leap_remainder": leap_remainder,
        "chapter_leap_year": leap_year,
        "month_count": month_count,
        "nominal_leap_count_raw": (
            (19 - leap_remainder) * 12 // 7 if leap_year else None
        ),
        "nominal_count_is_adjudicated_month_or_slot": False,
        "middle_term_assignment": middle_term_assignment,
        "empty_middle_term_slots": empty_slots,
        "conditional_leap_slot": leap_slot,
        "middle_term_assignment_adjudicated": False,
        "moon_length": _fraction(moon_length),
        "year_length": _fraction(year_length),
        "rainwater_phase_within_ji": _fraction(rainwater),
        "records": phase_rows,
        "next_year_first": {
            "day_within_previous_ji": int(last),
            "first_ganzhi": decode_day_counter(
                int(last), encoding="completed_days", epoch_ganzhi=JI_NAMES[ji_index]
            )["day_ganzhi"],
        },
        "absolute_julian_epoch_proved": False,
        "source_multiply_argument": "accumulated_months_under_explicit_dimensional_reading",
        "scope": "Yuanjia phase and conditional month-label diagnostics. No absolute epoch, Wang calendar identity, historical time-zone or public-provider claim.",
    }
