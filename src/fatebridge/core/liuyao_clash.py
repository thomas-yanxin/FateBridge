"""Distinct day clash, void filling, day break and conditional moving scatter."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_candidate, activity_condition
from .liuyao_metal_change import INTERNAL_KEY as OWN_SI_KEY
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-clash-v10.json")
    .read_text(encoding="utf-8")
)


def build_clash_conditions(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    assessment: dict[str, Any],
    month: str,
    day_ganzhi: str,
    focus: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    for line in lines:
        p, b = line["position"], line["branch"]
        c = conditions[p - 1]
        strength = assessment["lines"][p - 1]["strength"]
        facts = branch_facts(b, month, day, void)
        actors = []
        if facts["is_day_clash"]:
            actors.append(
                {
                    "location": "day",
                    "position": None,
                    "branch": day,
                    "activity_condition_match": True,
                    "status": "calendar_clash_fact",
                }
            )
        for other in lines:
            q = other["position"]
            if q == p or not activity_candidate(other, conditions[q - 1]):
                continue
            if branch_facts(b, month, other["branch"], void)["is_day_clash"]:
                match = activity_condition(other, conditions[q - 1])
                actors.append(
                    {
                        "location": "visible",
                        "position": q,
                        "branch": other["branch"],
                        "activity_condition_match": match,
                        "status": (
                            "active_clash_candidate"
                            if match is True
                            else "activity_prerequisites_unresolved"
                        ),
                    }
                )
        changed = line.get("changed_branch") if line["change"] else None
        back_clash = bool(
            changed and branch_facts(b, month, changed, void)["is_day_clash"]
        )
        back_control = bool(
            changed and element_relation(ELEMENTS[changed], line["element"]) == "克爻"
        )
        if back_clash:
            actors.append(
                {
                    "location": "changed",
                    "position": p,
                    "branch": changed,
                    "activity_condition_match": True,
                    "status": (
                        "own_back_clash_with_control"
                        if back_control
                        else "own_back_clash_without_control"
                    ),
                }
            )
        qi = (
            None
            if not line["change"] and strength["day_clash_break_condition"] is None
            else (
                True
                if strength["supports"]
                else None if strength["pending_supports"] else False
            )
        )
        if not line["change"]:
            scattered, status = None, "not_applicable_static_original"
        elif not actors:
            scattered, status = False, "no_scatter_collision"
        elif qi is True:
            scattered, status = (
                False,
                "supported_or_qi_moving_not_scattered_by_clash_alone",
            )
        else:
            scattered, status = (
                None,
                "weak_or_pending_moving_scatter_not_automatically_decided",
            )
        day_break = strength["day_clash_break_condition"]
        rows.append(
            {
                "position": p,
                "branch": b,
                "is_day_clash": facts["is_day_clash"],
                "day_void_fill_condition": facts["is_day_clash"]
                and facts["is_xunkong"],
                "day_break_condition": day_break,
                "day_break_status": strength["day_clash_break_status"],
                "day_clash_harm_condition": day_break,
                "moving_scatter_condition": scattered,
                "scatter_status": status,
                "has_confirmed_qi": qi,
                "activity_condition_match": activity_condition(line, c),
                "clash_actors": actors,
                "back_clash": back_clash,
                "back_control": back_control,
                **(
                    {
                        "qualified_back_control_condition": c[OWN_SI_KEY][
                            "qualified_back_control_condition"
                        ],
                        "own_si_growth_source_path": c[OWN_SI_KEY]["source_path"],
                    }
                    if OWN_SI_KEY in c
                    else {}
                ),
                "source_path": f"liuyao_evidence.conditional_analysis.clash_conditions.lines.{p-1}",
            }
        )
    selected = focus["selected"]
    return {
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": PROFILE["source"]["url"] + "#page=85",
        "source_sha256": PROFILE["source"]["sha256"],
        "clauses": deepcopy(PROFILE["clauses"]),
        "textual_issues": deepcopy(PROFILE["textual_issues"]),
        "lines": rows,
        "focus": (
            deepcopy(rows[selected["position"] - 1])
            if selected and selected["location"] == "visible"
            else None
        ),
        "adjudication": "clash_conditions_not_total_effectiveness",
        "scope": "日冲事实、冲空填实、静爻日破与明动冲散分别核对。不散不等于未受日月克或解除回头克；冲实只解除所列空亡门槛。衰动间有散不是必散或经验概率。静爻不套明动散式，同日比和扶冲并见仍审原有根气，未决保持未知。",
    }
