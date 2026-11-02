"""Selected wealth-supplement atoms from one held cast, without a net verdict."""

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
            / "data/meihua/wealth-components-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_wealth_components_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected wealth component profile")
    return profile


def wealth_component_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def build_wealth_components(
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    countercontrol: dict[str, Any],
    *,
    fact_prefix: str = "meihua",
    interpretation_prefix: str = "interpretation",
) -> dict[str, Any]:
    """Expose literal named relations; do not decide how 及 combines them."""
    if [row["role"] for row in stages] != list(ROLES):
        raise ValueError("Wealth components require all four actual stage roles")
    profile = _profile()
    qualifications = {q["role"]: q for q in countercontrol["qualifications"]}
    strengths = {
        row["role"]: (index, row)
        for index, row in enumerate(seasonal["trigrams"] if seasonal else [])
    }
    roles = []
    parts = []
    for index, stage in enumerate(stages):
        role = stage["role"]
        strength = strengths.get(role)
        strength_prefix = (
            fact_prefix + ".seasonal_strength"
            if fact_prefix == "meihua"
            else interpretation_prefix + ".seasonal_strength"
        )
        roles.append(
            {
                "role": role,
                "body": stage["body"],
                "body_fact_path": fact_prefix + ".body_trigram",
                "trigram": stage["trigram"],
                "relation": stage["relation"],
                "fact_path": stage["fact_path"],
                "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
                "source_component_sides": [
                    rule["side"]
                    for rule in profile["rules"]
                    if stage["relation"] in rule["named_relations"]
                ],
                "seasonal_strength": strength[1]["strength"] if strength else None,
                "strength_fact_path": (
                    f"{strength_prefix}.trigrams.{strength[0]}" if strength else None
                ),
                "countercontrol_qualification": deepcopy(qualifications[role]),
                "control_qualification_fact_path": (
                    f"{interpretation_prefix}.internal_countercontrol.qualifications.{index}"
                ),
                "effect_after_all_qualifications": None,
            }
        )
        parts.append(
            f"{LABELS[role]}{stage['trigram']}对原体{stage['body']}为{stage['relation']}。"
        )
    groups = {}
    for rule in profile["rules"]:
        components = [
            {
                "relation": relation,
                "present": any(r["relation"] == relation for r in roles),
                "matching_roles": [
                    r["role"] for r in roles if r["relation"] == relation
                ],
                "fact_paths": [
                    r["fact_path"] for r in roles if r["relation"] == relation
                ],
            }
            for relation in rule["named_relations"]
        ]
        groups[rule["side"]] = {
            "rule_id": rule["id"],
            "quote": rule["quote"],
            "source_result_wording": rule["source_result_wording"],
            "components": components,
            "all_named_components_present": all(c["present"] for c in components),
            "junction_semantics": "not_adjudicated",
            "full_clause_applies": None,
        }
    both = all(any(c["present"] for c in g["components"]) for g in groups.values())
    summary = "所选《求財占》补充句另核实际内卦关系：" + "".join(parts)
    if both:
        summary += "原文有财相关成分与破财相关成分同时出现，须并列保留。"
    summary += (
        "这些是原文所列关系成分，不替换初始体用条款；"
        "及的组合含义及旺衰、制约尚未综合，未据此断实际财增减或日期。"
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": wealth_component_ruleset(),
        "scope": "original_static_body_vs_four_actual_auxiliary_roles",
        "body": stages[0]["body"],
        "roles": roles,
        "source_groups": groups,
        "components_from_both_source_sides_present": both,
        "timing_reference": {
            "quote": profile["timing_quote"],
            "scope": "source_reference_not_computed_event_time",
            "event_time": None,
        },
        "event_time": None,
        "real_financial_change": None,
        "success_probability": None,
        "independent_observations": 0,
        "summary": summary,
    }
