"""Shared own-transformation support gate, not total rescue arbitration."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_month_break import day_value_exception
from .liuyao_penalty import INTERNAL_KEY
from .liuyao_penalty import PROFILE as PENALTY_PROFILE
from .liuyao_penalty import penalty_context, qualify_yin_generation
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-rescue-v12.json")
    .read_text(encoding="utf-8")
)


def own_back_generation(
    row: dict[str, Any], month: str, day_ganzhi: str
) -> dict[str, Any]:
    moving = bool(row["change"])
    changed = row["changed_branch"] if moving else None
    facts = (
        branch_facts(changed, month, day_ganzhi[1], xunkong(day_ganzhi))
        if changed
        else None
    )
    relation = element_relation(ELEMENTS[changed], row["element"]) if changed else None
    if not moving:
        match, status = False, "static_has_no_own_transformed_support"
    elif relation != "生爻":
        match, status = False, "own_transformation_not_back_generation"
    elif facts and (
        (facts["is_xunkong"] and not facts["is_day_clash"]) or facts["is_month_clash"]
    ):
        match, status = None, "own_back_generation_void_or_break_requires_resolution"
    else:
        match, status = True, "own_back_generation_gate_matched"
    p = row["position"]
    return dict(
        position=p,
        branch=row["branch"],
        is_actual_moving=moving,
        changed_branch=changed,
        changed_relation=relation,
        is_back_generation=relation == "生爻",
        condition_match=match,
        status=status,
        changed_void=facts["is_xunkong"] if facts else None,
        changed_day_void_fill=(
            (facts["is_xunkong"] and facts["is_day_clash"]) if facts else None
        ),
        changed_month_break=facts["is_month_clash"] if facts else None,
        changed_calendar_relations=(
            {
                loc: element_relation(ELEMENTS[b], ELEMENTS[changed])
                for loc, b in [("month", month), ("day", day_ganzhi[1])]
            }
            if changed
            else {}
        ),
        source_path=f"liuyao_evidence.conditional_analysis.back_generation_conditions.sources.{p-1}",
    )


def build_back_generation_conditions(
    lines: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    selected: dict[str, Any] | None = None,
    conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sources = [
        own_back_generation(r, month, day_ganzhi)
        for r in sorted(lines, key=lambda r: r["position"])
    ]
    for row, support in zip(sorted(lines, key=lambda r: r["position"]), sources):
        p = row["position"]
        context = (
            conditions[p - 1].get(INTERNAL_KEY) if conditions else None
        ) or penalty_context(
            branch=row["branch"],
            month=month,
            day=day_ganzhi[1],
            position=p,
            own_changed=row.get("changed_branch") if row["change"] else None,
            lines=lines,
            conditions=conditions or [{} for _ in lines],
        )
        raw = support["condition_match"]
        month_qualified = raw
        if (
            raw is None
            and support["is_actual_moving"]
            and support["is_back_generation"]
            and day_value_exception(support["changed_branch"], month, day_ganzhi[1])
            and not support["changed_void"]
        ):
            month_qualified = True
        qualified = qualify_yin_generation(
            month_qualified, support["changed_branch"] or "", context
        )
        support.update(
            raw_condition_match=raw,
            raw_status=support["status"],
            condition_match=qualified,
            month_break_qualified_gate=month_qualified,
            penalty_source_path=context["source_path"],
        )
        if support["is_back_generation"] and qualified is not month_qualified:
            support["status"] = (
                "si_yin_shen_excludes_own_yin_generation"
                if qualified is False
                else "own_yin_generation_triad_activity_pending"
            )
        elif month_qualified is not raw:
            support["status"] = "changed_day_value_excludes_month_only_obstruction"
    focus = (
        deepcopy(sources[selected["position"] - 1])
        if selected and selected["location"] == "visible"
        else None
    )
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        qualification_ruleset_id=PENALTY_PROFILE["ruleset_id"],
        qualification_ruleset_version=PENALTY_PROFILE["ruleset_version"],
        qualification_source_url=PENALTY_PROFILE["source"]["url"] + "#page=98",
        source_sha256=PROFILE["source"]["sha256"],
        source_url=PROFILE["source"]["url"] + "#page=53",
        clauses=deepcopy(PROFILE["clauses"]),
        textual_issues=deepcopy(PROFILE["textual_issues"]),
        sources=sources,
        focus=focus,
        adjudication="same_position_back_generation_gate_only",
        scope="明动本位回头生及变爻空破门槛共用一份同次事实；原门槛另存raw_condition_match，第98页巳寅申特定寅生排除先行。静爻不取变盘同位支。变爻日月生克事实保留，门槛匹配不等于变爻全局无伤或原爻所有反制解除；原爻空破、合绊、多动相克与受作用对象另审。变爻只作用本位，原爻及其他爻不能跨位伤变爻。",
    )
