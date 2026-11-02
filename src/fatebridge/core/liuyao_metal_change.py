"""Same-edition actual metal->Si qualification, separate from raw control."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from .liuyao_metal_moving import prove_moving_earth_sources
from .liuyao_month_break import month_opposition_applies
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong

INTERNAL_KEY = "_metal_own_si_growth"
PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-metal-own-si-v35.json")
    .read_text(encoding="utf-8")
)


def own_si_context(
    row: dict[str, Any],
    monthly: dict[str, Any],
    month: str,
    day_ganzhi: str,
    lines: list[dict[str, Any]],
    assessment: dict[str, Any] | None = None,
    generation: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not (row["change"] and row["element"] == "金" and row["changed_branch"] == "巳"):
        return None
    p, day = row["position"], day_ganzhi[1]
    path = f"liuyao_evidence.conditional_analysis.growth_conditions.lines.{p-1}.own_changed_si"
    roots = []
    for location, branch in [("month", month), ("day", day)]:
        relation = element_relation(ELEMENTS[branch], "金")
        if relation not in ("生爻", "比和") or (
            location == "month" and monthly["monthly_supported"] is not True
        ):
            continue
        root_path = None
        if assessment is not None:
            supports = assessment["lines"][p - 1]["strength"]["supports"]
            index = next(
                i
                for i, a in enumerate(supports)
                if a["location"] == location and a["branch"] == branch
            )
            root_path = f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p-1}.strength.supports.{index}"
        roots.append(
            dict(
                location=location,
                branch=branch,
                relation=relation,
                source_path=root_path,
            )
        )
    moving = None
    if assessment is not None and generation is not None:
        moving = prove_moving_earth_sources(
            subject_position=p,
            lines=lines,
            assessment=assessment,
            generation=generation,
            source_path=path + ".moving_support",
            profile=PROFILE,
            scope="只核实际化巳金爻以外的独立动土生扶，不用该金爻或巳信用自证。",
        )
    support = True if roots or moving and moving["condition_match"] is True else None
    facts = branch_facts("巳", month, day, xunkong(day_ganzhi))
    void_pending = facts["is_xunkong"] and not facts["is_day_clash"]
    month_pending = month_opposition_applies("巳", month, day)
    admission = None if void_pending or month_pending else True
    match = True if support is True and admission is True else None
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        position=p,
        branch=row["branch"],
        changed_branch="巳",
        is_actual_moving=True,
        raw_back_relation="克爻",
        raw_back_control=True,
        support_condition_match=support,
        calendar_supports=roots,
        **({"moving_support": moving} if moving is not None else {}),
        changed_void=facts["is_xunkong"],
        changed_day_void_fill=facts["is_xunkong"] and facts["is_day_clash"],
        changed_month_break=facts["is_month_clash"],
        changed_current_month_obstruction=month_pending,
        changed_admission_condition=admission,
        condition_match=match,
        qualified_back_control_condition=False if match is True else None,
        status=(
            "independently_supported_own_si_growth"
            if match is True
            else (
                "own_si_admission_requires_resolution"
                if admission is None
                else "own_si_independent_support_not_proven"
            )
        ),
        source_path=path,
        source_url=PROFILE["source"]["url"] + "#page=97",
        source_sha256=PROFILE["source"]["sha256"],
        admission_source_url=PROFILE["source"]["url"] + "#page=53",
        admission_interpretation="结合既有本位变爻空破门槛审当前效力；金化巳的长生条款与这一门槛分列，不冒充原文逐字描述本开发结构。",
        actual_total_effect_adjudicated=False,
        scope="金爻实际本位化巳，有独立生扶才核本项长生；原火克金关系保留，未核不等于全局无扶。只排除同一本位巳火的克，不解除原爻空破合绊、日月及其他动爻反制，不将变巳跨位使用。",
    )


def own_si_pending(condition: dict[str, Any]) -> bool:
    return (
        INTERNAL_KEY in condition and condition[INTERNAL_KEY]["condition_match"] is None
    )


def back_control_condition(
    row: dict[str, Any], condition: dict[str, Any]
) -> bool | None:
    if (
        not row["change"]
        or element_relation(ELEMENTS[row["changed_branch"]], row["element"]) != "克爻"
    ):
        return False
    context = condition.get(INTERNAL_KEY)
    return (
        cast(bool | None, context["qualified_back_control_condition"])
        if context
        else True
    )


def outgoing_blocker(condition: dict[str, Any]) -> bool | None:
    if not condition.get("outgoing_obstructions"):
        return False
    return None if own_si_pending(condition) else True
