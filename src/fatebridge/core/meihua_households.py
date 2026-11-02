"""Selected household/dwelling clauses, preserving unresolved source wording."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_roles import LABELS, ROLES

from .meihua import meihua_stage_relations

HOUSEHOLD_TOPICS = ("household", "dwelling")
_RELATIONS = {"体克用", "用克体", "体生用", "用生体", "体用比和"}


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/households-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_household_clauses_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or set(profile["topics"]) != set(HOUSEHOLD_TOPICS)
        or len(profile["rules"]) != 10
        or {(r["topic"], r["relation"]) for r in profile["rules"]}
        != {(topic, relation) for topic in HOUSEHOLD_TOPICS for relation in _RELATIONS}
    ):
        raise ValueError("Unknown or incomplete selected household profile")
    for row in profile["rules"]:
        unresolved = row["topic"] == "household" and row["relation"] == "体用比和"
        if row["source_relation_condition"] is not (None if unresolved else True):
            raise ValueError(
                "Unadjudicated 比利 cannot become an automatic 比和 clause"
            )
        if unresolved and (
            row["quote"] != "體用比利家宅安穩"
            or row["selection_status"] != "unadjudicated_original_relation_term"
        ):
            raise ValueError("Selected 比利 wording and unresolved status must survive")
    return profile


def household_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def household_qualifications(
    cast: dict[str, Any], topic: str, *, fact_prefix: str
) -> dict[str, Any]:
    """Retain actual same-cast generation roles without inferring a net result."""
    if topic not in HOUSEHOLD_TOPICS:
        raise ValueError("Select the household or dwelling chapter explicitly")
    profile = _profile()
    stages = meihua_stage_relations(cast, fact_prefix=fact_prefix)
    if [row["role"] for row in stages] != list(ROLES):
        raise ValueError("Household reference requires all four actual auxiliary roles")
    rule = next(
        row
        for row in profile["rules"]
        if row["topic"] == topic and row["relation"] == stages[0]["relation"]
    )
    cross_reference = None
    summary = ""
    if topic == "household":
        roles = [
            {
                "role": row["role"],
                "trigram": row["trigram"],
                "relation_to_original_body": row["relation"],
                "trigram_fact_path": row["fact_path"] + ".name",
                "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
            }
            for index, row in enumerate(stages)
            if row["relation"] == "用生体"
        ]
        cross_reference = {
            **deepcopy(profile["household_support_reference"]),
            "actual_generation_roles": roles,
            "raw_generation_condition_in_selected_scope": bool(roles),
            "full_source_generation_condition": None,
            "complete_cross_chapter_synthesis": None,
            "net_result": None,
            "role_occurrences_used_as_outcome_votes": False,
        }
        summary = (
            "家宅章另有生体转引句；"
            + (
                "所列"
                + "、".join(LABELS[row["role"]] + row["trigram"] for row in roles)
                + "生原体，触及所列内卦范围的转引条件。"
                if roles
                else "所列四个内卦辅助角色未见生原体，不等于已排除完整内外生助。"
            )
            + "原文转引《人事占》，既有互变、受制、旺衰分别保留，未形成完整跨章净结论。"
        )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "source_relation_condition": rule["source_relation_condition"],
        "source_relation_selection_status": rule["selection_status"],
        "source_term_adjudications": [
            deepcopy(row)
            for row in profile["source_term_adjudications"]
            if row["topic"] == topic
        ],
        "household_support_reference": cross_reference,
        "is_field_fengshui_assessment": False,
        "physical_home_inspection": None,
        "real_residential_safety_verdict": None,
        "real_financial_outcome": None,
        "event_time": None,
        "real_outcome": None,
        "summary": summary,
    }
