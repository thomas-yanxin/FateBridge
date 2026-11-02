"""Recompute a named Dayan model, keeping it separate from the issued calendar.

The fixed reference tables are credited to Takashi SUGA's MIT-licensed when_exe
implementation of named research. The original license is included in data/.
All arithmetic here uses exact rational values and explicit rounding stages.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_dayan_reconstruction.json"
CANONICAL_SHA256 = "ec68367411c7de35c7dc67d4a6fe2ffc6b3d574e88ecbac071047bfe2edffb34"
DAY_CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
    for i in range(60)
)


def _ratio(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _nearest(value: Fraction) -> int:
    """Round half toward positive infinity, including negative corrections."""
    return (value + Fraction(1, 2)) // 1


def _captured_model() -> tuple[dict[str, Any], str]:
    loaded = load_source(SOURCE)
    bundle = loaded.data
    canonical = json.dumps(
        bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(canonical).hexdigest() != CANONICAL_SHA256:
        raise ValueError("大衍复算的常数、系数或方法来源已改变，须重新核验")
    return bundle, loaded.sha256


def reconstruction_scope_reference() -> dict[str, Any]:
    from fatebridge.core.sukuyo_dayan_advance import research_scope

    bundle, digest = _captured_model()
    return {
        "ruleset_id": bundle["id"],
        "source_bundle_sha256": digest,
        "reference_scope": bundle["all_month_reference_scope"],
        "computational_reference": bundle["computational_reference"],
        "primary_research": bundle["primary_research"],
        "applies_to_every_input_or_calendar": False,
        "research_scope_delivery_round": 89,
        "fixed_host_research_scope": research_scope(),
    }


def reconstruction_scope_lines(
    reference: dict[str, Any], calendar: dict[str, Any]
) -> list[str]:
    scope = reference["reference_scope"]
    current = (calendar.get("calendar_reference") or {}).get(
        "dayan_nominal_new_moon_model"
    )
    lines = [
        f"大衍名义模型的实现对照范围为既有宿主{scope['declared_lunar_year_begin']}—"
        f"{scope['declared_lunar_year_end']}农历年共{scope['reference_corpus_months']}个月；"
        f"2022进朔研究表另选{scope['printed_2022_selected_rows']}行，未列选行的范围内月份仍另列模型结果。"
        "1212是数值实现对照的月份数，327是具名研究表行数；以宿主月首选择经朔的对照"
        "没有独立验证月名、置闰、颁历或古代钟界，也不计现实预测样本。"
        "系数取自固定提交的when_exe实现，Takashi SUGA署名据同提交gemspec作者字段另列；"
        "这不是本轮取得原典并逐字校勘系数。",
        (
            f"本次按声明的农历{current['declared_lunar_year_used_for_source_policy']}年另列大衍A／D模型，"
            "当前配宿及作者进朔方向仍各自保留。"
            if current is not None
            else "本次输入没有应用该大衍名义模型，历日和配宿沿用本次已声明的宿主与档案；"
            "该模型的1212月实现对照不能移作本次所选历日或现实效力的验收。"
        ),
    ]
    if (
        "research_scope_delivery_round" in reference
        or "fixed_host_research_scope" in reference
    ):
        from fatebridge.core.sukuyo_dayan_advance import research_scope

        comparison = reference.get("fixed_host_research_scope")
        if (
            reference.get("research_scope_delivery_round") != 89
            or comparison != research_scope()
        ):
            raise ValueError("全表研究方向、不利结果或未知行与具名来源不一致")
        unknown = "、".join(str(n) for n in comparison["unknown_direction_rows"])
        lines.append(
            f"既有具名研究表{comparison['complete_selected_research_rows']}行与固定NAOJ月首的方向对照，"
            f"仍保留{len(comparison['same_direction_rows'])}相合、"
            f"{len(comparison['different_direction_rows'])}不同、"
            f"{len(comparison['unknown_direction_rows'])}未知；"
            f"未知行号为{unknown}，作者横杠未补成不进。"
            "这是完整研究选表的固定参考，与本次输入是否应用大衍模型、是否列有本月选行分别交付；"
            "不把它应用成现代本次历日、不改写已有宿主或配宿。"
            "这些行不是独立古代观察或现实样本，也未完成全部原记录校勘、"
            "裁定古代钟界、原典半日或闰小月补配先后。"
        )
    return lines


def _solar(
    elapsed_days: Fraction, rows: list[dict[str, Any]], year: Fraction, units: int
) -> dict[str, Any]:
    elapsed = elapsed_days % year
    for index, row in enumerate(rows):
        following = rows[(index + 1) % len(rows)]
        width = year / len(rows) + Fraction(
            following["ahead_behind_units"] - row["ahead_behind_units"], units
        )
        if elapsed <= width:
            break
        elapsed -= width
    else:
        raise ValueError("大衍太阳订正未能定位具名区间")
    days = elapsed // 1
    remainder = int((elapsed - days) * units)
    b = Fraction(row["initial_rate_decimal"])
    c = Fraction(row["daily_difference_decimal"])
    rate = int(b + c * days)
    accumulated = int(
        row["correction_at_term_units"] + b * days + c * days * (days - 1) / 2
    )
    fraction = Fraction(rate * remainder, units)
    return {
        "solar_term": row["solar_term"],
        "coefficient_row": dict(row),
        "elapsed_days_in_segment": _ratio(elapsed),
        "whole_days": days,
        "fractional_day_units_truncated": remainder,
        "rate_truncated_toward_zero": rate,
        "accumulated_truncated_toward_zero": accumulated,
        "fractional_correction_exact": _ratio(fraction),
        "correction_units": accumulated + _nearest(fraction),
    }


def _lunar(elapsed_units: Fraction, rows: list[dict[str, Any]]) -> dict[str, Any]:
    start = accumulated = 0
    for index, row in enumerate(rows):
        end = start + row["segment_width_units"]
        if elapsed_units <= end:
            within = elapsed_units - start
            fractional = (
                Fraction(row["segment_increment_units"])
                * within
                / row["segment_width_units"]
            )
            return {
                "segment_index": index,
                "coefficient_row": dict(row),
                "anomaly_units": _ratio(elapsed_units),
                "elapsed_units_in_segment": _ratio(within),
                "accumulated_at_segment_start": accumulated,
                "fractional_correction_exact": _ratio(fractional),
                "correction_units": accumulated + _nearest(fractional),
            }
        start = end
        accumulated += row["segment_increment_units"]
    raise ValueError("大衍月行订正未能定位具名区间")


def reconstruct_new_moon(
    host_month_start_ordinal: int, lunar_year: int
) -> dict[str, Any]:
    """Select one mean lunation from the supplied host month, then compute A/D.

    Host month names, intercalation and absolute dates are selectors here, not
    independently verified outputs. A three-day bound cannot be relaxed by
    selecting whichever result matches a printed remainder or advance decision.
    """
    if type(host_month_start_ordinal) is not int or type(lunar_year) is not int:
        raise ValueError("大衍复算须明确宿主月首序数日和农历年份整数")
    bundle, digest = _captured_model()
    constants = bundle["constants"]
    units = constants["day_units"]
    epoch = Fraction(**constants["epoch_julian_day"])
    year_length = Fraction(constants["year_units"], units)
    lunation = Fraction(constants["lunation_units"], units)
    anomaly_period = Fraction(**constants["anomalistic_month_units"]) / units
    host_jdn = host_month_start_ordinal + 1721425
    epoch_count = _nearest((host_jdn - Fraction(1, 2) - epoch) / lunation)
    mean = epoch + epoch_count * lunation
    distance = mean + Fraction(1, 2) - host_jdn
    if abs(distance) > constants["host_selector_max_nominal_days"]:
        raise ValueError("宿主月首距最近经朔超出固定三日选择界限，未猜换其他朔")
    elapsed = mean - epoch
    solar = _solar(elapsed, bundle["solar_rows"], year_length, units)
    a = _lunar((elapsed % anomaly_period) * units, bundle["lunar_rows"])
    d = _lunar(
        ((elapsed + Fraction(solar["correction_units"], units)) % anomaly_period)
        * units,
        bundle["lunar_rows"],
    )

    def cycle(moment: Fraction) -> dict[str, Any]:
        coordinate = moment + Fraction(1, 2)
        day = coordinate // 1
        index = (day + constants["cycle_index_at_JDN0"]) % 60
        return {
            "nominal_midnight_JDN_coordinate": day,
            "cycle_index": index,
            "ganzhi": DAY_CYCLE[index],
            "remainder_units": _ratio((coordinate - day) * units),
        }

    selected = "D" if 793 <= lunar_year <= 819 else "A"
    return {
        "ruleset_id": bundle["id"],
        "source_bundle_sha256": digest,
        "primary_research": bundle["primary_research"],
        "computational_reference": bundle["computational_reference"],
        "policy": bundle["policy"],
        "host_month_start_ordinal_used_as_selector": host_month_start_ordinal,
        "declared_lunar_year_used_for_source_policy": lunar_year,
        "mean_epoch_lunation_index": epoch_count,
        "mean_nominal_julian_day": _ratio(mean),
        "host_selector_distance_nominal_days": _ratio(distance),
        "mean_cycle": cycle(mean),
        "solar_step": solar,
        "lunar_steps": {"A": a, "D": d},
        "models": {
            name: {
                "solar_correction_units": solar["correction_units"],
                "lunar_correction_units": lunar["correction_units"],
                "total_correction_units": solar["correction_units"]
                + lunar["correction_units"],
                "pre_advance_cycle": cycle(
                    mean
                    + Fraction(
                        solar["correction_units"] + lunar["correction_units"], units
                    )
                ),
            }
            for name, lunar in [("A", a), ("D", d)]
        },
        "source_policy_selected_model": selected,
        "within_studied_lunar_year_range": 764 <= lunar_year <= 861,
        "physical_new_moon_or_UTC_TT_recomputed": False,
        "host_calendar_or_month_labels_independently_verified": False,
        "advance_direction_determined": False,
        "current_calendar_or_mansion_changed": False,
        "historical_daybreak_hinoo_half_or_priority_established": False,
        "new_independent_historical_observations": 0,
        "real_samples": 0,
    }


def reconstruction_lines(result: dict[str, Any]) -> list[str]:
    selected = result["source_policy_selected_model"]
    models = result["models"]

    def describe(name: str) -> str:
        model = models[name]
        cycle = model["pre_advance_cycle"]
        value = cycle["remainder_units"]
        remainder = (
            str(value["numerator"])
            if value["denominator"] == 1
            else f"{value['numerator']}/{value['denominator']}"
        )
        return (
            f"{name}模型太阳订正{model['solar_correction_units']}、"
            f"月行订正{model['lunar_correction_units']}，进朔前定朔"
            f"{cycle['ganzhi']}（大余{cycle['cycle_index']}，小余{remainder}）"
        )

    return [
        "本月另作大衍名义定朔复算，一日3040分："
        + describe("A")
        + "；"
        + describe("D")
        + f"。按2022研究声明，793—819农历年取D，其余取A，本次农历"
        f"{result['declared_lunar_year_used_for_source_policy']}年，本月取{selected}；"
        "不是按哪一个更贴近原表或现用历日来择式。",
        "A在经朔处取太阳和比例月行订正，D先加太阳订正再取比例月行订正；"
        "各项取整及所用太阳、月行区间另列。系数来自固定提交的Takashi SUGA实现，"
        "结合具名竹迫研究；并非新取得原典每字校勘或另一组独立古代观测。"
        "本次以既有宿主月首选择三日界内最近经朔，因此没有独立验证月份、置闰或绝对历日。"
        "名义JDN坐标未赋UTC／TT或历史钟界，未决定进朔、改写主宿、裁定桧尾半日和闰小月先后，"
        "也没有消除研究表的52项分歧及1项未知或证明现实效力。",
    ]
