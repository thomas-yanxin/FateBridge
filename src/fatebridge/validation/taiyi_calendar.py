"""Exact diagnostics for source-scoped Taiyi mean-calendar constants.

This does not resolve historical dates or install a calendar profile. Inferred
values stay separate from literal readings, including when an equation has a
unique solution. Relations are compatibility checks, not dated ancient cases.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Any

Readings = dict[str, dict[str, Any]]


def _value(readings: Readings, name: str) -> Fraction | None:
    value = readings[name]["value"]
    if value is None:
        return None
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, dict) and set(value) == {"numerator", "denominator"}:
        numerator, denominator = value["numerator"], value["denominator"]
        if type(numerator) is int and type(denominator) is int and denominator > 0:
            return Fraction(numerator, denominator)
    raise ValueError(f"Invalid exact source value: {name}")


def _required(readings: Readings, name: str) -> Fraction:
    value = _value(readings, name)
    if value is None:
        raise ValueError(f"Unresolved required constant: {name}")
    return value


def _ratio(value: Fraction | None) -> dict[str, int] | None:
    if value is None:
        return None
    return {"numerator": value.numerator, "denominator": value.denominator}


def _relation(
    name: str,
    left: Fraction | None,
    right: Fraction | None,
    formula: str,
    fields: list[str],
    unit: str,
) -> dict[str, Any]:
    if left is None or right is None:
        status, difference = "unresolved", None
    else:
        status = "matching" if left == right else "different"
        difference = left - right
    return {
        "id": name,
        "status": status,
        "left": _ratio(left),
        "right": _ratio(right),
        "difference": _ratio(difference),
        "unit": unit,
        "formula": formula,
        "source_fields": fields,
    }


def audit_edition(readings: Readings) -> dict[str, Any]:
    """Keep all eight relations, including unparsed and incompatible ones."""

    def v(name: str) -> Fraction:
        return _required(readings, name)

    years, months = v("chapter_years"), v("chapter_months")
    day, month = v("day_denominator"), v("month_numerator")
    qi = v("qi_denominator")
    if (
        min(
            years,
            months,
            day,
            month,
            qi,
            v("double_hour_fraction_denominator"),
            v("sexagenary_day_cycle"),
            v("solstice_interval_denominator"),
        )
        <= 0
    ):
        raise ValueError("Calendar moduli and cycle counts must be positive")
    if years.denominator != 1 or months.denominator != 1:
        raise ValueError("Chapter years/months must be integral source counts")
    annual = months * month / (years * day)
    half_hour = v("half_double_hour_integer") + v(
        "half_double_hour_fraction_numerator"
    ) / v("double_hour_fraction_denominator")
    residue = _value(readings, "annual_residue_numerator")
    interval = v("solstice_interval_integer_days") + v(
        "solstice_interval_fraction_numerator"
    ) / v("solstice_interval_denominator")
    relations = [
        _relation(
            "month_fraction",
            month,
            v("synodic_integer_days") * day + v("synodic_fraction_numerator"),
            "月法 = 朔策×日法 + 小餘",
            [
                "month_numerator",
                "synodic_integer_days",
                "day_denominator",
                "synodic_fraction_numerator",
            ],
            "日法分",
        ),
        _relation(
            "year_day_denominator",
            qi,
            years * day,
            "氣法 = 章歲×日法",
            ["qi_denominator", "chapter_years", "day_denominator"],
            "原數比例檢查",
        ),
        _relation(
            "half_hour_day_scale",
            qi,
            24 * half_hour,
            "氣法 = 24×半辰法",
            [
                "qi_denominator",
                "half_double_hour_integer",
                "half_double_hour_fraction_numerator",
                "double_hour_fraction_denominator",
            ],
            "氣法分",
        ),
        _relation(
            "annual_residue",
            annual % v("sexagenary_day_cycle"),
            residue / qi if residue is not None else None,
            "(章月×月法÷(章歲×日法)) mod 紀法 = 全數÷氣法",
            [
                "chapter_months",
                "month_numerator",
                "chapter_years",
                "day_denominator",
                "sexagenary_day_cycle",
                "annual_residue_numerator",
                "qi_denominator",
            ],
            "日",
        ),
        _relation(
            "two_solstice_intervals",
            annual,
            2 * interval,
            "章月×月法÷(章歲×日法) = 2×冬夏至間隔",
            [
                "chapter_months",
                "month_numerator",
                "chapter_years",
                "day_denominator",
                "solstice_interval_integer_days",
                "solstice_interval_fraction_numerator",
                "solstice_interval_denominator",
            ],
            "日；等長二至間隔的相容性，不是實際定氣",
        ),
    ]
    numerator = _value(readings, "double_hour_fraction_numerator")
    integer, denominator = (
        v("double_hour_integer"),
        v("double_hour_fraction_denominator"),
    )
    if denominator <= 0:
        raise ValueError("Double-hour fraction denominator must be positive")
    candidate = (2 * half_hour - integer) * denominator
    proper = 0 <= candidate < denominator
    double_hour = _relation(
        "double_hour_fraction",
        integer + numerator / denominator if numerator is not None else None,
        2 * half_hour,
        "辰法 = 2×半辰法；未讀定的小分不由方程反填",
        [
            "double_hour_integer",
            "double_hour_fraction_numerator",
            "double_hour_fraction_denominator",
            "half_double_hour_integer",
            "half_double_hour_fraction_numerator",
        ],
        "氣法分",
    )
    if numerator is None and not proper:
        double_hour["status"] = "different"
    double_hour.update(
        required_numerator_if_identity=_ratio(candidate),
        proper_fraction_can_satisfy=proper,
        literal_numerator_adjudicated=numerator is not None,
        assumption="小分按0≤分子<分母解讀；負候選只證此解讀不能相容，不是改字值。",
    )
    relations.append(double_hour)
    # The source's small-remainder phrase is not numerically parsed. Deriving a
    # compatible increment does not supply missing glyphs or certify the rule.
    next_qi = _relation(
        "next_qi_increment",
        _value(readings, "next_qi_increment"),
        None,
        "原次氣小餘／秒的分組未裁定，不按年長反填原文",
        ["next_qi_increment"],
        "原文未定",
    )
    if all(r["status"] == "matching" for r in relations[:5]):
        remainder = (annual / 24 - 15) * qi
        whole = remainder // 1
        next_qi["inferred_compatible_candidate_not_source_value"] = {
            "integer_days": 15,
            "small_remainder": _ratio(remainder),
            "integer_small_remainder": whole,
            "seconds_if_unit_is_one_24th": _ratio((remainder - whole) * 24),
            "adopted": False,
        }
    relations.append(next_qi)
    seconds_denominator = v("seconds_denominator")
    if seconds_denominator <= 0:
        raise ValueError("Seconds denominator must be positive")
    step = v("leap_step_integer") + v("leap_step_seconds") / seconds_denominator
    advance = step * months
    low = advance // years
    high = low + int(advance % years != 0)
    required_leaps = months - 12 * years
    carries = sorted({low, high})
    regular_months = 12 * years
    regular_advance = step * regular_months
    regular_low = regular_advance // years
    regular_high = regular_low + int(regular_advance % years != 0)
    relations.append(
        {
            "id": "literal_leap_step_cycle",
            "status": "matching" if required_leaps in carries else "different",
            "required_leap_months": int(required_leaps),
            "possible_literal_carries": carries,
            "literal_step": _ratio(step),
            "aggregate_remainder": _ratio(advance % years),
            "step_needed_for_exact_cycle_closure_not_adopted": _ratio(
                required_leaps * years / months
            ),
            "source_fields": [
                "chapter_years",
                "chapter_months",
                "leap_step_integer",
                "leap_step_seconds",
                "seconds_denominator",
            ],
            "assumption": "若每個積月均加固定閏差，0≤初餘<章歲，滿章歲減章歲一次；只檢此單步解讀。",
            "scope": "原無中氣與提前置閏分支未復原；這不是完整置閏法或歷表的成敗裁定。",
            "post_freeze_regular_month_only_hypothesis_not_adopted": {
                "advanced_months": int(regular_months),
                "possible_carries": sorted({regular_low, regular_high}),
                "exact_residual_after_required_leaps": _ratio(
                    regular_advance - required_leaps * years
                ),
                "step_needed_for_exact_closure": _ratio(
                    required_leaps * years / regular_months
                ),
                "exact_cycle_closure": regular_advance == required_leaps * years,
                "scope": "另試只在平月加差；沒有因此改寫原16項判據或選用此法。進位數可相符仍不等於閏餘閉合。",
            },
        }
    )
    return {
        "relations": relations,
        "counts": dict(Counter(r["status"] for r in relations)),
        "derived_annual_days": _ratio(annual),
        "source_values_rewritten": False,
        "dated_cases": 0,
        "whole_calendar_acceptance": False,
    }


def audit_calendar_constants(editions: dict[str, Any]) -> dict[str, Any]:
    results = {
        name: audit_edition(edition["readings"]) for name, edition in editions.items()
    }
    counts = Counter(
        r["status"] for result in results.values() for r in result["relations"]
    )
    return {
        "scope": "Selected-edition exact-rational compatibility diagnostics; this diagnostic installs no calendar provider",
        "editions": results,
        "counts": dict(counts),
        "dated_cases": 0,
        "counts_are_independent_calendar_samples": False,
        "whole_calendar_acceptance": False,
        "interpretation_policy": "原字、數值解析、算術候選分開；不以自洽取代原典裁定或實際歷日驗收。",
    }
