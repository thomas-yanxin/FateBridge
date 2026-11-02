"""Selected ordinal emphasis and conditional relative wording from NLC1925."""

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
            / "data/meihua/stage-emphasis-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_stage_emphasis_nlc1925_v1"
        or profile["version"] != "1.1.0"
    ):
        raise ValueError("Unknown selected Meihua stage emphasis profile")
    return profile


def stage_emphasis_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _scenario_conditions(
    rule: dict[str, Any],
    structural: bool,
    scenario: str | None,
    *,
    unresolved: list[str] | None = None,
) -> dict[str, Any]:
    match = None if scenario is None else scenario == rule["required_scenario"]
    pending = list(unresolved or []) if match and structural else []
    return {
        "required_scenario": rule["required_scenario"],
        "structural_condition_met": structural,
        "scenario_condition": (
            "not_collected"
            if match is None
            else "caller_declared_match" if match else "caller_declared_other_scenario"
        ),
        "scenario_condition_met": match,
        "unresolved_conditions": pending,
        "full_clause_applies": (
            False
            if not structural
            else None if match is None or pending else bool(match)
        ),
        "condition_evaluation_scope": "selected_source_clause_conditions_only_not_net_effect_or_real_outcome",
    }


def _reading(
    stages: list[dict[str, Any]],
    control: dict[str, Any],
    seasonal: dict[str, Any] | None,
    *,
    fact_prefix: str,
    interpretation_prefix: str,
    matter_scenario: str | None,
    scenario_fact_path: str,
) -> dict[str, Any]:
    if [r["role"] for r in stages] != list(ROLES):
        raise ValueError("Stage emphasis requires four actual auxiliary roles")
    profile = _profile()
    rules = {r["id"]: r for r in profile["rules"]}
    qualifications = {r["role"]: r for r in control["qualifications"]}
    strengths = {
        r["role"]: (i, r)
        for i, r in enumerate(seasonal["trigrams"] if seasonal else [])
    }
    strength_prefix = (
        fact_prefix + ".seasonal_strength"
        if fact_prefix == "meihua"
        else interpretation_prefix + ".seasonal_strength"
    )
    roles = []
    for index, stage in enumerate(stages):
        strength = strengths.get(stage["role"])
        roles.append(
            {
                **deepcopy(stage),
                "body_fact_path": fact_prefix + ".body_trigram",
                "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
                "countercontrol_qualification": deepcopy(qualifications[stage["role"]]),
                "control_qualification_fact_path": f"{interpretation_prefix}.internal_countercontrol.qualifications.{index}",
                "seasonal_strength": strength[1]["strength"] if strength else None,
                "strength_fact_path": (
                    f"{strength_prefix}.trigrams.{strength[0]}" if strength else None
                ),
            }
        )
    generation = [r["role"] for r in roles if r["relation"] == "用生体"]
    attackers = [r["role"] for r in roles if r["relation"] == "用克体"]
    clauses = []
    for rule_id, group in [
        ("support_use_relative", ["use"]),
        ("support_mutual_relative", ["body_mutual", "use_mutual"]),
        ("support_changed_relative", ["changed_use"]),
    ]:
        rule = rules[rule_id]
        matching = [r for r in generation if r in group]
        clauses.append(
            {
                "rule_id": rule_id,
                "quote": rule["quote"],
                "original_pdf_indices": deepcopy(rule["pdf_indices"]),
                "relative_wording": rule["relative_wording"],
                "matching_roles": matching,
                "relation_fact_paths": [
                    r["relation_fact_path"] for r in roles if r["role"] in matching
                ],
                **_scenario_conditions(
                    rule,
                    bool(matching),
                    matter_scenario,
                    unresolved=(
                        ["mutual_phrase_scope"]
                        if rule_id == "support_mutual_relative"
                        else []
                    ),
                ),
                "reading": rule["reading"],
                "duration": None,
                "event_time": None,
            }
        )
    mixed = {
        "rule_id": "generation_and_control",
        "quote": rules["generation_and_control"]["quote"],
        "original_pdf_indices": deepcopy(
            rules["generation_and_control"]["pdf_indices"]
        ),
        "generation_roles": generation,
        "control_roles": attackers,
        **_scenario_conditions(
            rules["generation_and_control"],
            bool(generation and attackers),
            matter_scenario,
        ),
        "reading": rules["generation_and_control"]["reading"],
    }
    scenario_clauses = []
    for rule_id, structural in [
        (
            "favorable_without_generation_with_control",
            bool(not generation and attackers),
        ),
        ("unfavorable_with_generation", bool(generation)),
        ("unfavorable_without_generation", not bool(generation)),
    ]:
        rule = rules[rule_id]
        scenario_clauses.append(
            {
                "rule_id": rule_id,
                "quote": rule["quote"],
                "original_pdf_indices": deepcopy(rule["quote_pdf_indices"]),
                "generation_roles": list(generation),
                "control_roles": list(attackers),
                **_scenario_conditions(rule, structural, matter_scenario),
                "reading": rule["reading"],
                "real_outcome": None,
                "event_time": None,
            }
        )
    summary = (
        "所选卷三另列用最紧、互次之、变又次之；互层中体互最紧、用互次之。"
        "这是原文分析紧次，不是数值权重。"
    )
    if matter_scenario is None:
        summary += "生体迟速句以问吉事为前提，此项未采集。"
    else:
        label = "问吉事" if matter_scenario == "favorable_matter" else "问不吉之事"
        summary += (
            f"调用方明示本次为原文{label}情境，声明未独立核实，只用于核对所选原句前提。"
        )
    for clause in clauses:
        if clause["matching_roles"] and matter_scenario != "unfavorable_matter":
            names = "、".join(LABELS[r] for r in clause["matching_roles"])
            summary += (
                f"本次{names}为用生体，该位置所对应的条件原句作“{clause['quote']}”。"
            )
            if clause["unresolved_conditions"]:
                summary += "互字范围未裁定，所列互角色有生体仍不确认整句适用。"
    if not generation:
        summary += "本次所列内卦角色未见用生体，不能单凭这一项断事不成。"
    if mixed["structural_condition_met"] and matter_scenario != "unfavorable_matter":
        summary += "本次内卦同时见生体与克体，所选原句仍有“事有阻節好中不足”，不能只读生体迟速句。"
    if matter_scenario is None:
        summary += (
            "既有旺衰与直接制约保留，未综合净作用；未认定问事情境、现实成败或日期。"
        )
    else:
        for clause in scenario_clauses:
            if clause["full_clause_applies"]:
                summary += f"本次所报情境及所列关系对应原句“{clause['quote']}”；{clause['reading']}。"
        summary += "既有旺衰与直接制约保留，整句适用仅指所选条文前提核对，未综合净作用或认证现实成败、日期。"
    from .meihua_obstruction_days import build_obstruction_timing

    obstruction = build_obstruction_timing(
        stages,
        control,
        fact_prefix=fact_prefix,
        interpretation_prefix=interpretation_prefix,
        matter_scenario=matter_scenario,
        scenario_fact_path=scenario_fact_path,
    )
    summary += obstruction["summary"]
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": stage_emphasis_ruleset(),
        "body": stages[0]["body"],
        "reference_body": "original_static_body_of_this_candidate",
        "matter_scenario": matter_scenario or "not_collected",
        "scenario_declaration": (
            {
                "value": matter_scenario,
                "status": "caller_declared_unverified",
                "fact_path": scenario_fact_path,
                "scope": "source_subject_category_not_desired_answer_or_observed_outcome",
            }
            if matter_scenario is not None
            else None
        ),
        "stage_emphasis": {
            "rule_id": "stage_emphasis_order",
            "quote": rules["stage_emphasis_order"]["quote"],
            "ordered_layers": [
                {"stage": "initial", "roles": ["use"]},
                {"stage": "middle", "roles": ["body_mutual", "use_mutual"]},
                {"stage": "final", "roles": ["changed_use"]},
            ],
            "middle_rule_id": "mutual_emphasis_order",
            "middle_quote": rules["mutual_emphasis_order"]["quote"],
            "middle_ordered_roles": ["body_mutual", "use_mutual"],
            "numeric_weights": None,
        },
        "roles": roles,
        "generation_roles": generation,
        "control_roles": attackers,
        "relative_generation_clauses": clauses,
        "mixed_generation_control": mixed,
        "scenario_clauses": scenario_clauses,
        "obstruction_timing": obstruction,
        "selected_support_role": None,
        "net_effect_weight": None,
        "event_time": None,
        "real_outcome": None,
        "scope": (
            "selected_inner_role_conditions_only; scenario, mutual phrase scope and net effects not adjudicated"
            if matter_scenario is None
            else "selected_inner_role_conditions_under_caller_declared_scenario; mutual phrase scope and net effects not adjudicated"
        ),
        "summary": summary,
    }


