"""Compare explicitly named historical clock models without changing dates."""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_futen_arithmetic import (
    futen_arithmetic_lines,
    futen_arithmetic_reference,
)
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_futen_clock.json"
FUTEN = "takesako2015_1240_futen_10000"
SENMYO = "takesako2015_1240_senmyo_8400"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _ratio(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _models(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = bundle["models"]
    models = {row["id"]: row for row in rows}
    if len(rows) != 2 or set(models) != {FUTEN, SENMYO}:
        raise ValueError("符天研究的两种时制必须完整唯一")
    for name, day, koku in [(FUTEN, 10000, 100), (SENMYO, 8400, 84)]:
        row = models[name]
        if (
            any(
                type(row[key]) is not int
                for key in ["day_units", "koku_units", "double_hours_per_day"]
            )
            or (row["day_units"], row["koku_units"], row["double_hours_per_day"])
            != (day, koku, 12)
            or row["day_origin_literal"] != "子半"
        ):
            raise ValueError("符天研究时制单位或起点与所选解释不一致")
    return models


def _clock(literal: str, model: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(literal, str):
        raise ValueError("历史时点须为明确字符串")
    text = "".join(literal.split())
    match = re.fullmatch(
        r"([" + BRANCHES + r"])(時正|初刻(?:\d+分)?|\d+刻(?:\d+分)?)", text
    )
    if not match:
        raise ValueError("须明确辰、刻分或時正，不推测裸数字、半或单位")
    branch, tail = match.groups()
    day, koku = model["day_units"], model["koku_units"]
    per_branch = Fraction(day, model["double_hours_per_day"])
    if tail == "時正":
        offset = per_branch / 2
    else:
        parts = re.fullmatch(r"(初|\d+)刻(?:(\d+)分)?", tail)
        assert parts is not None
        count = 0 if parts[1] == "初" else int(parts[1])
        minute = int(parts[2] or 0)
        if minute >= koku:
            raise ValueError("时点的分栏超出所选一刻单位")
        offset = Fraction(count * koku + minute)
        if offset > per_branch:
            raise ValueError("时点超出所选一辰时")
    # The selected study starts the day at 子半. 子初 is in the preceding
    # nominal day; do not silently wrap it and lose the day shift.
    absolute = Fraction((2 * BRANCHES.index(branch) - 1) * day, 24) + offset
    day_shift = absolute // day
    return {
        "literal": literal,
        "model": model["id"],
        "within_branch_units": _ratio(offset),
        "units_from_selected_day_origin": _ratio(absolute),
        "nominal_day_fraction_from_selected_origin": _ratio(absolute / day),
        "nominal_day_shift": day_shift,
        "fraction_within_shifted_nominal_day": _ratio(absolute / day - day_shift),
        "at_next_branch_boundary": offset == per_branch,
        "civil_date_or_clock_assigned": False,
    }


def decode_clock(literal: str, *, model: str) -> dict[str, Any]:
    """Decode only a selected research model, never infer one from a date."""
    loaded = load_source(SOURCE)
    models = _models(loaded.data)
    if model not in models:
        raise ValueError("须明确选择符天研究所列的时制模型")
    return {
        **_clock(literal, models[model]),
        "source_bundle_sha256": loaded.sha256,
    }


def futen_clock_reference() -> dict[str, Any]:
    loaded = load_source(SOURCE)
    bundle = loaded.data
    models = _models(bundle)
    readings = bundle["selected_1240_readings"]
    if [row["id"] for row in readings] != ["start", "middle", "end"]:
        raise ValueError("符天研究所选三个时点须完整且按原顺序")
    comparisons = []
    values: dict[str, list[Fraction]] = {FUTEN: [], SENMYO: []}
    for row in readings:
        results = {
            name: _clock(row["literal"], model) for name, model in models.items()
        }
        exact = {
            name: Fraction(
                r["units_from_selected_day_origin"]["numerator"],
                r["units_from_selected_day_origin"]["denominator"],
            )
            for name, r in results.items()
        }
        for name in values:
            values[name].append(exact[name])
        alternative = exact[SENMYO] * 10000 / 8400
        comparisons.append(
            {
                **row,
                "decoded": results,
                "exact_futen_minus_printed_units": _ratio(
                    exact[FUTEN] - row["printed_futen_units"]
                ),
                "exact_senmyo_minus_printed_units": _ratio(
                    exact[SENMYO] - row["printed_alternative_senmyo_units"]
                ),
                "exact_senmyo_in_10000_units": _ratio(alternative),
                "exact_senmyo_in_10000_minus_printed": _ratio(
                    alternative - row["printed_alternative_in_10000_units"]
                ),
                "two_model_difference_in_nominal_days": _ratio(
                    exact[SENMYO] / 8400 - exact[FUTEN] / 10000
                ),
            }
        )
    intervals = {}
    for name, (start, middle, end) in values.items():
        intervals[name] = {
            "start_to_middle_units": _ratio(middle - start),
            "middle_to_end_units": _ratio(end - middle),
            "total_units": _ratio(end - start),
            "second_minus_first_interval_units": _ratio(end - 2 * middle + start),
            "source_asymmetry_removed": False,
        }
    return {
        **bundle,
        "source_bundle_sha256": loaded.sha256,
        "exact_units_per_double_hour": {
            name: _ratio(Fraction(row["day_units"], 12)) for name, row in models.items()
        },
        "selected_point_comparisons": comparisons,
        "exact_intervals": intervals,
        "all_three_source_points_retained": True,
        "residuals_are_not_software_or_source_error_certification": True,
        "selected_reconstruction_arithmetic": futen_arithmetic_reference(),
    }


def futen_clock_lines(reference: dict[str, Any]) -> list[str]:
    rows = reference["selected_point_comparisons"]
    labels = "、".join(row["literal"] for row in rows)

    def display(value: dict[str, int]) -> str:
        n, d = value["numerator"], value["denominator"]
        return str(n) if d == 1 else f"{n}/{d}"

    comparisons = []
    for row in rows:
        comparisons.append(
            f"{row['literal']}：万分模型精确{display(row['decoded'][FUTEN]['units_from_selected_day_origin'])}，"
            f"印出{row['printed_futen_units']}，差{display(row['exact_futen_minus_printed_units'])}；"
            f"另一模型精确{display(row['decoded'][SENMYO]['units_from_selected_day_origin'])}/8400日，"
            f"换成万分为{display(row['exact_senmyo_in_10000_units'])}，"
            f"原印{row['printed_alternative_in_10000_units']}，"
            f"差{display(row['exact_senmyo_in_10000_minus_printed'])}"
        )
    interval = reference["exact_intervals"][FUTEN]
    return [
        "符天历时刻研究另作对照：竹迫忍《符天暦法の復元》所引1240年记载的"
        f"{labels}，分别按该研究的一日10000分、一刻100分和另一宣明历一日8400分、一刻84分解释。"
        "两模型各为一日12辰时、子半起日；这是所选研究模型，不等于T1299平明起曜或所有古代历日。"
        "1164年计算的一日100分、一分100小分，以及995年说明的8分33另列，不能按同名字直接混合分母。",
        "三个时点均保留，以下万分模型量的单位为一日的1/10000，差为精确值减印值："
        + "；".join(comparisons)
        + "。万分模型起至中、中至末的精确间隔依次为"
        + display(interval["start_to_middle_units"])
        + "、"
        + display(interval["middle_to_end_units"])
        + "，总长"
        + display(interval["total_units"])
        + "，后段减前段"
        + display(interval["second_minus_first_interval_units"])
        + "；原印间隔1042、1053及总长2095另存。",
        "同三个时点的印出整数与精确分数重算并列，未将差额调平；起、中、末两段时长的不对称保留，"
        "作者因不对称怀疑某时值有误，该意见另存，不能据此认证抄本错字、统一历史时制或实测食时。尚未直接读录原1240年文书，"
        "该研究对多个符天历重建的讨论不等于完整符天历已复原，也没有给出桧尾半日或闰小月优先。"
        "本次日期、参考日界、主宿及补配分支均未由这三个历史时点改动。",
        *futen_arithmetic_lines(reference["selected_reconstruction_arithmetic"]),
    ]
