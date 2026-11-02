"""Selected internal cross-control clauses, retaining every original relation.

Role occurrences share a diagram; they are not independent observations. Only
direct control qualifies support or attack. No recursive cancellation or vote.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role
from fatebridge.core.meihua_roles import LABELS, ROLES


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/internal-control-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_internal_control_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown internal Meihua control profile")
    return profile


def internal_control_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def build_internal_countercontrol(
    stages: list[dict[str, Any]], *, fact_prefix: str = "meihua"
) -> dict[str, Any]:
    """Inspect actual original-body/use/mutual/changed-use role occurrences."""
    if [row["role"] for row in stages] != list(ROLES):
        raise ValueError(
            "Internal control requires all four actual stage roles in order"
        )
    first = stages[0]
    nodes = [
        {
            "role": "body",
            "trigram": first["body"],
            "element": first["body_element"],
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
    edges = [
        {
            "controller_role": a["role"],
            "target_role": b["role"],
            "controller_fact_path": a["fact_path"],
            "target_fact_path": b["fact_path"],
            "controller_relation_to_body": a["relation_to_body"],
            "relation": "克",
        }
        for a in nodes
        for b in nodes
        if a["role"] != b["role"]
        and relationship_by_role(b["element"], a["element"]) == "用克体"
    ]
    incoming = {
        n["role"]: [
            e["controller_role"] for e in edges if e["target_role"] == n["role"]
        ]
        for n in nodes
    }
    for edge in edges:
        edge["controller_itself_controlled_by_roles"] = incoming[
            edge["controller_role"]
        ]
    by_role = {n["role"]: n for n in nodes}
    rules = {r["relation"]: r for r in _profile()["rules"]}
    qualifications = []
    parts = []
    for row in stages:
        rule = rules.get(row["relation"])
        controllers = incoming[row["role"]]
        matched = rule is not None and bool(controllers)
        qualification = (
            rule["qualification"]
            if rule is not None and controllers
            else (
                "no_direct_control_in_selected_scope"
                if rule is not None
                else "outside_two_selected_clauses"
            )
        )
        text = None
        if matched:
            actor = "、".join(LABELS[c] + by_role[c]["trigram"] for c in controllers)
            target = LABELS[row["role"]] + row["trigram"]
            text = (
                f"{target}生体而受{actor}制约，所列生助受到限制。"
                if qualification == "support_constrained"
                else f"{target}克体而受{actor}制约，原文取稍解其凶，仍保留原有克体。"
            )
            leaking = [
                c for c in controllers if by_role[c]["relation_to_body"] == "体生用"
            ]
            if leaking:
                text += (
                    "其中"
                    + "、".join(LABELS[c] + by_role[c]["trigram"] for c in leaking)
                    + "对原体同时为体生用，耗泄关系仍须同看。"
                )
            parts.append(text)
        qualifications.append(
            {
                "role": row["role"],
                "original_relation_to_body": row["relation"],
                "target_fact_path": row["fact_path"],
                "incoming_controller_roles": controllers,
                "qualification": qualification,
                "rule_id": rule["id"] if rule is not None and controllers else None,
                "quote": rule["quote"] if rule is not None and controllers else None,
                "reading": text,
            }
        )
    summary = "".join(parts)
    if parts:
        summary += "上述为所列内卦的直接制约，尚未裁定多层制约、季令与外应的综合结果。"
    else:
        summary = (
            "所列内卦未触发这两条生体受制或克体受制条款；外应及其他综合条件仍未核定。"
        )
    return {
        "ruleset_id": _profile()["id"],
        "version": _profile()["version"],
        "ruleset": internal_control_ruleset(),
        "scope": "original_body_and_four_auxiliary_role_occurrences_static_body_once",
        "nodes": nodes,
        "directed_role_pairs_evaluated": 20,
        "control_edges": edges,
        "qualifications": qualifications,
        "summary": summary,
        "recursive_cancellation_applied": False,
        "seasonal_strength_used_to_disable_control": False,
        "full_internal_external_synthesis": "not_computed",
        "net_verdict": None,
        "event_time": None,
        "success_probability": None,
        "real_world_efficacy": "not_established",
    }