def apply_stage_emphasis(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    *,
    matter_scenario: str | None = None,
    scenario_fact_path: str = "input_normalized.matter_scenario",
) -> None:
    """Annotate completed readings; keep geometry, prior clauses and policies."""
    interpretation["stage_emphasis"] = None
    if matter_scenario not in {None, "favorable_matter", "unfavorable_matter"}:
        raise ValueError("Unknown declared source matter scenario")
    if interpretation["interpretation_topic"] == "weather":
        if matter_scenario is not None:
            raise ValueError("Weather has no human-matter body/use scenario")
        return
    layer = _reading(
        cast["stage_relations"],
        interpretation["internal_countercontrol"],
        cast.get("seasonal_strength"),
        fact_prefix="meihua",
        interpretation_prefix="interpretation",
        matter_scenario=matter_scenario,
        scenario_fact_path=scenario_fact_path,
    )
    interpretation["stage_emphasis"] = layer
    suffix = layer["summary"]
    for index, candidate in enumerate(interpretation.get("casting_readings") or []):
        row = _reading(
            candidate["stage_relations"],
            candidate["internal_countercontrol"],
            candidate["seasonal_strength"],
            fact_prefix=f"meihua.counting_variants.{index}",
            interpretation_prefix=f"interpretation.casting_readings.{index}",
            matter_scenario=matter_scenario,
            scenario_fact_path=scenario_fact_path,
        )
        candidate["stage_emphasis"] = row
        label = (
            "原数口径" if candidate["line_sum_basis"] == "raw_counts" else "卦序数口径"
        )
        suffix += label + "紧次与迟速条件另核：" + row["summary"]
    interpretation["evidence_scope"][
        "stage_emphasis"
    ] = "selected_NLC1925_ordinal_emphasis_and_conditional_relative_wording; no scenario inference or net verdict"
    interpretation["comprehensive_judgement"] += suffix
