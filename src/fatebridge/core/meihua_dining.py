"""Dining symbols retain the selected source's direct-control qualifications."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

DINING_TOPIC = "dining"


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/dining-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_dining_clauses_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 5
        or {r["relation"] for r in profile["rules"]}
        != {"体克用", "用克体", "体生用", "用生体", "体用比和"}
        or profile["generation_reference"]["quote"] != "兌坎生身酒肉醉飽"
        or profile["generation_reference"]["source_target_as_original_body_adjudicated"]
        is not False
    ):
        raise ValueError("Unknown or incomplete selected dining profile")
    return profile


def dining_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def dining_qualifications(
    cast: dict[str, Any],
    stages: list[dict[str, Any]],
    control: dict[str, Any],
    *,
    fact_prefix: str,
    interpretation_prefix: str,
) -> dict[str, Any]:
    """Keep raw presence and actual named control, without inferring a meal."""
    profile = _profile()
    nodes = control["nodes"]
    if [n["role"] for n in nodes] != [
        "body",
        "use",
        "body_mutual",
        "use_mutual",
        "changed_use",
    ]:
        raise ValueError("Dining needs the original body and all four auxiliary roles")
    expected_paths = [fact_prefix + ".body_trigram", *[s["fact_path"] for s in stages]]
    expected_names = [cast["body_trigram"]["name"], *[s["trigram"] for s in stages]]
    if [n["fact_path"] for n in nodes] != expected_paths or [
        n["trigram"] for n in nodes
    ] != expected_names:
        raise ValueError("Dining control graph must belong to this candidate")
    by_role = {n["role"]: n for n in nodes}
    positions = [
        {
            "hexagram": key,
            "position": position,
            "trigram": cast[key][position]["name"],
            "fact_path": f"{fact_prefix}.{key}.{position}.name",
        }
        for key in ["base_hexagram", "mutual_hexagram", "changed_hexagram"]
        for position in ["lower", "upper"]
    ]
    if {n["trigram"] for n in nodes} != {p["trigram"] for p in positions}:
        raise ValueError("Dining five-role and six-position presence disagree")
    symbols = []
    summary_parts = []
    for rule in profile["symbol_clauses"]:
        targets = [
            {**deepcopy(n), "trigram_fact_path": n["fact_path"] + ".name"}
            for n in nodes
            if n["trigram"] == rule["trigram"]
        ]
        pairs = []
        for index, edge in enumerate(control["control_edges"]):
            target = by_role[edge["target_role"]]
            actor = by_role[edge["controller_role"]]
            if (
                target["trigram"] == rule["trigram"]
                and actor["trigram"] in rule["controller_trigrams"]
            ):
                pairs.append(
                    {
                        "target_role": target["role"],
                        "target_trigram": target["trigram"],
                        "target_fact_path": target["fact_path"] + ".name",
                        "controller_role": actor["role"],
                        "controller_trigram": actor["trigram"],
                        "controller_fact_path": actor["fact_path"] + ".name",
                        "controller_itself_controlled_by_roles": deepcopy(
                            edge["controller_itself_controlled_by_roles"]
                        ),
                        "control_edge_fact_path": (
                            f"{interpretation_prefix}.internal_countercontrol.control_edges.{index}"
                        ),
                    }
                )
        status = (
            "not_present_in_selected_scope"
            if not targets
            else (
                "directly_controlled_in_selected_scope"
                if pairs
                else "present_without_selected_internal_control"
            )
        )
        symbols.append(
            {
                **deepcopy(rule),
                "symbol_present_in_selected_scope": bool(targets),
                "actual_matching_roles": targets,
                "six_position_matches": [
                    deepcopy(p) for p in positions if p["trigram"] == rule["trigram"]
                ],
                "actual_direct_controller_pairs": pairs,
                "direct_control_condition_in_selected_scope": bool(pairs),
                "qualified_symbol_status": status,
                "many_threshold_required_by_selected_control_sentence": False,
                "seasonal_strength_used_to_disable_direct_control": False,
                "recursive_cancellation_applied": False,
                "complete_internal_external_control_assessment": None,
                "real_food_or_drink_available": None,
            }
        )
        noun = "酒象" if rule["symbol"] == "wine" else "食象"
        summary_parts.append(
            noun
            + (
                "在所列内卦未见"
                if not targets
                else (
                    "在所列内卦出现且触发原文直接制约"
                    if pairs
                    else "在所列内卦出现、未见本条列明的内卦制约"
                )
            )
            + "。"
        )
    generation = {
        **deepcopy(profile["generation_reference"]),
        "source_target_binding": None,
        "original_body": cast["body_trigram"]["name"],
        "original_body_fact_path": fact_prefix + ".body_trigram.name",
        "named_generation_atoms": [
            {
                "trigram": trigram,
                "actual_generating_auxiliary_roles": [
                    {
                        "role": row["role"],
                        "trigram_fact_path": row["fact_path"] + ".name",
                        "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
                    }
                    for index, row in enumerate(stages)
                    if row["trigram"] == trigram and row["relation"] == "用生体"
                ],
            }
            for trigram in profile["generation_reference"]["named_trigrams"]
        ],
        "full_source_clause_applies": None,
        "real_satiety_or_intoxication": None,
    }
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "source_inner_scope": deepcopy(profile["inner_scope_reference"]),
        "actual_five_roles": deepcopy(nodes),
        "actual_six_positions": positions,
        "presence_equal_under_five_roles_and_six_positions": True,
        "role_occurrences_used_as_outcome_votes": False,
        "symbols": symbols,
        "absence_reference": {
            **deepcopy(profile["absence_clause"]),
            "neither_symbol_present_in_selected_scope": not any(
                s["symbol_present_in_selected_scope"] for s in symbols
            ),
            "real_food_and_drink_absence": None,
        },
        "generation_reference": generation,
        "food_and_people_references": {
            **deepcopy(profile["food_and_people_references"]),
            "actual_mutual_roles": [
                {
                    "role": s["role"],
                    "trigram": s["trigram"],
                    "fact_path": s["fact_path"],
                }
                for s in stages
                if s["role"] in {"body_mutual", "use_mutual"}
            ],
            "selected_food_role": None,
            "selected_attendee_mutual_side": None,
            "actual_menu": None,
            "actual_attendees": None,
        },
        "net_result": None,
        "alcohol_consumption_or_dietary_advice": None,
        "event_time": None,
        "real_outcome": None,
        "summary": (
            "饮食补充层按原体与四辅助角色的内卦工作范围另核酒食象："
            + "".join(summary_parts)
            + "所列制约不需要多字门槛，制约者自身受制与季令另列，不递归抵消。"
            "影印生身与转录生体、兑坎的组合及完整内外范围未裁定；"
            "未据此核定实际餐食、饮酒、菜单、席上人物或时间。"
        ),
    }
