"""Selected volume-three strength clauses, including the attacking-role exception.

These are tests of declared-month labels and raw inner relations. They do not
cancel existing relations, adjudicate outer support or synthesize a net result.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any

from fatebridge.core.meihua_roles import LABELS, ROLES


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath("meihua/strength-exceptions-nlc1925-v1.json")
        .read_text(encoding="utf-8")
    )
    expected = {
        "wang_body_receives_control",
        "wang_auxiliary_except_attacker",
        "shuai_body",
        "wang_body_receives_generation",
    }
    if (
        profile["id"] != "meihua_strength_exceptions_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != len(expected)
        or {r["id"] for r in profile["rules"]} != expected
    ):
        raise ValueError("Unknown selected volume-three strength clauses")
    return profile


def strength_exception_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _condition_status(structural: bool, strength: str | None, required: str) -> str:
    if not structural:
        return "not_matched"
    if strength not in {"旺", "衰"}:
        return "pending_strength"
    return (
        "matched_selected_month_conditions" if strength == required else "not_matched"
    )


def _auxiliary_clause_applicability(
    strength: str | None, attacking: bool
) -> dict[str, bool | None]:
    wang = None if strength not in {"旺", "衰"} else strength == "旺"
    return {
        "favorable_clause_applies": False if attacking or wang is False else wang,
        "attacker_wang_exception_applies": (
            False if not attacking or wang is False else wang
        ),
    }


def build_strength_exceptions(
    roles: list[dict[str, Any]], control: dict[str, Any]
) -> dict[str, Any]:
    """Read the actual precomputed role labels; never infer a missing month."""
    if (
        [r["role"] for r in roles] != ["body", *ROLES]
        or [r["role"] for r in control["nodes"]] != ["body", *ROLES]
        or [r["role"] for r in control["qualifications"]] != list(ROLES)
    ):
        raise ValueError("Strength exceptions require the same five actual roles")
    for row, node in zip(roles, control["nodes"], strict=True):
        if any(
            row[key] != node[key]
            for key in ["trigram", "element", "relation_to_body", "fact_path"]
        ):
            raise ValueError("Strength and control facts belong to different casts")
        if row["strength"] not in {None, "旺", "衰", "原文未定"}:
            raise ValueError(
                "Unknown strength is not an invented weak or neutral label"
            )
    for row, qualification in zip(roles[1:], control["qualifications"], strict=True):
        if (row["relation_to_body"], row["fact_path"]) != (
            qualification["original_relation_to_body"],
            qualification["target_fact_path"],
        ):
            raise ValueError("Strength exception qualifications belong to another cast")
    profile = _profile()
    rules = {r["id"]: r for r in profile["rules"]}
    body = roles[0]
    checks = []
    for rule_id in [
        "wang_body_receives_control",
        "shuai_body",
        "wang_body_receives_generation",
    ]:
        rule = rules[rule_id]
        related = [r for r in roles[1:] if r["relation_to_body"] == rule["relation"]]
        structural = rule["relation"] is None or bool(related)
        checks.append(
            {
                "rule_id": rule_id,
                "quote": rule["quote"],
                "source_pdf_indices": deepcopy(rule["pdf_indices"]),
                "source_symbol": rule["source_symbol"],
                "status": _condition_status(
                    structural, body["strength"], rule["body_strength"]
                ),
                "structural_condition_met": structural,
                "required_body_strength": rule["body_strength"],
                "body_strength": body["strength"],
                "body_fact_path": body["fact_path"],
                "body_strength_fact_path": body["strength_fact_path"],
                "related_roles": [r["role"] for r in related],
                "relation_fact_paths": [r["relation_fact_path"] for r in related],
                "effect_after_all_controls": None,
            }
        )
    rule = rules["wang_auxiliary_except_attacker"]
    auxiliary = []
    for row, qualification in zip(roles[1:], control["qualifications"], strict=True):
        wang = _condition_status(True, row["strength"], "旺")
        status = (
            "excluded_by_attacker_exception"
            if wang == "matched_selected_month_conditions"
            and row["relation_to_body"] == "用克体"
            else wang
        )
        auxiliary.append(
            {
                **deepcopy(row),
                "rule_id": rule["id"],
                "quote": rule["quote"],
                "source_pdf_indices": deepcopy(rule["pdf_indices"]),
                "status": status,
                "attacking_relation": row["relation_to_body"] == "用克体",
                **_auxiliary_clause_applicability(
                    row["strength"], row["relation_to_body"] == "用克体"
                ),
                "internal_control_qualification": deepcopy(qualification),
                "effect_after_all_controls": None,
            }
        )
    parts = []
    for row in checks:
        if row["status"] != "matched_selected_month_conditions":
            continue
        if row["rule_id"] == "wang_body_receives_control":
            parts.append(
                f"原体{body['trigram']}标旺且见克体，卷三所选句另列亦無大害的传统限定；原克体仍保留。"
            )
        elif row["rule_id"] == "shuai_body":
            parts.append(f"原体{body['trigram']}标衰，所选段列不吉之占的强弱象义。")
        else:
            parts.append(
                f"原体{body['trigram']}标旺且有生体，所选段列吉事之来；未计算应期。"
            )
    favorable = [
        r for r in auxiliary if r["status"] == "matched_selected_month_conditions"
    ]
    excepted = [r for r in auxiliary if r["status"] == "excluded_by_attacker_exception"]
    if favorable:
        parts.append(
            "、".join(LABELS[r["role"]] + r["trigram"] for r in favorable)
            + "符合所选用互变乘旺句的角色条件。"
        )
    if excepted:
        parts.append(
            "、".join(LABELS[r["role"]] + r["trigram"] for r in excepted)
            + "既克体又标旺，属于原句明示例外，不引用乘旺皆吉。"
        )
    if not parts:
        parts.append("所列卷三条件未触发或旺衰待定，不把未知当衰。")
    parts.append(
        "本层仅核所选月令与原始内卦关系，制约、卷二条件及日气另核；未综合净作用、现实安全或成败。"
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": strength_exception_ruleset(),
        "basis": "existing_declared_month_labels_and_raw_internal_relations",
        "original_body": deepcopy(body),
        "condition_checks": checks,
        "auxiliary_checks": auxiliary,
        "unresolved_source_clauses": [
            {
                **deepcopy(clause),
                "status": "not_adjudicated",
                "known_internal_generation_roles": [
                    r["role"] for r in roles[1:] if r["relation_to_body"] == "用生体"
                ],
                "external_support_or_absence": None,
                "external_status": "not_adjudicated_by_this_month_internal_layer",
                "full_clause_applies": None,
            }
            for clause in profile["unresolved_source_clauses"]
        ],
        "source_conditions_are_effective_net_strength": False,
        "volume2_volume3_priority": "not_adjudicated",
        "net_verdict": None,
        "event_time": None,
        "real_outcome": None,
        "success_probability": None,
        "summary": "".join(parts),
        "predictive_efficacy_established": False,
    }
