"""Audit a named reconstruction's arithmetic without assigning historical dates."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_futen_arithmetic.json"
UNIT_SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_futen_clock.json"
CANONICAL_SHA256 = "fbcd437bead47a0a82121604b8030b41e12fb14fe067872ff50e2addaa2febd6"
DAY_CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
    for i in range(60)
)


def _ratio(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _cycle(units: int, day_units: int) -> dict[str, Any]:
    units %= 60 * day_units
    index, remainder = divmod(units, day_units)
    return {
        "cycle_units": units,
        "cycle_index": index,
        "ganzhi": DAY_CYCLE[index],
        "remainder_units": remainder,
    }


def futen_arithmetic_reference() -> dict[str, Any]:
    """Recompute all fifteen printed means and sums, retaining source conflicts.

    The correction values are read from the lecture, not reconstructed from
    astronomical formulae. Neither this example nor an arithmetic discrepancy
    identifies an issued calendar, a physical manuscript error, or a day boundary.
    """
    loaded = load_source(SOURCE)
    bundle = loaded.data
    projection = json.dumps(
        bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(projection).hexdigest() != CANONICAL_SHA256:
        raise ValueError("符天讲义所选常数、十五行或未决印值已改变，须重新校核")
    c = bundle["constants"]
    unit_source = load_source(UNIT_SOURCE)
    unit_bundle = unit_source.data
    models = {row["id"]: row for row in unit_bundle["models"]}
    model_ids = {
        "senmyo": "takesako2015_1240_senmyo_8400",
        "futen": "takesako2015_1240_futen_10000",
    }
    if len(unit_bundle["models"]) != 2 or set(models) != set(model_ids.values()):
        raise ValueError("进朔限名义单位须绑定完整两种既有研究模型")
    printed = bundle["printed_example"]
    day = c["day_units"]
    cycle = c["cycle_days"] * day
    accumulated = (c["example_year"] - c["epoch_year"]) * c["solar_year_units"]
    rain = (accumulated + c["qi_ying_units"]) % cycle
    run0 = accumulated % c["mean_lunation_units"]
    run = (accumulated + c["run_ying_units"]) % c["mean_lunation_units"]
    # The cycle coordinate includes 氣應. The lunar anomaly uses the source's
    # distinct unadjusted 閏餘o, not the adjusted elapsed rain-to-mean interval.
    mean = (rain - run) % cycle
    anomaly = (accumulated - run0 + c["zhuan_ying_units"]) % c[
        "anomalistic_month_units"
    ]
    mean_without_qi_ying = (accumulated - run) % cycle
    winter = Fraction(c["solar_year_units"], 6) - run
    rows = []
    for row in bundle["rows"]:
        calculated_mean = (
            mean + row["lunation_offset"] * c["mean_lunation_units"]
        ) % cycle
        calculated_true = (
            calculated_mean
            + row["printed_solar_correction_units"]
            + row["printed_lunar_correction_units"]
        ) % cycle
        rows.append(
            {
                **row,
                "calculated_mean": _cycle(calculated_mean, day),
                "sum_using_printed_corrections": _cycle(calculated_true, day),
                "mean_minus_printed_units": calculated_mean
                - (row["mean_cycle_index"] * day + row["mean_remainder"]),
                "sum_minus_printed_units": calculated_true
                - (row["true_cycle_index"] * day + row["true_remainder"]),
                "correction_functions_reconstructed": False,
            }
        )
    plus11 = next(
        row
        for row in rows
        if row["lunation_offset"] == printed["eleventh_step_lunation_offset"]
    )
    thresholds = []
    for row in bundle["threshold_labels"]:
        model = models[model_ids[row["model"]]]
        if model["day_units"] != row["day_units"]:
            raise ValueError("进朔限名义换算单位与所引研究模型不一致")
        nominal_hour = Fraction(24 * row["printed_threshold_units"], row["day_units"])
        units_at_hour = Fraction(row["printed_hour"] * row["day_units"], 24)
        thresholds.append(
            {
                **row,
                "conditional_unit_model_id": model["id"],
                "nominal_hours_from_printed_units": _ratio(nominal_hour),
                "units_at_printed_nominal_hour": _ratio(units_at_hour),
                "printed_units_minus_units_at_hour": _ratio(
                    row["printed_threshold_units"] - units_at_hour
                ),
                "nominal_hours_minus_printed_hour": _ratio(
                    nominal_hour - row["printed_hour"]
                ),
                "printed_values_overwritten": False,
                "threshold_selected_for_calendar": False,
            }
        )
    return {
        **bundle,
        "source_bundle_sha256": loaded.sha256,
        "calculated_chain": {
            "accumulated_units": accumulated,
            "rain_cycle": _cycle(rain, day),
            "unadjusted_run_remainder": run0,
            "adjusted_run_remainder": run,
            "mean_cycle_with_qi_ying": _cycle(mean, day),
            "mean_literal_without_qi_ying": _cycle(mean_without_qi_ying, day),
            "literal_without_qi_ying_minus_printed_units": mean_without_qi_ying
            - printed["mean_cycle_units"],
            "anomaly_units": anomaly,
            "anomaly_dependency": {
                "source_page": 53,
                "remainder_basis": "unadjusted_run_remainder",
                "remainder_units": run0,
                "accumulated_units": accumulated,
                "zhuan_ying_units": c["zhuan_ying_units"],
                "modulus_units": c["anomalistic_month_units"],
                "formula": "(accumulated - unadjusted_run_remainder + zhuan_ying) modulo anomalistic_month",
            },
            "winter_to_mean_units_exact": _ratio(winter),
            "winter_exact_minus_printed_units": _ratio(
                winter - printed["winter_to_mean_units"]
            ),
            "rain_cycle_days_exact": _ratio(Fraction(rain, day)),
            "rain_cycle_days_using_printed_denominator": _ratio(
                Fraction(rain, printed["rain_fraction_denominator_literal"])
            ),
            "printed_mean_name_index": DAY_CYCLE.index(
                printed["mean_cycle_name_literal"]
            ),
            "printed_mean_name_matches_index": printed["mean_cycle_name_literal"]
            == DAY_CYCLE[printed["mean_cycle_index_literal"]],
        },
        "plus_eleven_label_comparison": {
            "source_step_label": printed["eleventh_label_literal"],
            "cycle_units": plus11["calculated_mean"]["cycle_units"],
            "table_month_key": [
                plus11["year"],
                plus11["month"],
                plus11["is_leap_month"],
            ],
            "source_months_relabelled": False,
        },
        "all_fifteen_row_checks": rows,
        "threshold_unit_checks": thresholds,
        "conditional_unit_model_reference": {
            "source_title": unit_bundle["source_title"],
            "source_url": unit_bundle["source_url"],
            "source_pdf_sha256": unit_bundle["source_sha256"],
            "source_bundle_sha256": unit_source.sha256,
            "source_models": models,
            "unit_denominators_are_selected_2015_models": True,
            "unit_denominators_printed_in_selected_2024_captions": False,
            "historical_day_boundary_certified": False,
        },
    }


def futen_arithmetic_lines(reference: dict[str, Any]) -> list[str]:
    chain = reference["calculated_chain"]
    return [
        "符天历复原另核竹迫忍2024年讲义第52–56页：所选1163年十一月至1164年十二月共15行，"
        "包括普通十一月和闰十一月，逐行经朔及印出日月订正之和均另列。订正值取自该研究表，"
        "没有复原日月订正函数，也没有独立读录其所引1164年原文书。",
        f"该例雨水干支量{chain['rain_cycle']['cycle_units']}，閏餘o为"
        f"{chain['unadjusted_run_remainder']}、加閏應后的閏餘为{chain['adjusted_run_remainder']}，"
        f"入转量{chain['anomaly_units']}采用未加閏應的閏餘o192502，依原页第7式"
        "(1840834800−192502＋32568)除275544取余；不能把此处閏餘o与200759互换。"
        "经朔须在含氣應398535的干支坐标中减閏餘，得232576，"
        "照未列氣應的字面式算则为434041。原页433335分/1000与一日10000分分别保留，"
        "不直接照抄分母；原印23壬午与甲子起零的23丁亥不合，壬午为18，未改写原印。",
        "同页加11朔望月得480942，在紧接的表中是闰十一月；普通十一月为185636。"
        "表明示尚未退朔改月，不能把两月合并、把经朔当颁历朔日或据此裁定闰小月补配先后。"
        "冬至至经朔式精确为1223948/3分，原印407982分，差2/3分保留，不把显示取整直接判为抄本错误。",
        "进朔限单位也须校核：该讲义宣明历栏印18时、6400分；按一日8400分，"
        "6400分是128/7名义小时，18时应为6300分，相差100分。符天历栏7500/10000则为18名义小时。"
        "8400与10000是一日单位，来自既有2015研究所列两模型，并非2024这两处限值图注印出的分母；"
        "保留两栏印值及差额，不据现代24小时换算确定实际历史钟时，亦未选择6400或6300替代历法。"
        "这些算术与标签核验没有确定T1299平明、桧尾半日、闰小月优先、历史绝对日期或现实预测效力；"
        "本次输入日期和主宿未由此改变。",
    ]
