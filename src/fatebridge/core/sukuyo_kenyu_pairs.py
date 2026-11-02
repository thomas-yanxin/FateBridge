"""Keep a developmental component model separate from literal period tables."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_profiles import source_bundle, source_digest
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_kenyu_ndl_pairs.json"
LUMINARIES = "日月火水木金土"


def conditional_pair_comparison(
    calendar: dict[str, Any],
    lookups: list[dict[str, Any]],
    selected_lookup: dict[str, Any] | None,
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    source = loaded.data
    host = calendar.get("profile_calculation", {}).get("host_calculation")
    result: dict[str, Any] = {
        "source_reference": {**source, "source_bundle_sha256": loaded.sha256},
        "status": "not_evaluated_missing_or_inconsistent_fullmoon27_basis",
        "baseline_fullmoon27_calculation": None,
        "conditional_month_start_comparisons": [],
        "selected_civil_condition_comparison": None,
        "day_luminary_basis": "explicit_first_day_label_plus_day_minus_one_modulo_seven",
        "selected_profile_mansion_or_hinoo_half_used": False,
        "printed_unlisted_membership_remains_unknown": True,
        "pair_false_means_certain_no_lingbi": False,
        "authenticated_original_combination_formula": False,
        "physical_witness_identity_established": False,
        "ancient_day_boundary_established": False,
        "leap_month_start_ruler_inheritance_established": False,
        "t1299_planetary_condition_evaluated": False,
        "applied_to_primary_or_activities": False,
    }
    if not isinstance(host, dict):
        return result
    month, day = calendar.get("lunar_month"), calendar.get("lunar_day")
    if (
        type(month) is not int
        or not 1 <= month <= 12
        or type(day) is not int
        or not 1 <= day <= 30
        or host.get("lunar_month") != month
        or host.get("lunar_day") != day
        or host.get("ruleset_id") != source_bundle()["id"]
        or host.get("source_bundle_sha256") != source_digest()
        or host.get("methods_agree") is not True
        or host.get("direct_mansion") != host.get("shortcut_mansion")
        or not isinstance(host.get("direct_mansion"), str)
        or not lookups
    ):
        return result
    translation = str.maketrans(source["normalization"])
    mansion = host["direct_mansion"].translate(translation)
    memberships = {
        ruler: {name.translate(translation) for name in names}
        for ruler, names in source["memberships"].items()
    }
    if mansion not in set().union(*memberships.values()):
        return result
    comparisons = []
    # Consume the existing literal lookups, without recalculating the mansion,
    # inventing missing intervals, or using the selected Hinoo candidate.
    for lookup in lookups:
        first = lookup["condition_month_start_luminary"]
        if (
            first not in LUMINARIES
            or len(first) != 1
            or lookup["condition_lunar_month"] != month
            or lookup["condition_lunar_day"] != day
        ):
            raise ValueError("曜宿对照与月表条件不一致")
        day_ruler = LUMINARIES[(LUMINARIES.index(first) + day - 1) % 7]
        pair_match = mansion in memberships[day_ruler]
        printed = lookup["membership_in_printed_interval"]
        comparison = (
            ("unlisted_pair_model_true" if pair_match else "unlisted_pair_model_false")
            if printed is None
            else (
                ("listed_agree_true" if pair_match else "listed_agree_false")
                if pair_match == printed
                else (
                    "listed_disagree_model_true"
                    if pair_match
                    else "listed_disagree_model_false"
                )
            )
        )
        comparisons.append(
            {
                **deepcopy(lookup),
                "hypothetical_day_luminary": day_ruler,
                "baseline_fullmoon27_mansion": mansion,
                "conditional_pair_match": pair_match,
                "comparison": comparison,
            }
        )
    result.update(
        status="conditional_component_model",
        baseline_fullmoon27_calculation=deepcopy(host),
        conditional_month_start_comparisons=comparisons,
        selected_civil_condition_comparison=(
            next(
                row
                for row in comparisons
                if row["condition_month_start_luminary"]
                == selected_lookup["condition_month_start_luminary"]
            )
            if selected_lookup is not None
            else None
        ),
    )
    return result


def pair_comparison_reading(reference: dict[str, Any]) -> str:
    if reference["status"] != "conditional_component_model":
        return "缺少可核对的T1299望宿基准，未组合曜宿小表，也未用已选主宿补算。"
    selected = reference["selected_civil_condition_comparison"]
    rows = (
        [selected]
        if selected is not None
        else reference["conditional_month_start_comparisons"]
    )
    branches = []
    for row in rows:
        printed = row["membership_in_printed_interval"]
        table = (
            "月表未列、判断未定"
            if printed is None
            else ("月表在内" if printed else "月表在外")
        )
        branches.append(
            f"若朔为{row['condition_month_start_luminary']}曜，则本日为"
            f"{row['hypothetical_day_luminary']}曜、基准{row['baseline_fullmoon27_mansion']}宿，"
            + ("组合命中" if row["conditional_pair_match"] else "组合不命中")
            + f"，{table}"
        )
    return (
        "另以国立国会图书馆特2-721帧6的27个可读曜宿成员作条件组合对照："
        + "；".join(branches)
        + "。此开发组合沿用未补配的T1299望宿基准与假定朔曜的逐日七曜，"
        "未改用桧尾半日或已选主宿；未列月表仍未定，组合命中或不命中均不等于实际陵逼结论。"
        "两件实物见证的版本关系、原书组合公式、古代日界及闰月朔曜继承尚未认证；"
        "没有补入月曜第四宿，也未覆盖主宿、事项或现实预测。"
    )
