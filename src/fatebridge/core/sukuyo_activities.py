"""Source-located activity evidence without collapsing contradictory clauses."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, Sequence

from fatebridge.core.sukuyo_calendar_text import source_bundle as day_source_bundle
from fatebridge.core.sukuyo_calendar_text import source_digest as day_source_digest
from fatebridge.core.sukuyo_clothing import SOURCE as CLOTHING_SOURCE
from fatebridge.core.sukuyo_clothing import source_bundle as clothing_source_bundle
from fatebridge.core.sukuyo_directions import source_bundle as direction_source_bundle
from fatebridge.core.sukuyo_directions import source_digest as direction_source_digest
from fatebridge.core.sukuyo_documentary import with_text_layers
from fatebridge.core.sukuyo_lower import (
    activity_detail_closure,
)
from fatebridge.core.sukuyo_lower import source_bundle as lower_source_bundle
from fatebridge.core.sukuyo_lower import source_digest as lower_source_digest
from fatebridge.core.sukuyo_lower import validate_activity_details
from fatebridge.core.sukuyo_lower_methods import SOURCE as METHOD_SOURCE
from fatebridge.core.sukuyo_lower_methods import source_bundle as method_source_bundle
from fatebridge.core.sukuyo_sanjiu_days import SOURCE as SANJIU_SOURCE
from fatebridge.core.sukuyo_sanjiu_days import source_bundle as sanjiu_source_bundle
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_special_days import source_bundle as special_source_bundle
from fatebridge.core.sukuyo_special_days import source_digest as special_source_digest

ACTIVITIES = (
    "social",
    "marriage",
    "travel",
    "relocation",
    "commerce",
    "study",
    "clothing",
)
SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_activities.json"


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def assess_activity(
    day: dict[str, Any],
    activity: Optional[str],
    activity_details: Optional[Sequence[str]] = None,
) -> Optional[dict[str, Any]]:
    validate_activity_details(
        activity, activity_details if activity_details is not None else []
    )
    details = list(dict.fromkeys(activity_details or []))
    effective_details, detail_inferences = activity_detail_closure(details)
    if activity is None:
        return None
    if activity not in ACTIVITIES:
        raise ValueError(
            "activity仅支持social/marriage/travel/relocation/commerce/study/clothing"
        )
    relative = (day.get("personal_day") or {}).get("relation")
    lower_special = next(
        w
        for w in day["special_day_evidence"]["comparisons"]
        if w["witness"] == "lower_taisho"
    )
    unresolved_special = (
        lower_special["unresolved_rows"] if day.get("day_mansion") else []
    )
    selectors = {
        "sanjiu": [relative["relation"]] if relative else [],
        "nature": [day["nature"]] if day.get("nature") else [],
        "weekday": [day["weekday"]["luminary"]],
        "special_day": day["special_day_labels"],
        "named_day": [day["calendar_day"]["lunar_day"]],
        "lower_mansion": [day["day_mansion"]] if day.get("day_mansion") else [],
        "lower_nature": (
            [day["lower_methods"]["nature"]["selected_group"]["name"]]
            if day["lower_methods"]["nature"]["selected_group"]
            else []
        ),
        "lower_weekday": [day["weekday"]["luminary"]],
        "travel_direction": [day["day_mansion"]] if day.get("day_mansion") else [],
        "lower_special_day": [
            *lower_special["matched_labels"],
            *[r["label"] for r in unresolved_special],
        ],
    }
    if activity == "clothing":
        reference = day["clothing_reference"]
        selectors["clothing_chapter"] = (
            [reference["primary_assessment"]] if reference["primary_assessment"] else []
        )
        selectors["clothing_upper_mansion"] = (
            [day["day_mansion"]] if day.get("day_mansion") else []
        )
    bundle = source_bundle()
    topic_matches = [
        {**with_text_layers(rule), "source_url": bundle["source_url"]}
        for rule in [
            *bundle["rules"],
            *day_source_bundle()["activity_rules"],
            *lower_source_bundle()["rules"],
            *method_source_bundle()["rules"],
            *direction_source_bundle()["rules"],
            *special_source_bundle()["activity_rules"],
            *sanjiu_source_bundle()["activity_rules"],
            *(clothing_source_bundle()["rules"] if activity == "clothing" else []),
        ]
        if activity in rule["activities"]
        and set(rule["selectors"]).intersection(selectors[rule["layer"]])
    ]
    # Some legacy rules span several topics. Qualify only the activity whose
    # source wording is narrower, preserving its other topic mappings.
    for index, rule in enumerate(topic_matches):
        if rule["layer"] == "lower_special_day" and not set(
            rule["selectors"]
        ).intersection(lower_special["matched_labels"]):
            literal = "、".join(
                r["literal_mansion"]
                for r in unresolved_special
                if r["label"] in rule["selectors"]
            )
            rule = {
                **rule,
                "applicability": "activity_detail_required",
                "requires_textual_review": True,
                "activity_detail_any_of": [],
                "topic_condition": f"下卷大正宿字{literal}未识别，未与输入日宿匹配；不以明本改字补定，不代入已匹配宜忌。",
            }
            topic_matches[index] = rule
        condition = rule.get("activity_conditions", {}).get(activity)
        if condition:
            topic_matches[index] = {
                **rule,
                "applicability": "activity_detail_required",
                "activity_detail_any_of": condition.get("any_of", []),
                "activity_detail_all_of": condition.get("all_of", []),
                "topic_condition": condition["condition"],
            }
    matches = []
    conditional = []
    for rule in topic_matches:
        if rule.get("applicability") != "activity_detail_required":
            matches.append(rule)
            continue
        any_of = rule.get("activity_detail_any_of", [])
        all_of = rule.get("activity_detail_all_of", [])
        matched_details = [d for d in effective_details if d in [*any_of, *all_of]]
        any_satisfied = not any_of or bool(set(effective_details).intersection(any_of))
        missing_all = [d for d in all_of if d not in effective_details]
        reading_resolved = not rule.get("requires_textual_review")
        applies = (
            bool(any_of or all_of)
            and any_satisfied
            and not missing_all
            and reading_resolved
        )
        detail_match = {
            "required_any_of": any_of,
            "required_all_of": all_of,
            "satisfied_details": matched_details,
            "declared_satisfied_details": [d for d in matched_details if d in details],
            "implied_satisfied_details": [
                d for d in matched_details if d not in details
            ],
            "missing_all_of": missing_all,
            "any_of_satisfied": any_satisfied,
            "all_of_satisfied": not missing_all,
            "textual_reading_resolved": reading_resolved,
            "applied_to_aggregate": applies,
        }
        if applies:
            matches.append(
                {
                    **rule,
                    "applicability_status": "matched_declared_activity_detail",
                    "matched_activity_details": matched_details,
                    "applied_to_aggregate": True,
                    "detail_match": detail_match,
                }
            )
        else:
            conditional.append(
                {
                    **rule,
                    "applicability_status": (
                        "not_evaluated_textual_reading_unresolved"
                        if rule.get("requires_textual_review")
                        else "not_evaluated_activity_detail_missing"
                    ),
                    "applied_to_aggregate": False,
                    "detail_match": detail_match,
                }
            )
    layers = []
    for name, values in selectors.items():
        facts = [r for r in matches if r["layer"] == name]
        pending = [r for r in conditional if r["layer"] == name]
        signs = {r["assessment"] for r in facts}
        state = (
            "conflicted"
            if len(signs) > 1
            else (
                next(iter(signs))
                if signs
                else (
                    "conditional_only"
                    if pending
                    else "not_evaluated" if not values else "uncovered"
                )
            )
        )
        layers.append(
            {
                "layer": name,
                "status": state,
                "rule_ids": [r["rule_id"] for r in facts],
                "conditional_rule_ids": [r["rule_id"] for r in pending],
            }
        )
    signs = {r["assessment"] for r in matches}
    # Status describes the selected documentary evidence, not an event forecast.
    status = (
        "conflicted"
        if len(signs) > 1
        else (
            next(iter(signs))
            if signs
            else "conditional_only" if conditional else "uncovered"
        )
    )
    return {
        "activity": activity,
        "activity_details": details,
        "effective_activity_details": effective_details,
        "detail_inferences": detail_inferences,
        "evidence_status": status,
        "layers": layers,
        "matched_rules": matches,
        "conditional_rules": conditional,
        "conditional_rules_applied_to_aggregate": False,
        "textual_issues": [
            *day.get("lower_mansion_day", {}).get("textual_issues", []),
            *(
                day.get("directional_travel", {}).get("textual_issues", [])
                if activity == "travel"
                else []
            ),
        ],
        "ruleset_id": bundle["id"],
        "source_bundle_sha256": load_source(SOURCE).sha256,
        "named_day_source_bundle_sha256": day_source_digest(),
        "lower_mansion_source_bundle_sha256": lower_source_digest(),
        "lower_methods_source_bundle_sha256": load_source(METHOD_SOURCE).sha256,
        "travel_direction_source_bundle_sha256": direction_source_digest(),
        "special_day_source_bundle_sha256": special_source_digest(),
        "sanjiu_day_source_bundle_sha256": load_source(SANJIU_SOURCE).sha256,
        "unresolved_source_rules_present": any(
            r.get("requires_textual_review") for r in conditional
        ),
        "supplemental_ruleset_ids": [
            day_source_bundle()["id"],
            lower_source_bundle()["id"],
            method_source_bundle()["id"],
            direction_source_bundle()["id"],
            special_source_bundle()["id"],
            sanjiu_source_bundle()["id"],
            *([clothing_source_bundle()["id"]] if activity == "clothing" else []),
        ],
        **(
            {"clothing_source_bundle_sha256": load_source(CLOTHING_SOURCE).sha256}
            if activity == "clothing"
            else {}
        ),
        "time_evaluation_status": day["calendar_day"]["clock_evaluation_status"],
        "aggregation": "No weights, score, majority vote or tie breaking; preserve every matched clause.",
        "scope": "文献事项证据；未列事项不等于禁忌，冲突不改成综合吉日；conditional_rules为缺适用细节或文本读法未校定的条件文，不代入汇总；昼夜例外另见calendar_day，未完成钟时判定，不能当作全天适宜；不代表现实结果或行动许可。",
    }
