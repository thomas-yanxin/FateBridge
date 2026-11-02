"""Selected day/month qi clauses, without a year-qi or net forecast model."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role

from .almanac import get_day_ganzhi
from .meihua import meihua_stage_relations
from .requests.meihua_day_qi import MeihuaDayQiContext

_RELATION_LABELS = {
    "体用比和": "日气与原体比和",
    "体生用": "原体生日气",
    "体克用": "原体克日气",
    "用生体": "日气生原体",
    "用克体": "日气克原体",
}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/day-qi-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if value["id"] != "meihua_day_qi_nlc1925_v1" or value["version"] != "1.0.0":
        raise ValueError("Unknown selected day-qi profile")
    return value


def day_qi_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def normalize_day_qi_context(
    context: dict[str, Any] | None, topic: str
) -> dict[str, Any] | None:
    if context is None:
        return None
    if topic == "weather":
        raise ValueError("所选日气体用条款仅用于人事分支，不能套用天时占")
    return MeihuaDayQiContext.model_validate(context).model_dump(mode="json")


def civil_day_qi_context(moment: datetime, *, bazi_day_ganzhi: str) -> dict[str, Any]:
    """Use the cast's declared civil-midnight date; retain the 23h alternative."""
    civil = moment.date()
    selected = get_day_ganzhi(civil.year, civil.month, civil.day)
    zi_date = civil + timedelta(days=int(moment.hour == 23))
    zi = get_day_ganzhi(zi_date.year, zi_date.month, zi_date.day)
    candidates = [
        {
            "id": "local_midnight",
            "date": civil.isoformat(),
            "ganzhi": selected,
            "day_branch": selected[1],
            "day_boundary": "local_midnight",
        }
    ]
    if moment.hour == 23:
        candidates.append(
            {
                "id": "zi_start",
                "date": zi_date.isoformat(),
                "ganzhi": zi,
                "day_branch": zi[1],
                "day_boundary": "zi_start",
            }
        )
    return {
        "origin": "computed_from_selected_civil_clock",
        "selected_candidate_id": "local_midnight",
        "selection_basis": "matches_existing_meihua_civil_midnight_convention_not_unique_classical_adjudication",
        "clock_fact_path": "analysis_context.analysis_datetime",
        "timezone_fact_path": "analysis_context.timezone",
        "candidates": candidates,
        "boundary_changes_day_branch": moment.hour == 23,
        "bazi_day_reference": {
            "ganzhi": bazi_day_ganzhi,
            "fact_path": "calendar_context.lunar_calendar.day_ganzhi",
            "matches_zi_start_reference": bazi_day_ganzhi == zi,
            "used_as_selected_midnight_day": False,
        },
    }


def reported_day_qi_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "origin": "caller_reported_day_branch_unverified",
        "selected_candidate_id": "caller_reported",
        "selection_basis": "explicit_day_branch_not_a_verified_date",
        "clock_fact_path": None,
        "timezone_fact_path": None,
        "candidates": [
            {
                "id": "caller_reported",
                "date": None,
                "ganzhi": None,
                "day_branch": context["day_branch"],
                "day_boundary": context["declared_day_boundary"],
            }
        ],
        "boundary_changes_day_branch": None,
        "bazi_day_reference": None,
    }


