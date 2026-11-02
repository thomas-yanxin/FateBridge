"""Exact arithmetic for the named NAOJ 2019 Guchureki clock interpretation.

This does not assign an ancient daybreak, civil time, Gregorian date or Hinoo
half. The study's 360-day seasonal axis is not a civil-day counter.
"""

from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_naoj_guchureki_clock.json"
MODEL = "naoj2019_guchureki_50koku6fun"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _ratio(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _units(bundle: dict[str, Any]) -> tuple[int, int, int]:
    units = bundle["selected_model"]
    values = [
        units[k] for k in ["double_hours_per_day", "koku_per_day", "fun_per_koku"]
    ]
    if any(type(v) is not int or v <= 0 for v in values):
        raise ValueError("具注历所选单位须为正整数")
    hours, koku, fun = values
    if units["id"] != MODEL or (hours, koku, fun) != (12, 50, 6):
        raise ValueError("单位不符合所选NAOJ2019五十刻模型")
    return hours, koku, fun


def _quantity(text: str, fun_per_koku: int) -> Fraction:
    """Read a quantity, including the table's noncanonical sum 3刻7分."""
    if not isinstance(text, str):
        raise ValueError("刻分量须为明确字符串")
    text = "".join(text.split())
    match = re.fullmatch(r"(?:(\d+)刻)?(?:(\d+)分(半)?)?", text)
    if not match or not any(match.groups()):
        raise ValueError("刻分量须明确单位；不把裸半或半刻改读为半分")
    koku, fun, half = match.groups()
    return Fraction(int(koku or 0) * fun_per_koku + int(fun or 0)) + (
        Fraction(1, 2) if half else 0
    )


def _clock(text: str, bundle: dict[str, Any]) -> dict[str, Any]:
    hours, koku_per_day, fun_per_koku = _units(bundle)
    if not isinstance(text, str):
        raise ValueError("辰刻时点须为明确字符串")
    normalized = "".join(text.split())
    match = re.fullmatch(
        r"([" + BRANCHES + r"])(時正|初(?:\d+分(?:半)?)?|\d+刻(?:\d+分(?:半)?)?)",
        normalized,
    )
    if not match:
        raise ValueError("辰刻时点须明确初、刻分或時正；不猜裸半的单位")
    branch, tail = match.groups()
    per_day = koku_per_day * fun_per_koku
    per_hour = Fraction(per_day, hours)
    if tail == "時正":
        offset = per_hour / 2
    else:
        quantity = "0刻" + tail[1:] if tail.startswith("初") else tail
        offset = _quantity(quantity, fun_per_koku)
        fun_match = re.search(r"(\d+)分", quantity)
        if fun_match and int(fun_match[1]) >= fun_per_koku:
            raise ValueError("时点的分栏须小于六；表中和数另按量计算")
        if offset > per_hour:
            raise ValueError("时点超过一辰刻；四刻一分是下一辰刻边界")
    boundary = offset == per_hour
    return {
        "literal": text,
        "normalized_literal": normalized,
        "branch": branch,
        "within_branch_fun": _ratio(offset),
        "within_branch_nominal_day_fraction": _ratio(offset / per_day),
        "nominal_24h_equivalent_seconds_from_branch_start": _ratio(
            offset * 86400 / per_day
        ),
        "at_next_branch_boundary": boundary,
        "next_branch_if_boundary": (
            BRANCHES[(BRANCHES.index(branch) + 1) % 12] if boundary else None
        ),
        "civil_date_or_clock_assigned": False,
    }


def decode_clock(text: str, *, model: str) -> dict[str, Any]:
    """Decode only an explicitly selected model, never infer it from a date."""
    if model != MODEL:
        raise ValueError("必须明确选择所选NAOJ2019五十刻模型")
    source = load_source(SOURCE)
    return {
        **_clock(text, source.data),
        "model": model,
        "source_bundle_sha256": source.sha256,
    }


def quantity_fun(text: str, *, model: str) -> dict[str, int]:
    if model != MODEL:
        raise ValueError("必须明确选择所选NAOJ2019五十刻模型")
    bundle = load_source(SOURCE).data
    return _ratio(_quantity(text, _units(bundle)[2]))


def seasonal_ordinal(label: str) -> int:
    """Count the study's nominal seasonal labels, excluding 没日, not dates."""
    bundle = load_source(SOURCE).data
    if not isinstance(label, str):
        raise ValueError("须提供平气节气日标签，不能用民用日期替代")
    match = re.fullmatch(r"(.+?)(\d+)日", label)
    names: list[str] = bundle["seasonal_axis"]["term_order_from_winter_solstice"]
    if not match or match[1] not in names or not 1 <= int(match[2]) <= 15:
        raise ValueError("平气标签须为所选二十四气及一至十五日")
    return names.index(match[1]) * 15 + int(match[2])


def _assess(bundle: dict[str, Any], *, include_all_rows: bool) -> dict[str, Any]:
    hours, koku, fun = _units(bundle)
    expected = Fraction(koku * fun, hours)
    residuals: Counter[str] = Counter()
    rows, exceptional_groups, errors = [], set(), []
    groups = bundle["record_groups"]
    for index, group in enumerate(groups):
        # Use this same captured bundle for labels, units, readings and digest.
        label_match = re.fullmatch(r"(.+?)(\d+)日", group["season_label"])
        names = bundle["seasonal_axis"]["term_order_from_winter_solstice"]
        if not label_match or label_match[1] not in names:
            errors.append(["season_label", group["id"]])
        elif (
            names.index(label_match[1]) * 15 + int(label_match[2])
            != group["nominal_seasonal_ordinal"]
        ):
            errors.append(["seasonal_ordinal", group["id"]])
        gap = (
            groups[(index + 1) % len(groups)]["nominal_seasonal_ordinal"]
            - group["nominal_seasonal_ordinal"]
        ) % 360
        if gap != group["printed_interval_to_next"]:
            errors.append(["nominal_interval", group["id"]])
        for number, reading in enumerate(group["readings"]):
            sunrise, sunset = [
                _clock(reading[key], bundle) for key in ["sunrise", "sunset"]
            ]
            a, b = [
                Fraction(
                    row["within_branch_fun"]["numerator"],
                    row["within_branch_fun"]["denominator"],
                )
                for row in [sunrise, sunset]
            ]
            total = a + b
            printed = reading["printed_sum"]
            if printed is not None and total != _quantity(printed, fun):
                errors.append(["printed_sum", group["id"], number])
            residual = total - expected
            residuals[str(residual)] += 1
            if residual:
                exceptional_groups.add(group["id"])
            rows.append(
                {
                    "group_id": group["id"],
                    "season_label": group["season_label"],
                    "nominal_seasonal_ordinal": group["nominal_seasonal_ordinal"],
                    "reading_index": number,
                    "sunrise_literal": reading["sunrise"],
                    "sunset_literal": reading["sunset"],
                    "printed_sum": printed,
                    "computed_sum_fun": _ratio(total),
                    "symmetry_residual_fun": _ratio(residual),
                    "alternative_readings_preserved": len(group["readings"]) > 1,
                }
            )
    result: dict[str, Any] = {
        "record_groups_checked": len(groups),
        "paired_readings_checked": len(rows),
        "source_study_claims_not_independent_observations": True,
        "exact_symmetry_target_fun": _ratio(expected),
        "residual_counts_by_exact_fun": dict(residuals),
        "nonzero_residual_groups_retained": len(exceptional_groups),
        "nonzero_residual_readings_retained": sum(
            v for k, v in residuals.items() if k != "0"
        ),
        "exception_readings": [
            r for r in rows if r["symmetry_residual_fun"]["numerator"]
        ],
        "table_printed_sums_and_nominal_intervals_errors": errors,
        "nonzero_source_residuals_are_not_software_errors": True,
    }
    if include_all_rows:
        result["all_readings"] = rows
    return result


def clock_arithmetic_reference(*, include_all_rows: bool = False) -> dict[str, Any]:
    source = load_source(SOURCE)
    bundle = source.data
    hours, koku, fun = _units(bundle)
    senmyo = bundle["comparative_units"]["senmyoreki_clock_definition"]
    result = {key: value for key, value in bundle.items() if key != "record_groups"}
    result.update(
        source_bundle_sha256=source.sha256,
        exact_unit_relations={
            "fun_per_double_hour": _ratio(Fraction(koku * fun, hours)),
            "fun_at_shizheng": _ratio(Fraction(koku * fun, hours * 2)),
            "nominal_seconds_per_fun": _ratio(Fraction(86400, koku * fun)),
            "nominal_seconds_per_half_fun": _ratio(Fraction(43200, koku * fun)),
            "nominal_seconds_per_half_koku": _ratio(Fraction(43200, koku)),
            "half_koku_minus_half_fun_nominal_seconds": _ratio(
                Fraction(43200, koku) - Fraction(43200, koku * fun)
            ),
            "fifty_vs_hundred_koku_unit_ratio": _ratio(
                Fraction(senmyo["koku_per_day"], koku)
            ),
            "guchureki_vs_senmyoreki_fun_unit_ratio": _ratio(
                Fraction(
                    senmyo["double_hours_per_day"]
                    * (
                        senmyo["whole_koku_per_double_hour"] * senmyo["fun_per_koku"]
                        + senmyo["remainder_fun_per_double_hour"]
                    ),
                    koku * fun,
                )
            ),
        },
        table_check=_assess(bundle, include_all_rows=include_all_rows),
    )
    return result
