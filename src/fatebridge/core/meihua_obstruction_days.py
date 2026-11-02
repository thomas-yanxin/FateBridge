"""Source day counts for mixed support/control, without a net event date."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.hexagram_relations import relationship_by_role
from fatebridge.core.meihua_roles import ROLES


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/obstruction-days-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        value["id"] != "meihua_obstruction_days_nlc1925_v1"
        or value["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected obstruction-day profile")
    return value


def build_obstruction_timing(
    stages: list[dict[str, Any]],
    control: dict[str, Any],
    *,
    fact_prefix: str,
    interpretation_prefix: str,
    matter_scenario: str | None,
    scenario_fact_path: str,
) -> dict[str, Any]:
    """Use each candidate's raw relations; retain countercontrol separately."""
    if [r["role"] for r in stages] != list(ROLES):
        raise ValueError("Obstruction timing requires four actual stage roles")
    if matter_scenario not in {None, "favorable_matter", "unfavorable_matter"}:
        raise ValueError("Unknown declared source matter scenario")
    profile = _profile()
    first = stages[0]
    if profile["body_elements"].get(first["body"]) != first["body_element"]:
        raise ValueError("Original body trigram and element disagree")
    qualifications = control["qualifications"]
    if [r["role"] for r in qualifications] != list(ROLES):
        raise ValueError("Countercontrol roles must remain bound to this candidate")
    for index, row in enumerate(stages):
        if (
            row["body"],
            row["body_element"],
            profile["body_elements"].get(row["trigram"]),
            relationship_by_role(first["body_element"], row["element"]),
        ) != (
            first["body"],
            first["body_element"],
            row["element"],
            row["relation"],
        ) or not row[
            "fact_path"
        ].startswith(
            fact_prefix + "."
        ):
            raise ValueError(
                "Timing must use this candidate's actual body and relations"
            )
        qualification = qualifications[index]
        if (
            qualification["original_relation_to_body"],
            qualification["target_fact_path"],
        ) != (row["relation"], row["fact_path"]):
            raise ValueError("Timing and countercontrol facts must remain bound")
    generation = [r["role"] for r in stages if r["relation"] == "用生体"]
    attackers = [r for r in stages if r["relation"] == "用克体"]
    structural = bool(generation and attackers)
    scenario_met = (
        None if matter_scenario is None else matter_scenario == "favorable_matter"
    )
    applies = (
        False if not structural else None if scenario_met is None else scenario_met
    )
    records = []
    groups: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(stages):
        if row["relation"] != "用克体":
            continue
        name = row["trigram"]
        days = profile["trigram_numbers"][name]
        basis = (
            "explicit_source_example"
            if name in profile["explicit_day_examples"]
            else "derived_by_source_analogy"
        )
        records.append(
            {
                "role": row["role"],
                "trigram": name,
                "element": row["element"],
                "fact_path": row["fact_path"],
                "relation": row["relation"],
                "relation_fact_path": f"{fact_prefix}.stage_relations.{index}.relation",
                "nominal_source_day_count": days,
                "day_count_basis": basis,
                "selected_clause_applies": applies,
                "applied_source_day_count": days if applies is True else None,
                "countercontrol_qualification": deepcopy(qualifications[index]),
                "countercontrol_fact_path": f"{interpretation_prefix}.internal_countercontrol.qualifications.{index}",
                "net_effective_delay": None,
            }
        )
        group = groups.setdefault(
            name,
            {
                "trigram": name,
                "nominal_source_day_count": days,
                "day_count_basis": basis,
                "roles": [],
            },
        )
        group["roles"].append(row["role"])
    summary = ""
    if applies is True:
        counts = "、".join(
            f"{g['trigram']}所列{g['nominal_source_day_count']}日"
            + (
                "（按类推句及卦数推得）"
                if g["day_count_basis"] == "derived_by_source_analogy"
                else "（原句明例）"
            )
            for g in groups.values()
        )
        summary = (
            "所报问吉事情境下，本候选内卦同时见生体与克体；所选阻节计日句对应"
            + counts
            + "。这是条件化原文日数；同卦重复角色不累加，多卦日数不合并，既有制约与旺衰仍须另核。未据此确定净延迟、起算日、完成日期或现实成败。"
        )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": deepcopy(profile),
        "original_body": {
            "trigram": first["body"],
            "element": first["body_element"],
            "fact_path": fact_prefix + ".body_trigram",
        },
        "required_scenario": "favorable_matter",
        "declared_scenario": matter_scenario,
        "scenario_fact_path": (
            scenario_fact_path if matter_scenario is not None else None
        ),
        "scenario_condition_met": scenario_met,
        "generation_roles": generation,
        "generation_relation_fact_paths": [
            f"{fact_prefix}.stage_relations.{i}.relation"
            for i, r in enumerate(stages)
            if r["relation"] == "用生体"
        ],
        "control_roles": [r["role"] for r in attackers],
        "structural_condition_met": structural,
        "selected_clause_applies": applies,
        "condition_scope": "selected_raw_internal_relations_and_declared_scenario_not_net_effect_or_real_outcome",
        "attacker_records": records,
        "distinct_trigram_day_candidates": list(groups.values()),
        "activated_day_candidates": (
            deepcopy(list(groups.values())) if applies is True else []
        ),
        "unit": "source_day_not_elapsed_24_hour_guarantee",
        "multiple_role_delays_summed": False,
        "selected_single_delay": None,
        "net_effective_delay": None,
        "calendar_anchor": None,
        "inclusive_counting_convention": None,
        "event_time": None,
        "real_outcome": None,
        "independent_verified_observations": 0,
        "summary": summary,
    }
