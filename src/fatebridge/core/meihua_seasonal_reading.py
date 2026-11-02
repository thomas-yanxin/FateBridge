"""Selected joint strength/relation clauses without a net outcome model."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_roles import LABELS, ROLES


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/seasonal-reading-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_seasonal_reading_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected Meihua strength-reading profile")
    return profile


def seasonal_reading_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _preference_status(actual: str | None, expected: str | None) -> str:
    if expected is None:
        return "not_applicable"
    if actual not in {"旺", "衰"}:
        return "unknown_strength"
    return "matches" if actual == expected else "does_not_match"


def build_seasonal_qualification(
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    control: dict[str, Any],
    *,
    fact_prefix: str = "meihua",
    strength_prefix: str = "meihua.seasonal_strength",
) -> dict[str, Any]:
    """Use computed labels as supplied; 原文未定 never becomes neutral or weak."""
    if [r["role"] for r in stages] != list(ROLES):
        raise ValueError("Strength reading requires the four actual stage roles")
    nodes = control["nodes"]
    if [n["role"] for n in nodes] != ["body", *ROLES]:
        raise ValueError("Strength reading requires the same internal role occurrences")
    if (nodes[0]["trigram"], nodes[0]["element"]) != (
        stages[0]["body"],
        stages[0]["body_element"],
    ) or any(
        (n["trigram"], n["element"], n["relation_to_body"])
        != (r["trigram"], r["element"], r["relation"])
        for n, r in zip(nodes[1:], stages, strict=True)
    ):
        raise ValueError(
            "Strength and control contexts must belong to the same actual cast"
        )
    strengths = {}
    if seasonal is not None:
        if [r["role"] for r in seasonal["trigrams"]] != ["body", *ROLES]:
            raise ValueError("Strength labels must cover each actual role once")
        for index, (n, row) in enumerate(zip(nodes, seasonal["trigrams"], strict=True)):
            if (n["trigram"], n["element"]) != (row["trigram"], row["element"]):
                raise ValueError("Strength label belongs to another cast")
            strengths[n["role"]] = (
                row["strength"],
                f"{strength_prefix}.trigrams.{index}.strength",
            )
    rules = {r["id"]: r for r in _profile()["rules"]}
    role_rows = []
    for index, n in enumerate(nodes):
        strength, path = strengths.get(n["role"], (None, None))
        role_rows.append(
            {
                **deepcopy(n),
                "strength": strength,
                "strength_fact_path": path,
                "relation_fact_path": (
                    None
                    if index == 0
                    else f"{fact_prefix}.stage_relations.{index-1}.relation"
                ),
                "strength_status": (
                    "known_selected_label"
                    if strength in {"旺", "衰"}
                    else (
                        "not_classified_in_selected_strength_table"
                        if strength is not None
                        else "month_branch_not_supplied"
                    )
                ),
            }
        )
    body = role_rows[0]
    preferences = []
    for n in role_rows:
        key = (
            "body_prefers_wang"
            if n["role"] == "body"
            else (
                "supporter_prefers_wang"
                if n["relation_to_body"] == "用生体"
                else (
                    "attacker_prefers_shuai"
                    if n["relation_to_body"] == "用克体"
                    else None
                )
            )
        )
        rule = rules[key] if key is not None else None
        expected = rule["preferred_strength"] if rule is not None else None
        preferences.append(
            {
                "role": n["role"],
                "strength": n["strength"],
                "preferred_strength": expected,
                "status": _preference_status(n["strength"], expected),
                "rule_id": key,
                "quote": rule["quote"] if rule is not None else None,
                "trigram_fact_path": n["fact_path"],
                "strength_fact_path": n["strength_fact_path"],
            }
        )
    control_qualifications = {
        q["role"]: q["qualification"] for q in control["qualifications"]
    }
    conditions = []
    for rule in _profile()["rules"]:
        if rule["kind"] != "joint_condition":
            continue
        related = [
            n
            for n in role_rows[1:]
            if n["relation_to_body"] == rule["auxiliary_relation"]
        ]
        if not related:
            status = "not_matched"
        elif body["strength"] not in {"旺", "衰"}:
            status = "pending_strength"
        else:
            status = (
                "matched"
                if body["strength"] == rule["body_strength"]
                else "not_matched"
            )
        conditions.append(
            {
                "rule_id": rule["id"],
                "quote": rule["quote"],
                "signal": rule["signal"],
                "status": status,
                "expected_body_strength": rule["body_strength"],
                "actual_body_strength": body["strength"],
                "body_strength_fact_path": body["strength_fact_path"],
                "auxiliary_relation": rule["auxiliary_relation"],
                "related_roles": [n["role"] for n in related],
                "relation_fact_paths": [n["relation_fact_path"] for n in related],
                "countercontrol_qualifications": {
                    n["role"]: control_qualifications[n["role"]] for n in related
                },
                "full_effect_after_countercontrol": "not_adjudicated",
            }
        )
    matched = {r["rule_id"] for r in conditions if r["status"] == "matched"}
    parts = []
    for row in conditions:
        if row["status"] != "matched":
            continue
        labels = "、".join(
            LABELS[r] + next(n["trigram"] for n in role_rows if n["role"] == r)
            for r in row["related_roles"]
        )
        if row["rule_id"] == "wang_body_receives_generation":
            parts.append(
                f"原体{body['trigram']}标为旺，又有{labels}生体，所选《衰旺论》取气旺逢生之吉象。"
            )
        elif row["rule_id"] == "shuai_body_receives_control":
            parts.append(
                f"原体{body['trigram']}标为衰，且有{labels}克体，所选条款取受克之忧加重之象。"
            )
        else:
            parts.append(
                f"原体{body['trigram']}标为衰，仍有{labels}生体，所选条款取衰稍解。"
            )
    if any(r["status"] == "pending_strength" for r in conditions):
        parts.append(
            "体气未由当前所选月支旺衰表定级，相关联合条件仍待核定。"
            if seasonal is not None
            else "未给已确认节月，相关旺衰联合条件待核定。"
        )
    preferred = [r for r in preferences[1:] if r["status"] == "matches"]
    if preferred:
        labels = "、".join(
            LABELS[r["role"]]
            + next(n["trigram"] for n in role_rows if n["role"] == r["role"])
            + ("符合生体宜旺" if r["preferred_strength"] == "旺" else "符合克体宜衰")
            for r in preferred
        )
        parts.append(labels + "的所列偏好。")
    if not parts:
        parts.append("当前所列三条旺衰联合条件未触发；不据此给出整体吉凶。")
    parts.append(
        "这些为分别记录的条款与偏好，须与生克受制并看，未合成为净吉凶、应期或现实成败。"
    )
    result = {
        "ruleset_id": _profile()["id"],
        "version": _profile()["version"],
        "ruleset": seasonal_reading_ruleset(),
        "context_status": (
            "supplied_declared_month_branch"
            if seasonal is not None
            else "missing_month_branch"
        ),
        "basis": seasonal["basis"] if seasonal is not None else None,
        "month_branch": seasonal["month_branch"] if seasonal is not None else None,
        "roles": role_rows,
        "preferences": preferences,
        "condition_checks": conditions,
        "simultaneous_increased_constraint_and_partial_relief": {
            "shuai_body_receives_control",
            "shuai_body_receives_generation",
        }
        <= matched,
        "preference_matches_are_joint_necessary_conditions": False,
        "repeated_control_clause": {
            "quote": _profile()["unresolved_clause"]["quote"],
            "status": "not_adjudicated",
            "reason": _profile()["unresolved_clause"]["scope"],
        },
        "month_day_strength_synthesis": "not_computed",
        "full_countercontrol_strength_synthesis": "not_computed",
        "net_verdict": None,
        "success_probability": None,
        "event_time": None,
        "summary": "".join(parts),
        "real_world_efficacy": "not_established",
    }
    from .meihua_strength_exceptions import build_strength_exceptions

    result["volume3_qualification"] = build_strength_exceptions(role_rows, control)
    result["volume2_summary"] = result["summary"]
    result["summary_scope"] = (
        "selected_volume2_and_volume3_parallel_conditions_no_net_priority_v1"
    )
    result["summary"] = (
        "卷二所选《衰旺论》："
        + result["volume2_summary"]
        + "卷三所选《体用衰旺之诀》："
        + result["volume3_qualification"]["summary"]
    )
    from .meihua_volume5_strength import build_volume5_strength_comparison

    result["volume5_table_comparison"] = build_volume5_strength_comparison(
        role_rows, seasonal
    )
    return result
