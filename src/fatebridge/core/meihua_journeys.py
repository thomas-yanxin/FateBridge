"""NLC1925 travel/meeting clauses and explicitly scoped travel preferences."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .meihua_qualified_motion import build_qualified_motion

JOURNEY_TOPICS = ("travel", "meeting")
_RELATIONS = ("体克用", "用克体", "体生用", "用生体", "体用比和")


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/journeys-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_journey_clauses_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 10
        or {(r["topic"], r["relation"]) for r in profile["rules"]}
        != {(t, r) for t in JOURNEY_TOPICS for r in _RELATIONS}
    ):
        raise ValueError("Unknown or incomplete selected journey chapter profile")
    return profile


def journey_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def travel_qualifications(
    cast: dict[str, Any],
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    *,
    fact_prefix: str,
    strength_prefix: str,
    interpretation_prefix: str,
) -> dict[str, Any]:
    """Preferences use this candidate; unclear 多/role scopes never become votes."""
    profile = _profile()
    body = cast["body_trigram"]
    strength = (
        next(row for row in seasonal["trigrams"] if row["role"] == "body")["strength"]
        if seasonal is not None
        else None
    )
    known = strength in {"旺", "衰"}
    roles = [
        {
            "role": "body",
            "trigram": body["name"],
            "fact_path": fact_prefix + ".body_trigram",
        },
        *[
            {key: row[key] for key in ["role", "trigram", "fact_path"]}
            for row in stages
        ],
    ]
    positions = [
        {
            "trigram": cast[key][position]["name"],
            "fact_path": f"{fact_prefix}.{key}.{position}",
        }
        for key in ["base_hexagram", "mutual_hexagram", "changed_hexagram"]
        for position in ["lower", "upper"]
    ]
    five = Counter(row["trigram"] for row in roles)
    six = Counter(row["trigram"] for row in positions)
    qualified = build_qualified_motion(cast, "travel", fact_prefix=fact_prefix)
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "source": deepcopy(profile["source"]),
        "section": "出行占第十二",
        "qualitative_motion": qualified,
        "body_strength_preference": {
            "quote": "體宜乘旺",
            "body": body["name"],
            "body_fact_path": fact_prefix + ".body_trigram",
            "reported_month_branch": (
                seasonal["month_branch"] if seasonal is not None else None
            ),
            "actual_strength": strength,
            "strength_fact_path": (
                strength_prefix + ".trigrams.0.strength"
                if seasonal is not None
                else None
            ),
            "preferred_strength": "旺",
            "status": (
                "preference_met"
                if strength == "旺"
                else "preference_not_met" if known else "pending_known_strength"
            ),
            "is_travel_permission_or_safety_gate": False,
        },
        "auxiliary_preferences": [
            {
                "quote": "諸卦宜生體",
                "role": row["role"],
                "trigram": row["trigram"],
                "relation": row["relation"],
                "fact_path": row["fact_path"],
                "symbolic_generation_present": row["relation"] == "用生体",
                "countercontrol_qualifications_fact_path": (
                    interpretation_prefix + ".internal_countercontrol"
                ),
                "net_support_or_all_roles_requirement_established": False,
            }
            for row in stages
        ],
        "actual_role_occurrences": roles,
        "frequency_diagnostics": {
            "five_roles_original_static_body_once": dict(five),
            "six_base_mutual_changed_positions": dict(six),
            "six_position_records": positions,
            "source_many_threshold_and_denominator_adjudicated": False,
            "counts_used_as_independent_evidence_or_outcome_votes": False,
        },
        "unadjudicated_source_clauses": [
            {
                **deepcopy(clause),
                "status": "pending_source_scope",
                "actual_matching_roles": (
                    [
                        deepcopy(row)
                        for row in roles
                        if row["trigram"] in clause["trigrams"]
                    ]
                    if clause["trigrams"]
                    else None
                ),
                "automatic_outcome_or_travel_mode_selected": False,
            }
            for clause in profile["travel_pending_clauses"]
        ],
        "selected_facsimile_complete_supplement": profile["complete_travel_supplement"],
        "event_time": None,
        "geographic_direction": None,
        "travel_mode_instruction": None,
        "hazard_verdict": None,
        "real_outcome": None,
        "summary": (
            f"出行章另列原体{body['name']}的旺气偏好（"
            + (str(strength) if known else "所需旺衰未知")
            + "）及四个辅助角色各自生体关系，均未合成为出行许可、灾祸、收益或日期；"
            "多字门槛及舟陆等句的角色范围未裁定，不按计票选行止或路线。"
            + qualified["summary"]
        ),
    }
