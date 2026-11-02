"""Literal monthly period conditions from one named print, not sky events."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_kenyu_pairs import (
    conditional_pair_comparison,
    pair_comparison_reading,
)
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_weekday import civil_weekday

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_kenyu_selected_lingbi.json"
LUMINARIES = "日月火水木金土"


def _lookup(
    source: dict[str, Any], month: int, month_start_luminary: str, day: int
) -> dict[str, Any]:
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("陵逼表只接受月序整数1至12")
    if month_start_luminary not in LUMINARIES or len(month_start_luminary) != 1:
        raise ValueError("陵逼表朔曜须为日月火水木金土之一")
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("陵逼表只接受实际入月日整数1至30")
    rows = [
        row
        for row in source["printed_rows"]
        if row["month"] == month and row["month_start_luminary"] == month_start_luminary
    ]
    return {
        "condition_lunar_month": month,
        "condition_month_start_luminary": month_start_luminary,
        "condition_lunar_day": day,
        "matching_intervals": deepcopy(rows),
        "membership_in_printed_interval": (
            any(row["start_day"] <= day <= row["end_day"] for row in rows)
            if rows
            else None
        ),
        "unlisted_condition_means_no_lingbi": False,
    }


def lookup_lingbi_interval(
    month: int, month_start_luminary: str, day: int
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    return {
        "ruleset_id": loaded.data["id"],
        "source_bundle_sha256": loaded.sha256,
        **_lookup(loaded.data, month, month_start_luminary, day),
    }


def conditional_lingbi_reference(
    calendar: dict[str, Any], personal_relation: str | None
) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    source = loaded.data
    missing = [
        field
        for field in ("lunar_month", "is_leap_month")
        if calendar.get(field) is None
    ]
    if missing:
        # Existing callers may supply only a mansion and a day number. Do not
        # infer a month/leap policy or interrupt those independent facts.
        return {
            **source,
            "source_bundle_sha256": loaded.sha256,
            "lookup_status": "not_evaluated_missing_calendar_context",
            "missing_context_fields": missing,
            "civil_month_start_reference": None,
            "selected_civil_month_start_lookup": None,
            "conditional_month_start_lookups": [],
            "weekday_mansion_comparison": conditional_pair_comparison(
                calendar, [], None
            ),
            "personal_relation": personal_relation,
            "selected_personal_condition": next(
                (
                    deepcopy(row)
                    for row in source["personal_conditions"]
                    if personal_relation in row["relations"]
                ),
                None,
            ),
            "urgent_action_established": None,
            "ancient_day_boundary_established": False,
            "t1299_planetary_condition_evaluated": False,
            "applied_to_primary_or_activities": False,
        }
    month, day = calendar["lunar_month"], calendar["lunar_day"]
    lookups = [_lookup(source, month, ruler, day) for ruler in LUMINARIES]
    try:
        month_start_date = date.fromisoformat(calendar["calendar_date"]) - timedelta(
            days=day - 1
        )
        civil_reference = {
            "date": month_start_date.isoformat(),
            **civil_weekday(
                month_start_date.isoformat(), calendar["calendar_timezone"]
            ),
            "origin": "derived_host_month_start_not_observed_birth_date",
        }
    except OverflowError:
        civil_reference = None
    # The short note does not specify which first-day ruler is inherited by a
    # repeated leap month. Keep all seven source conditions, not a chosen rule.
    selected = (
        _lookup(source, month, civil_reference["luminary"], day)
        if civil_reference is not None and not calendar["is_leap_month"]
        else None
    )
    return {
        **source,
        "source_bundle_sha256": loaded.sha256,
        "civil_month_start_reference": civil_reference,
        "selected_civil_month_start_lookup": selected,
        "conditional_month_start_lookups": lookups,
        "weekday_mansion_comparison": conditional_pair_comparison(
            calendar, lookups, selected
        ),
        "personal_relation": personal_relation,
        "selected_personal_condition": next(
            (
                deepcopy(row)
                for row in source["personal_conditions"]
                if personal_relation in row["relations"]
            ),
            None,
        ),
        "urgent_action_established": None,
        "ancient_day_boundary_established": False,
        "t1299_planetary_condition_evaluated": False,
        "applied_to_primary_or_activities": False,
    }


def lingbi_reading_lines(reference: dict[str, Any]) -> list[str]:
    civil = reference["civil_month_start_reference"]
    selected = reference["selected_civil_month_start_lookup"]
    if reference.get("missing_context_fields"):
        selection = (
            "缺少"
            + "、".join(reference["missing_context_fields"])
            + "，未查询本表；没有补推月序或闰月身份。"
        )
    elif civil is None:
        selection = "宿主月首超出可表示日期，未补定朔曜。"
    elif selected is None:
        branches = []
        for lookup in reference["conditional_month_start_lookups"]:
            intervals = lookup["matching_intervals"]
            branches.append(
                f"若月首{lookup['condition_month_start_luminary']}曜，"
                + (
                    "表列"
                    + "、".join(row["literal"] for row in intervals)
                    + (
                        "，本日在内"
                        if lookup["membership_in_printed_interval"]
                        else "，本日在外"
                    )
                    if intervals
                    else "本月未列，成员判断未定"
                )
            )
        selection = (
            f"宿主民用月首{civil['date']}为{civil['luminary']}曜；"
            "本次为闰月，旁注潤月全如本月未说明继承哪一个朔曜，七种条件均保留，未选唯一表值。"
            + "；".join(branches)
            + "。未列与明确在区间外分别保留，均未据此确定实际无陵逼。"
        )
    else:
        rows = selected["matching_intervals"]
        selection = f"以宿主{civil['basis']}月首{civil['date']}的{civil['luminary']}曜为月首曜条件，" + (
            "表列"
            + "、".join(row["literal"] for row in rows)
            + (
                "，当前入月日在所列区间内。"
                if selected["membership_in_printed_interval"]
                else "，当前入月日在所列区间外。"
            )
            if rows
            else "所选月份未列这一朔曜；未列不能解释为确定无陵逼。"
        )
    return [
        "堅雄《宿曜經撮要》名古屋大学148.8-Ke、NIJL100159236帧8右页另有23行陵逼表。"
        + selection
        + "这是具名印本的条件查表，不是已经计算实际天体陵犯守逼。"
        "T1299下卷0398a18–26另要求知五星及日月实际在何宿；未用本表、民用午夜、任意角距或现代天文宿名代替该条件。",
        "帧7左页柱记宿曜經撮要序文之次入紙，末有取意，不能全当经文逐字引录或已认证传承。"
        "此补纸只在陵逼之間的语境下讨论三九；尤其若有急事欲作之者，才称可用衰危坏，"
        "同段列荣成友亲安五宿不可取用，命胎及业另有不利条文。"
        "未确认本次实际陵逼或急事，也不把这些条文改作平日一般规则、个体灾祸断言或覆盖本次事项。"
        "右表潤月全如本月与左页潤月朔宿全如本月分别保留，均未裁定T2465补配先后；"
        "八十六年唯六年无陵逼是来源自述，未复算，不增加现实验证样本。",
        pair_comparison_reading(reference["weekday_mansion_comparison"]),
    ]
