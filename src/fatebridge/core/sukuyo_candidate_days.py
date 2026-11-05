"""Conditional day evidence for already enumerated mansion alternatives.

The original calendar and primary evidence remain unresolved. These branches
apply the same documentary selectors under each named condition, without
choosing a clock, reconstruction, candidate, or real-world action.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional, Sequence


def personal_day_evidence(
    natal_mansion: Optional[str], mansion: Optional[str]
) -> Optional[dict[str, Any]]:
    from fatebridge.core.sukuyo_relations import TEXT_URL, relation_between_su27

    if natal_mansion is not None:
        # Validate even when the target day's mansion remains unresolved.
        relation_between_su27(natal_mansion, natal_mansion)
    relative = (
        relation_between_su27(natal_mansion, mansion)
        if natal_mansion and mansion
        else None
    )
    personal_day = None
    if relative:
        from fatebridge.core.sukuyo_sanjiu_days import personal_day_witnesses

        label = relative["relation"]
        upper = {
            "命": "原文不宜举动百事。",
            "胎": "原文不宜举动百事。",
            "業": "上卷称所作皆吉祥。",
            "衰": "原文不宜远行、迁移、买卖等。",
            "危": "宜结交婚姻、欢会宴聚；另称不宜远行等，按事项分别保留。",
            "壊": "原文不宜远行、迁移、买卖等；不输出伤害性操作。",
            "安": "原文宜移动远行、修园宅卧具。",
            "成": "保留修学问道的文献含义。",
            "友": "原文宜结交朋友。",
            "親": "原文宜结交朋友。",
            "栄": "上卷本段未单列荣日事项；不拿结交判断替代择日条文。",
        }
        personal_day = {
            "relation": relative,
            "source_day_evidence": personal_day_witnesses(label),
            "upper_volume": {
                "meaning": upper[label],
                "locator": "T21n1299_p0391b19-25",
                "source": TEXT_URL,
            },
            "textual_conflict": label in {"業", "危"},
            "lower_volume_variant": (
                {
                    "meaning": "下卷称业宿日所作善恶亦不成就，与上卷不同。",
                    "locator": "T21n1299_p0398a07-08",
                    "source": TEXT_URL,
                }
                if label == "業"
                else (
                    {
                        "meaning": "下卷0398a02称危日宜定婚姻，0398a09-10又称危坏日不宜婚姻，保留两条。",
                        "locator": "T21n1299_p0398a02; p0398a09-10",
                        "source": TEXT_URL,
                    }
                    if label == "危"
                    else None
                )
            ),
            "scope": "文献择日条文；不从原文标签推断现实必然吉凶、疾病或灾祸。",
        }
    return personal_day


def mansion_nature(mansion: Optional[str]) -> Optional[str]:
    groups = {
        "安重": "毕翼斗壁",
        "和善": "觜角房奎",
        "毒害": "参柳心尾",
        "急速": "鬼轸胃娄",
        "猛恶": "星张箕室",
        "轻燥": "井亢女虚危",
        "刚柔": "昴氐",
    }
    return (
        next((key for key, values in groups.items() if mansion in values), None)
        if mansion
        else None
    )


def _conditions(calendar: dict[str, Any], name: str) -> list[dict[str, Any]]:
    profile = calendar["profile_calculation"]
    assignment = profile.get("short_month_assignment")
    selected = calendar.get("calendar_day_part")
    conditions = []
    precedence = assignment.get("leap_short_month_precedence") if assignment else None
    if precedence:
        for branch in precedence["reconstruction_calculations"]:
            for half, key in (
                ("first_half", "first_half_calculation"),
                ("second_half", "second_half_calculation"),
            ):
                if selected not in (None, half):
                    continue
                calculation = branch[key]
                if calculation["direct_mansion"] == name:
                    conditions.append(
                        {
                            "calendar_day_part": half,
                            "reconstruction_id": branch["id"],
                            "calculation": deepcopy(calculation),
                        }
                    )
    elif assignment:
        for slot in assignment["slots"]:
            if (
                selected in (None, slot["day_part"])
                and name in slot["candidate_mansions"]
            ):
                conditions.append(
                    {
                        "calendar_day_part": slot["day_part"],
                        "reconstruction_id": None,
                        "assignment_origin": slot["origin"],
                    }
                )
    else:
        conditions.append(
            {
                "calendar_day_part": selected,
                "reconstruction_id": None,
                "assignment_origin": "enumerated_profile_candidate_without_slot_binding",
            }
        )
    return conditions


def candidate_mansion_days(
    day: dict[str, Any],
    natal_mansion: Optional[str],
    activity: Optional[str],
    activity_details: Optional[Sequence[str]],
) -> list[dict[str, Any]]:
    from fatebridge.core.sukuyo_activities import assess_activity
    from fatebridge.core.sukuyo_clothing import clothing_reference
    from fatebridge.core.sukuyo_directions import travel_direction_evidence
    from fatebridge.core.sukuyo_lower import lower_mansion_evidence
    from fatebridge.core.sukuyo_lower_methods import lower_methods_evidence
    from fatebridge.core.sukuyo_special_days import special_day_evidence

    calendar = day["calendar"]
    if day["day_mansion"] is not None:
        return []
    rows = []
    for name in calendar.get("candidate_su27s", []):
        nature = mansion_nature(name)
        special = special_day_evidence(
            name,
            day["weekday"]["index_sunday_zero"],
            [],
            weekday_basis=day["weekday"]["basis"],
        )
        facts = {
            "day_mansion": name,
            "personal_day": personal_day_evidence(natal_mansion, name),
            "nature": nature,
            "special_day_labels": special["primary"]["matched_labels"],
            "special_day_evidence": special,
            "lower_mansion_day": lower_mansion_evidence(name),
            "lower_methods": lower_methods_evidence(
                name,
                day["weekday"]["luminary"],
                nature,
                weekday_basis=day["weekday"]["basis"],
            ),
            "directional_travel": travel_direction_evidence(name, []),
        }
        if activity == "clothing":
            # A per-name documentary lookup, not a rewritten birth calendar.
            facts["clothing_reference"] = clothing_reference({"natal_su27": name})
        assessment = assess_activity(
            {**facts, "weekday": day["weekday"], "calendar_day": day["calendar_day"]},
            activity,
            activity_details,
        )
        rows.append(
            {
                "status": "conditional_mansion_evidence",
                "calendar_date": calendar["calendar_date"],
                "conditions": _conditions(calendar, name),
                "candidate_set_complete_under_declared_reconstructions": calendar[
                    "profile_calculation"
                ]["candidate_set_complete_under_declared_reconstructions"],
                "applied_to_primary": False,
                **facts,
                "activity_assessment": assessment,
                "scope": "仅在该候选宿条件下查原典；事项汇总只属于本条件分支，未代入主结果。民用日期、七曜及入月日沿用父结果；不确定古代钟界、半日或补配先后，不代表现实成功概率。",
            }
        )
    return rows
