"""Selected marriage clauses keep family roles and source ambiguities separate."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

MARRIAGE_TOPIC = "marriage"


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/marriage-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_marriage_clauses_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 5
        or {r["relation"] for r in profile["rules"]}
        != {"体克用", "用克体", "体生用", "用生体", "体用比和"}
        or [r["role"] for r in profile["strength_clauses"]] != ["body", "use"]
        or profile["bili_supplement"]["quote"] != "若體用比利則彼此相就良配無疑"
        or profile["bili_supplement"]["automatic_same_element_supplement"] is not False
    ):
        raise ValueError("Unknown or incomplete selected marriage profile")
    return profile


def marriage_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def marriage_qualifications(
    cast: dict[str, Any],
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    *,
    fact_prefix: str,
    strength_prefix: str,
) -> dict[str, Any]:
    """Evaluate held body/use strength; source scope never becomes a net verdict."""
    if [r["role"] for r in stages] != [
        "use",
        "body_mutual",
        "use_mutual",
        "changed_use",
    ]:
        raise ValueError("Marriage qualifications require all four auxiliary roles")
    profile = _profile()
    strengths = {
        row["role"]: (index, row)
        for index, row in enumerate(seasonal["trigrams"] if seasonal else [])
    }
    families = []
    strength_clauses = []
    for rule in profile["strength_clauses"]:
        role = rule["role"]
        trigram = cast["body_trigram" if role == "body" else "use_trigram"]
        path = fact_prefix + (".body_trigram" if role == "body" else ".use_trigram")
        families.append(
            {
                "role": role,
                "source_family_role": rule["source_family_role"],
                "trigram": trigram["name"],
                "fact_path": path,
                "actual_person_or_gender_assignment": None,
            }
        )
        strength_record = strengths.get(role)
        if strength_record is not None:
            index, actual = strength_record
            if (actual["trigram"], actual["element"], actual["fact_path"]) != (
                trigram["name"],
                trigram["element"],
                path,
            ):
                raise ValueError(
                    "Marriage strength must belong to this candidate's role"
                )
            strength = actual["strength"]
            strength_path = f"{strength_prefix}.trigrams.{index}.strength"
        else:
            strength, strength_path = None, None
        condition = True if strength == "旺" else False if strength == "衰" else None
        strength_clauses.append(
            {
                **deepcopy(rule),
                "trigram": trigram["name"],
                "trigram_fact_path": path,
                "reported_month_branch": seasonal["month_branch"] if seasonal else None,
                "actual_strength": strength,
                "strength_fact_path": strength_path,
                "wang_condition": condition,
                "status": (
                    "condition_met"
                    if condition is True
                    else (
                        "condition_not_met"
                        if condition is False
                        else "pending_known_strength"
                    )
                ),
                "basis": "declared_solar_term_month_policy_not_full_year_month_day_synthesis",
                "actual_household_wealth_or_status": None,
            }
        )
    relation_atoms = []
    for rule in profile["generation_clauses"]:
        matches = [
            {
                "role": row["role"],
                "trigram": row["trigram"],
                "relation": row["relation"],
                "trigram_fact_path": row["fact_path"] + ".name",
                "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
            }
            for index, row in enumerate(stages)
            if row["relation"] == rule["relation_atom"]
        ]
        relation_atoms.append(
            {
                **deepcopy(rule),
                "initial_pair_relation": stages[0]["relation"],
                "initial_pair_relation_fact_path": fact_prefix
                + ".stage_relations.0.relation",
                "initial_pair_atom_present": stages[0]["relation"]
                == rule["relation_atom"],
                "actual_matching_auxiliary_roles": matches,
                "atom_present_in_four_auxiliary_roles": bool(matches),
                "full_source_clause_applies": None,
                "alternatives_combined_as_conjunction": False,
                "real_wealth_dowry_or_proposal_intent": None,
            }
        )
    supplement = {
        **deepcopy(profile["bili_supplement"]),
        "actual_initial_relation": stages[0]["relation"],
        "relation_fact_path": fact_prefix + ".stage_relations.0.relation",
        "initial_same_element": stages[0]["relation"] == "体用比和",
        "source_relation_condition": None,
        "full_source_clause_applies": None,
    }
    strength_summary = "、".join(
        ("原体" if row["role"] == "body" else "初用")
        + row["trigram"]
        + "的旺气条件"
        + (
            "符合"
            if row["wang_condition"] is True
            else "不符" if row["wang_condition"] is False else "待定"
        )
        for row in strength_clauses
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "family_frame": {**deepcopy(profile["family_frame"]), "actual_roles": families},
        "strength_clauses": strength_clauses,
        "generation_relation_atoms": relation_atoms,
        "bili_supplement": supplement,
        "unapplied_historical_person_descriptions": deepcopy(
            profile["unapplied_historical_person_descriptions"]
        ),
        "full_stage_strength_synthesis": None,
        "net_result": None,
        "actual_partner_traits": None,
        "actual_family_wealth": None,
        "real_marriage_or_consent_verdict": None,
        "event_time": None,
        "real_outcome": None,
        "summary": (
            "婚姻补充层依原体为所占之家、初用为所婚之家，分别核对："
            + strength_summary
            + "；这只是所报节月约定下的原文条件，未核实两家财富或门户。"
            "生体、体生另列实际关系成分，或字保留为原文候选，完整角色范围未裁定；"
            "后段比利与转录比和分列，不能自动补成彼此相就、良配无疑。"
            "八卦相貌品行文字只作历史记录，未选定现实人物、特征、意愿或婚姻结果。"
        ),
    }
