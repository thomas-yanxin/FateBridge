"""NLC1925 trigram-specific imagery, bound to each actual original-body role.

Raw support/control selects a historical clause. It never selects a real person,
an observed event, a hazard verdict or an effective net result.
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
        .joinpath("meihua/trigram-symbols-nlc1925-v1.json")
        .read_text(encoding="utf-8")
    )
    expected = {(t, r) for t in "乾兑离震巽坎艮坤" for r in ("用生体", "用克体")}
    if (
        profile["id"] != "meihua_trigram_relation_symbols_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 16
        or {(r["trigram"], r["relation"]) for r in profile["rules"]} != expected
        or len({r["id"] for r in profile["rules"]}) != 16
    ):
        raise ValueError("Retain all eight trigram-specific support/control pairs")
    return profile


def trigram_symbols_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _layer(
    stages: list[dict[str, Any]],
    control: dict[str, Any],
    seasonal: dict[str, Any],
    *,
    fact_prefix: str,
    interpretation_prefix: str,
) -> dict[str, Any]:
    if (
        [r["role"] for r in stages] != list(ROLES)
        or [r["role"] for r in control["qualifications"]] != list(ROLES)
        or [r["role"] for r in control["nodes"]] != ["body", *ROLES]
        or [r["role"] for r in seasonal["roles"]] != ["body", *ROLES]
    ):
        raise ValueError("Symbol imagery requires the four actual roles in order")
    body = stages[0]["body"]
    if (control["nodes"][0]["trigram"], control["nodes"][0]["fact_path"]) != (
        body,
        fact_prefix + ".body_trigram",
    ) or any(
        (n["trigram"], n["element"], n["relation_to_body"], n["fact_path"])
        != (r["trigram"], r["element"], r["relation"], r["fact_path"])
        for n, r in zip(control["nodes"][1:], stages, strict=True)
    ):
        raise ValueError("Trigram-symbol control context belongs to another cast")
    if (seasonal["roles"][0]["trigram"], seasonal["roles"][0]["fact_path"]) != (
        body,
        fact_prefix + ".body_trigram",
    ):
        raise ValueError("Trigram-symbol strength context belongs to another cast")
    rules = {(r["trigram"], r["relation"]): r for r in _profile()["rules"]}
    evaluations = []
    for index, (stage, qualification, strength) in enumerate(
        zip(stages, control["qualifications"], seasonal["roles"][1:], strict=True)
    ):
        if (
            stage["body"] != body
            or qualification["original_relation_to_body"] != stage["relation"]
            or qualification["target_fact_path"] != stage["fact_path"]
            or (
                strength["trigram"],
                strength["relation_to_body"],
                strength["fact_path"],
            )
            != (stage["trigram"], stage["relation"], stage["fact_path"])
            or not stage["fact_path"].startswith(fact_prefix + ".")
        ):
            raise ValueError("Symbol, control and strength facts must share one cast")
        rule = rules.get((stage["trigram"], stage["relation"]))
        evaluations.append(
            {
                "role": stage["role"],
                "stage": stage["stage"],
                "body": body,
                "trigram": stage["trigram"],
                "relation": stage["relation"],
                "body_fact_path": fact_prefix + ".body_trigram.name",
                "trigram_fact_path": stage["fact_path"] + ".name",
                "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
                "status": (
                    "matched_raw_relation" if rule else "outside_selected_relations"
                ),
                "clause_id": rule["id"] if rule else None,
                "quote": rule["quote"] if rule else None,
                "source_pdf_indices": deepcopy(rule["pdf_indices"]) if rule else [],
                "quote_scope": (
                    "historical_alternative_imagery_not_observed_event"
                    if rule
                    else None
                ),
                "internal_control_qualification": deepcopy(qualification),
                "control_fact_path": f"{interpretation_prefix}.internal_countercontrol.qualifications.{index}",
                "strength": strength["strength"],
                "strength_status": strength["strength_status"],
                "strength_fact_path": f"{interpretation_prefix}.seasonal_qualification.roles.{index+1}.strength",
                "effective_net_imagery": None,
                "real_person_or_event_inferred": False,
            }
        )
    matched = [r for r in evaluations if r["clause_id"] is not None]
    return {
        "body": body,
        "body_fact_path": fact_prefix + ".body_trigram.name",
        "fact_prefix": fact_prefix,
        "role_evaluations": evaluations,
        "matched_clause_ids": [r["clause_id"] for r in matched],
        "generating_roles": [r["role"] for r in matched if r["relation"] == "用生体"],
        "controlling_roles": [r["role"] for r in matched if r["relation"] == "用克体"],
        "closing_clause_automatically_applied": False,
        "summary": (
            "、".join(LABELS[r["role"]] + r["trigram"] + r["relation"] for r in matched)
            + "的八卦专属史料象义已分列。"
            if matched
            else "所列角色未匹配这16项生体或克体象义；不反推不存在其他生克。"
        )
        + "原文或字保留为备选列举，受制与旺衰另核，未识别现实人物、事件或净吉凶。",
        "net_verdict": None,
        "event_time": None,
        "success_probability": None,
    }


def apply_trigram_relation_symbols(
    cast: dict[str, Any], interpretation: dict[str, Any]
) -> None:
    """Add one evidence field; preserve all old facts, summaries and candidates."""
    interpretation["trigram_relation_symbols"] = None
    if interpretation["interpretation_topic"] == "weather":
        return
    selected = _layer(
        cast["stage_relations"],
        interpretation["internal_countercontrol"],
        interpretation["seasonal_qualification"],
        fact_prefix="meihua",
        interpretation_prefix="interpretation",
    )
    candidates = []
    for index, row in enumerate(interpretation.get("casting_readings") or []):
        candidates.append(
            {
                "candidate_index": index,
                "line_sum_basis": row["line_sum_basis"],
                "selected": row["selected"],
                "reading": _layer(
                    row["stage_relations"],
                    row["internal_countercontrol"],
                    row["seasonal_qualification"],
                    fact_prefix=f"meihua.counting_variants.{index}",
                    interpretation_prefix=f"interpretation.casting_readings.{index}",
                ),
            }
        )
    interpretation["trigram_relation_symbols"] = {
        "ruleset_id": _profile()["id"],
        "version": _profile()["version"],
        "ruleset": trigram_symbols_ruleset(),
        "selected": selected,
        "counting_candidates": candidates,
        "scope": "original body against four actual auxiliary role occurrences; each candidate owns its body and qualifiers; weather excluded",
        "source_interpretation": "或 alternatives retained; no automated choice of actual direction/person/property/event",
        "source_variants_used_to_override_selected_edition": False,
        "repeated_roles_are_independent_observations": False,
        "effective_role_or_global_synthesis": "not_computed",
        "real_world_efficacy": "not_established",
        "real_outcome": None,
        "event_time": None,
        "success_probability": None,
    }