def _reading(
    cast: dict[str, Any],
    context: dict[str, Any],
    *,
    fact_prefix: str,
    layer_path: str,
    declared_fact_path: str | None,
    month_strength: dict[str, Any] | None,
    month_path: str | None,
) -> dict[str, Any]:
    body = cast["body_trigram"]
    stages = meihua_stage_relations(cast, fact_prefix=fact_prefix)
    nodes = [
        {
            "role": "body",
            "trigram": body["name"],
            "element": body["element"],
            "relation_to_body": "body_self",
            "fact_path": fact_prefix + ".body_trigram",
        },
        *[
            {
                "role": row["role"],
                "trigram": row["trigram"],
                "element": row["element"],
                "relation_to_body": row["relation"],
                "fact_path": row["fact_path"],
            }
            for row in stages
        ],
    ]
    month_rows = (
        {row["role"]: (i, row) for i, row in enumerate(month_strength["trigrams"])}
        if month_strength
        else {}
    )
    candidates = []
    for index, calendar in enumerate(context["candidates"]):
        branch = calendar["day_branch"]
        element = _profile()["day_branch_elements"][branch]
        weak = _profile()["weak_element_when_wang"][element]
        relation = relationship_by_role(body["element"], element)
        roles = []
        for node in nodes:
            strength = (
                "旺"
                if node["element"] == element
                else "衰" if node["element"] == weak else "原文未定"
            )
            preferred = (
                "旺"
                if node["relation_to_body"] == "用生体"
                else "衰" if node["relation_to_body"] == "用克体" else None
            )
            month_index, month = month_rows.get(node["role"], (None, None))
            if month is not None and (month["trigram"], month["element"]) != (
                node["trigram"],
                node["element"],
            ):
                raise ValueError(
                    "Day and month strength must refer to the same actual role"
                )
            month_label = month["strength"] if month else None
            agreement = (
                "month_context_missing"
                if month_label is None
                else (
                    "not_comparable_in_selected_tables"
                    if "原文未定" in (strength, month_label)
                    else (
                        "same_label"
                        if strength == month_label
                        else "different_labels_no_aggregation"
                    )
                )
            )
            roles.append(
                {
                    **deepcopy(node),
                    "day_strength": strength,
                    "preferred_day_strength": preferred,
                    "preference_status": (
                        "not_stated_for_this_role_relation"
                        if preferred is None
                        else (
                            "unknown_strength"
                            if strength == "原文未定"
                            else (
                                "matches" if strength == preferred else "does_not_match"
                            )
                        )
                    ),
                    "preference_rule_id": (
                        "supporter_prefers_wang"
                        if preferred == "旺"
                        else "attacker_prefers_shuai" if preferred == "衰" else None
                    ),
                    "month_strength": month_label,
                    "month_strength_fact_path": (
                        f"{month_path}.trigrams.{month_index}.strength"
                        if month is not None
                        else None
                    ),
                    "month_day_comparison": agreement,
                    "net_strength": None,
                }
            )
        preference = _profile()["day_relation_preferences"].get(relation)
        candidates.append(
            {
                "calendar": deepcopy(calendar),
                "day_branch_fact_path": (
                    declared_fact_path
                    if declared_fact_path is not None
                    else f"{layer_path}.calendar_candidates.{index}.calendar.day_branch"
                ),
                "calendar_derivation_clock_fact_path": context["clock_fact_path"],
                "day_element": element,
                "day_element_is_a_unique_trigram": False,
                "wang_element": element,
                "shuai_element": weak,
                "original_body": {
                    "name": body["name"],
                    "element": body["element"],
                    "fact_path": fact_prefix + ".body_trigram",
                },
                "day_qi_relation_to_original_body": relation,
                "day_relation_label": _RELATION_LABELS[relation],
                "selected_day_clause_preference": preference,
                "day_clause_subject_scope": "Selected reading of卦against本日所屬卦氣; no unique complete interpretation claim",
                "roles": roles,
                "overall_day_verdict": None,
                "month_day_net_judgement": None,
            }
        )
    selected = next(
        row
        for row in candidates
        if row["calendar"]["id"] == context["selected_candidate_id"]
    )
    calendar = selected["calendar"]
    label = (
        f"按已声明民用午夜日界，{calendar['date']}{calendar['ganzhi']}"
        if context["origin"] == "computed_from_selected_civil_clock"
        else f"按已报{calendar['day_branch']}日支"
    )
    body_row = selected["roles"][0]
    summary = f"{label}取{selected['day_element']}气，原体{body['name']}的日气标记为{body_row['day_strength']}，符号关系为{selected['day_relation_label']}。"
    if body_row["month_day_comparison"] == "different_labels_no_aggregation":
        summary += f"月令标记{body_row['month_strength']}与日气标记{body_row['day_strength']}并存，未作平均、抵消或净旺衰裁定。"
    if context["boundary_changes_day_branch"]:
        alternate = candidates[1]
        summary += f"23时另保留子初换日口径：{alternate['calendar']['date']}{alternate['calendar']['ganzhi']}、{alternate['day_element']}气，原体日气标记{alternate['roles'][0]['day_strength']}；不能把附带八字日柱冒作所选午夜日。"
    summary += "日应与时令偏好另列，年月日完整合参尚未成立，不据此推断现实成败或应期。"
    return {
        "ruleset_id": _profile()["id"],
        "version": _profile()["version"],
        "ruleset": day_qi_ruleset(),
        "origin": context["origin"],
        "selected_candidate_id": context["selected_candidate_id"],
        "selection_basis": context["selection_basis"],
        "selected_boundary_uniquely_authorized_by_original": False,
        "clock_fact_path": context["clock_fact_path"],
        "timezone_fact_path": context["timezone_fact_path"],
        "bazi_day_reference": deepcopy(context["bazi_day_reference"]),
        "boundary_changes_day_branch": context["boundary_changes_day_branch"],
        "boundary_changes_day_element": (
            len({row["day_element"] for row in candidates}) > 1
            if context["boundary_changes_day_branch"] is not None
            else None
        ),
        "calendar_candidates": candidates,
        "complete_year_month_day_strength_synthesis": None,
        "full_selected_quiet_judgement_established": False,
        "event_time": None,
        "real_outcome": None,
        "changes_registered_forecast_eligibility_or_denominators": False,
        "summary": summary,
    }


def apply_day_qi(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    context: dict[str, Any] | None,
    *,
    declared_fact_path: str | None = None,
) -> None:
    interpretation["day_qi"] = None
    if interpretation["interpretation_topic"] == "weather":
        return
    if context is not None:
        interpretation["day_qi"] = _reading(
            cast,
            context,
            fact_prefix="meihua",
            layer_path="interpretation.day_qi",
            declared_fact_path=declared_fact_path,
            month_strength=cast.get("seasonal_strength"),
            month_path="meihua.seasonal_strength",
        )
    suffix = interpretation["day_qi"]["summary"] if context is not None else ""
    for index, row in enumerate(interpretation.get("casting_readings") or []):
        row["day_qi"] = (
            _reading(
                cast["counting_variants"][index],
                context,
                fact_prefix=f"meihua.counting_variants.{index}",
                layer_path=f"interpretation.casting_readings.{index}.day_qi",
                declared_fact_path=declared_fact_path,
                month_strength=row.get("seasonal_strength"),
                month_path=f"interpretation.casting_readings.{index}.seasonal_strength",
            )
            if context is not None
            else None
        )
        if context is not None:
            suffix += (
                ("原数" if row["line_sum_basis"] == "raw_counts" else "卦序数")
                + "候选日气另核："
                + row["day_qi"]["summary"]
            )
    if suffix:
        interpretation["comprehensive_judgement"] += suffix
