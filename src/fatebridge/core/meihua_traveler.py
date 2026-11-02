"""Selected 行人 clauses with separate original-body and initial-use frames."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role
from fatebridge.core.meihua_roles import LABELS, ROLES

from .meihua_countercontrol import build_internal_countercontrol
from .meihua_qualified_motion import build_qualified_motion

TRAVELER_TOPIC = "traveler"
_TARGET_RELATIONS = {
    "体用比和": "same_element",
    "体生用": "target_generates_actor",
    "体克用": "target_controls_actor",
    "用生体": "actor_generates_target",
    "用克体": "actor_controls_target",
}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/traveler-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_traveler_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 5
        or {r["relation"] for r in profile["rules"]} != set(_TARGET_RELATIONS)
        or len(profile["supplement_rules"]) != 6
        or profile["selection_policy"]["target_role"] != "use"
    ):
        raise ValueError("Unknown or incomplete selected traveler profile")
    return profile


def traveler_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def traveler_qualifications(
    cast: dict[str, Any],
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    *,
    fact_prefix: str,
    strength_prefix: str,
) -> dict[str, Any]:
    """Evaluate directed atoms against initial use; never rename the original body."""
    if [r["role"] for r in stages] != list(ROLES):
        raise ValueError("Traveler frame requires all four actual stage roles")
    profile = _profile()
    target = cast["use_trigram"]
    initial = stages[0]
    if (initial["trigram"], initial["element"], initial["fact_path"]) != (
        target["name"],
        target["element"],
        fact_prefix + ".use_trigram",
    ):
        raise ValueError("Traveler target must be this candidate's original use")
    control = build_internal_countercontrol(stages, fact_prefix=fact_prefix)
    nodes = control["nodes"]
    incoming = {
        n["role"]: [
            e["controller_role"]
            for e in control["control_edges"]
            if e["target_role"] == n["role"]
        ]
        for n in nodes
    }
    actors = [
        {
            **deepcopy(n),
            "relation_to_initial_use": _TARGET_RELATIONS[
                relationship_by_role(target["element"], n["element"])
            ],
            "target_role": "use",
            "target_fact_path": fact_prefix + ".use_trigram",
            "controlled_by_roles": incoming[n["role"]],
        }
        for n in nodes
        if n["role"] != "use"
    ]
    generators = [
        n for n in actors if n["relation_to_initial_use"] == "actor_generates_target"
    ]
    controllers = [
        n for n in actors if n["relation_to_initial_use"] == "actor_controls_target"
    ]
    strength = None
    strength_path = None
    if seasonal is not None:
        index = next(
            i for i, r in enumerate(seasonal["trigrams"]) if r["role"] == "use"
        )
        row = seasonal["trigrams"][index]
        if (row["trigram"], row["element"], row["fact_path"]) != (
            target["name"],
            target["element"],
            fact_prefix + ".use_trigram",
        ):
            raise ValueError("Traveler strength must belong to this candidate's use")
        strength = row["strength"]
        strength_path = f"{strength_prefix}.trigrams.{index}.strength"
    weak = True if strength == "衰" else False if strength == "旺" else None
    controlled = bool(controllers)
    # Three-valued conjunction; 原文未定 is unknown, not the opposite of 衰.
    weak_controlled = (
        False if weak is False or not controlled else True if weak is True else None
    )
    rules = {r["id"]: r for r in profile["supplement_rules"]}
    received = {
        **deepcopy(rules["traveler_receives_generation"]),
        "selected_scope_condition": bool(generators),
        "full_clause_condition": None,
        "full_clause_status": "pending_complete_actor_scope_and_strength_synthesis",
        "actor_roles": [r["role"] for r in generators],
        "actor_fact_paths": [r["fact_path"] for r in generators],
        "controlled_actor_roles": [
            r["role"] for r in generators if r["controlled_by_roles"]
        ],
        "net_support_established": False,
    }
    weak_clause = {
        **deepcopy(rules["traveler_weak_and_controlled"]),
        "use_weak": weak,
        "use_controlled_in_selected_scope": controlled,
        "selected_scope_condition": weak_controlled,
        "full_clause_condition": None,
        "full_clause_status": "pending_complete_actor_scope_and_strength_synthesis",
        "actor_roles": [r["role"] for r in controllers],
        "actor_fact_paths": [r["fact_path"] for r in controllers],
        "real_hazard_verdict": None,
    }
    positions = [
        {"trigram": cast[k][p]["name"], "fact_path": f"{fact_prefix}.{k}.{p}.name"}
        for k in ("base_hexagram", "mutual_hexagram", "changed_hexagram")
        for p in ("lower", "upper")
    ]
    five = Counter(n["trigram"] for n in nodes)
    six = Counter(n["trigram"] for n in positions)
    many = [
        {
            **deepcopy(rules[key]),
            "five_role_count": five[trigram],
            "six_position_count": six[trigram],
            "selected_scope_condition": None,
            "full_clause_condition": None,
            "threshold": None,
            "status": "pending_many_threshold_and_scope",
        }
        for key, trigram in (("traveler_zhen_many", "震"), ("traveler_gen_many", "艮"))
    ]
    symbols = [
        {
            **deepcopy(rules[key]),
            "selected_role": "use",
            "trigram_fact_path": fact_prefix + ".use_trigram.name",
            "selected_scope_condition": target["name"] == trigram,
            "full_clause_condition": None,
            "full_source_role_scope_adjudicated": False,
            "real_hazard_or_dispute_verdict": None,
        }
        for key, trigram in (("traveler_kan", "坎"), ("traveler_dui", "兑"))
    ]
    support_names = "、".join(LABELS[r["role"]] + r["trigram"] for r in generators)
    attack_names = "、".join(LABELS[r["role"]] + r["trigram"] for r in controllers)
    qualified = build_qualified_motion(cast, "traveler", fact_prefix=fact_prefix)
    summary = (
        f"行人在外补充另以初用{target['name']}为受作用者，原体{cast['body_trigram']['name']}及原生克方向保留。"
        + (
            f"所列{support_names}生初用，触及逢生句；受制另列，未定净生助。"
            if generators
            else "所列四个内卦角色未见生初用，不等于完整内外无生助。"
        )
        + f"初用月令标记为{strength or '未知'}，"
        + (f"受{attack_names}克；" if controllers else "所列范围未见受克；")
        + f"逢衰且受克条件在此范围为{'成立' if weak_controlled is True else '不同时成立' if weak_controlled is False else '待所需旺衰'}。"
        + "震多、艮多的门槛与范围未裁定；坎兑句只另列初用经卦读法，不替换为互卦或变用。"
        + "归迟、未归、即归及不日未换算日期；没有核实返归、行踪、安全、灾害或争端，不生成现实结局。"
        + qualified["summary"]
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "source": deepcopy(profile["source"]),
        "section": "行人占第十三",
        "qualitative_motion": qualified,
        "supplement_header": deepcopy(profile["supplement_header"]),
        "selection_policy": deepcopy(profile["selection_policy"]),
        "original_body_frame": {
            "body": cast["body_trigram"]["name"],
            "body_fact_path": fact_prefix + ".body_trigram",
            "initial_relation": initial["relation"],
            "initial_relation_fact_path": fact_prefix + ".stage_relations.0.relation",
            "preserved_without_reversal": True,
        },
        "initial_use_frame": {
            "target_role": "use",
            "target_trigram": target["name"],
            "target_element": target["element"],
            "target_fact_path": fact_prefix + ".use_trigram",
            "actors": actors,
            "directed_control_edges": deepcopy(control["control_edges"]),
            "recursive_cancellation_applied": False,
            "month_branch": seasonal["month_branch"] if seasonal is not None else None,
            "actual_strength": strength,
            "strength_fact_path": strength_path,
            "full_year_month_day_strength_synthesis": "not_computed",
            "external_observations_rebased_to_use": False,
        },
        "received_generation": received,
        "weak_and_controlled": weak_clause,
        "many_clauses": many,
        "initial_use_symbols": symbols,
        "frequency_diagnostics": {
            "five_roles_static_body_once": dict(five),
            "six_positions": dict(six),
            "position_records": positions,
            "counts_are_independent_evidence": False,
        },
        "all_supplement_rules_retained": len(rules),
        "full_chapter_synthesis": "not_computed",
        "event_time": None,
        "return_verified": None,
        "real_location": None,
        "hazard_verdict": None,
        "success_probability": None,
        "real_outcome": None,
        "summary": summary,
    }
