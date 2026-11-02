"""Directed chapter-14 control conditions; no condition-count strength vote."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_metal_change import outgoing_blocker
from .liuyao_metal_moving import moving_growth_qualified
from .liuyao_month_break import day_value_exception, month_opposition_applies
from .liuyao_moving_si import INTERNAL_KEY as MOVING_SI_KEY
from .liuyao_moving_si import moving_si_context, qualify_control
from .liuyao_penalty import INTERNAL_KEY, penalty_context, qualify_yin_generation
from .liuyao_relations import branch_facts, element_relation, xunkong
from .liuyao_rescue import build_back_generation_conditions
from .liuyao_strength import active, calendar_conditions
from .liuyao_void_control import ROOT as VOID_FILL_ROOT
from .liuyao_void_control import current_void_fill_control, qualification_evidence

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-control-v9.json")
    .read_text(encoding="utf-8")
)


def build_control_conditions(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    stages: dict[str, dict[str, str]],
    activity_overrides: set[int] | None = None,
    back_generation_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ordered = sorted(lines, key=lambda r: r["position"])
    rows = {r["position"]: r for r in ordered}
    cs = {r["position"]: dict(r) for r in conditions}
    for p, row in rows.items():
        if MOVING_SI_KEY not in cs[p]:
            context = moving_si_context(
                row, cs[p]["monthly_strength"], month, day_ganzhi, ordered
            )
            if context is not None:
                cs[p][MOVING_SI_KEY] = context
    back_generation_conditions = (
        back_generation_conditions
        or build_back_generation_conditions(
            lines, month, day_ganzhi, conditions=conditions
        )
    )
    back_supports = {r["position"]: r for r in back_generation_conditions["sources"]}
    activity_overrides = activity_overrides or set()
    moving = {p: active(r, cs[p]) or p in activity_overrides for p, r in rows.items()}
    calendars = {
        p: calendar_conditions(
            branch=r["branch"],
            month=month,
            day_ganzhi=day_ganzhi,
            monthly=cs[p]["monthly_strength"],
            metal_moving_support=moving_growth_qualified(cs[p]),
            stages=stages,
            penalty=cs[p].get(INTERNAL_KEY)
            or penalty_context(
                branch=r["branch"],
                month=month,
                day=day_ganzhi[1],
                position=p,
                own_changed=r.get("changed_branch") if r["change"] else None,
                lines=ordered,
                conditions=[cs[q] for q in rows],
            ),
        )
        for p, r in rows.items()
    }
    contexts = {
        p: cs[p].get(INTERNAL_KEY)
        or penalty_context(
            branch=r["branch"],
            month=month,
            day=day_ganzhi[1],
            position=p,
            own_changed=r.get("changed_branch") if r["change"] else None,
            lines=ordered,
            conditions=[cs[q] for q in rows],
        )
        for p, r in rows.items()
    }
    monthly_qualified = {
        p: qualify_yin_generation(
            cs[p]["monthly_strength"]["monthly_supported"], month, contexts[p]
        )
        for p in rows
    }
    calendar_supported: dict[int, bool | None] = {}
    preliminary: dict[int, bool | None] = {}
    reasons: dict[int, list[str]] = {}
    rescue_used: dict[int, bool] = {}
    void_fill_qualified: dict[int, bool] = {}
    void_fill_used: dict[int, bool] = {}
    for p, row in rows.items():
        cal = calendars[p]
        calendar_supported[p] = (
            True
            if cal["supports"] and not cal["oppositions"]
            else None if cal["supports"] or cal["pending_supports"] else False
        )
        facts = branch_facts(row["branch"], month, day_ganzhi[1], xunkong(day_ganzhi))
        reasons[p] = []
        rescue_used[p] = False
        void_fill_used[p] = False
        void_fill_qualified[p] = current_void_fill_control(
            row, facts, cal["oppositions"], day_ganzhi[1]
        )
        if outgoing_blocker(cs[p]) is None:
            preliminary[p] = None
            reasons[p].append("本位金化巳的长生或回头克资格待审")
        elif cs[p].get("outgoing_obstructions"):
            preliminary[p] = False
            reasons[p].append("本位回头克，先审解救")
        elif cs[p]["binding_cues"]:
            preliminary[p] = None
            reasons[p].append("动合未解")
        elif (
            facts["is_xunkong"] and not facts["is_day_clash"]
        ) or month_opposition_applies(row["branch"], month, day_ganzhi[1]):
            preliminary[p] = None
            reasons[p].append("原爻空破，作用条件待审")
        elif (
            cal["oppositions"]
            and back_supports[p]["condition_match"] is not True
            and not void_fill_qualified[p]
        ):
            preliminary[p] = None
            reasons[p].append(
                "日月反制，本位回头生支持未确认，作用条件待审"
                if any(
                    a.get("harm_condition_match", True) is True
                    for a in cal["oppositions"]
                )
                else "三支总作用待审，本位回头生支持未确认，作用条件待审"
            )
        else:
            # Activity, not the source's own 旺相, licenses this condition.
            preliminary[p] = True
            rescue_used[p] = bool(
                cal["oppositions"] and back_supports[p]["condition_match"] is True
            )
            void_fill_used[p] = void_fill_qualified[p] and not rescue_used[p]
    before_activity = dict(preliminary)
    activity_match: dict[int, bool | None] = {}
    for p, row in rows.items():
        if row["change"]:
            activity_match[p] = True
        elif not moving[p]:
            activity_match[p] = False
        elif (
            f := branch_facts(row["branch"], month, day_ganzhi[1], xunkong(day_ganzhi))
        )["is_xunkong"] and f["is_day_clash"]:
            activity_match[p] = True
        elif monthly_qualified[p] is True:
            activity_match[p] = True
        else:
            activity_match[p] = None
        if p in activity_overrides:
            activity_match[p] = None
        if moving[p] and activity_match[p] is None and preliminary[p] is not False:
            preliminary[p] = None
            reasons[p].append("暗动前提的生扶来源待审")
    # Simultaneous moving control cannot be resolved by arbitrary loop order.
    competing = {
        p: [
            q
            for q in rows
            if q != p
            and moving[q]
            and preliminary[q] is not False
            and element_relation(rows[q]["element"], rows[p]["element"]) == "克爻"
        ]
        for p in rows
    }
    available = {
        p: (
            None
            if moving[p] and preliminary[p] is True and competing[p]
            else preliminary[p]
        )
        for p in rows
    }
    before_confirmation = dict(available)
    for p in rows:
        if not moving[p] or activity_match[p] is not None:
            continue
        helpers = (
            cs[p]["supporting_moving_positions"] + cs[p]["supporting_static_positions"]
        )
        if any(
            (
                calendar_supported[h] is True
                or (moving[h] and back_supports[h]["condition_match"] is True)
            )
            and before_confirmation[h] is True
            and (moving[h] or not competing[h])
            and qualify_yin_generation(True, rows[h]["branch"], contexts[p]) is True
            for h in helpers
        ):
            activity_match[p] = True
            preliminary[p] = before_activity[p]
            available[p] = (
                None if preliminary[p] is True and competing[p] else preliminary[p]
            )
            reasons[p].remove("暗动前提的生扶来源待审")
    confirmed: dict[int, list[int]] = {}
    pending: dict[int, list[int]] = {}
    for p in rows:
        confirmed[p] = [q for q in competing[p] if available[q] is True]
        pending[p] = [q for q in competing[p] if available[q] is None]
    controls: list[dict[str, Any]] = []
    for p, source in rows.items():
        for q, target in rows.items():
            if (
                p == q
                or element_relation(source["element"], target["element"]) != "克爻"
            ):
                continue
            source_month = monthly_qualified[p] is True
            target_month = monthly_qualified[q] is True
            if moving[p]:
                match = available[p]
                if match is False:
                    status = "back_control_obstructs_outgoing_candidate"
                elif moving[q]:
                    match, status = None, "active_to_active_requires_arbitration"
                elif match is None:
                    status = "active_control_requires_conditions"
                else:
                    status = (
                        "active_control_supported_by_own_back_generation"
                        if rescue_used[p]
                        else (
                            "current_void_fill_active_control_matched"
                            if void_fill_used[p]
                            else "active_control_condition_matched"
                        )
                    )
                rule = (
                    "active-back-generation-support"
                    if rescue_used[p]
                    else (
                        "current-void-fill-active-control"
                        if void_fill_used[p]
                        else "weak-active-controls-static"
                    )
                )
            else:
                rule = "static-supported-to-weak"
                generators = [
                    k
                    for k in rows
                    if k != p
                    and moving[k]
                    and available[k] is not False
                    and element_relation(rows[k]["element"], source["element"])
                    == "生爻"
                ]
                if moving[q] and activity_match[q] is True:
                    match, status, rule = (
                        False,
                        "static_cannot_control_active",
                        "static-cannot-control-active",
                    )
                elif moving[q]:
                    match, status = None, "target_activity_requires_resolution"
                elif target_month:
                    match, status = False, "static_target_not_seasonally_weak"
                elif day_value_exception(
                    target["branch"], month, day_ganzhi[1]
                ) and not any(
                    k != q
                    and moving[k]
                    and available[k] is not False
                    and element_relation(rows[k]["element"], target["element"])
                    == "克爻"
                    for k in rows
                ):
                    match, status = (
                        False,
                        "static_target_day_value_month_break_exception",
                    )
                elif confirmed[p]:
                    match, status, rule = (
                        False,
                        "active_control_obstructs_static_control",
                        "injured-static-control",
                    )
                elif pending[p]:
                    match, status = None, "static_injury_requires_control_resolution"
                elif calendar_supported[p] is not True:
                    match = (
                        None if calendar_supported[p] is None or generators else False
                    )
                    status = (
                        "static_strength_requires_resolution"
                        if match is None
                        else "static_strength_condition_not_matched"
                    )
                elif calendars[q]["supports"] or calendars[q]["pending_supports"]:
                    match, status = (
                        None,
                        "static_target_calendar_support_requires_strength",
                    )
                else:
                    match, status = True, "static_control_condition_matched"
            index = len(controls)
            match, status, si_qualification = qualify_control(
                source, target, cs[q], available[p], match, status
            )
            controls.append(
                {
                    "source_position": p,
                    "target_position": q,
                    "source_branch": source["branch"],
                    "target_branch": target["branch"],
                    "source_active": moving[p],
                    "target_active": moving[q],
                    "source_activity_match": activity_match[p],
                    "target_activity_match": activity_match[q],
                    "relation": "克爻",
                    "condition_match": match,
                    "status": status,
                    **si_qualification,
                    "source_calendar_supported": calendar_supported[p],
                    "target_calendar_supported": calendar_supported[q],
                    "source_confirmed_active_controllers": confirmed[p],
                    "source_pending_active_controllers": pending[p],
                    "source_competing_active_controls": (
                        competing[p] if moving[p] else []
                    ),
                    "source_obstructions": list(reasons[p]) if moving[p] else [],
                    "source_back_generation_condition": back_supports[p][
                        "condition_match"
                    ],
                    "back_generation_source_path": back_supports[p]["source_path"],
                    "source_rescue_used": rescue_used[p],
                    "source_void_fill_control_condition": void_fill_qualified[p],
                    "source_void_fill_used": void_fill_used[p],
                    "void_fill_qualification_path": VOID_FILL_ROOT,
                    "source_calendar_oppositions": deepcopy(
                        calendars[p]["oppositions"]
                    ),
                    "emit_edge": moving[p]
                    or (
                        not target_month
                        and (source_month or calendar_supported[p] is not False)
                    ),
                    "rule_id": rule,
                    "source_url": PROFILE["source"]["url"]
                    + (
                        "#page=53"
                        if rule == "active-back-generation-support"
                        else (
                            "#page=67"
                            if rule == "current-void-fill-active-control"
                            else (
                                "#page=57"
                                if rule == "static-supported-to-weak"
                                else "#page=58"
                            )
                        )
                    ),
                    "fact_path": f"liuyao_evidence.conditional_analysis.control_conditions.controls.{index}",
                }
            )
    return {
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": PROFILE["source"]["url"] + "#page=58",
        "source_sha256": PROFILE["source"]["sha256"],
        "clauses": deepcopy(PROFILE["clauses"]),
        "textual_issues": deepcopy(PROFILE["textual_issues"]),
        "controls": controls,
        "void_fill_qualification": qualification_evidence(),
        "activity_conditions": [
            {
                "position": p,
                "raw_activity": cs[p]["activity"],
                "activity_condition_match": activity_match[p],
                "status": (
                    "activity_prerequisites_unresolved"
                    if activity_match[p] is None
                    else "active" if activity_match[p] else "static"
                ),
            }
            for p in rows
        ],
        "activity_resolution_passes": 1,
        "unresolved_day_clash_positions": sorted(activity_overrides),
        "back_generation_source_path": "liuyao_evidence.conditional_analysis.back_generation_conditions",
        "support_ruleset_id": back_generation_conditions["ruleset_id"],
        "support_ruleset_version": back_generation_conditions["ruleset_version"],
        "adjudication": "directed_control_conditions_only",
        "scope": "动克静不先要求动爻自身旺相；静爻克休囚静爻另审自身受克，静爻不能克活动爻。condition_match为已列作用条件，不是最终受伤或事件成败；日月扶克、空破合绊及多动制化未决保留未知。受伤静爻只限制向外克，不泛化为所有生扶归零或永久无用。",
    }
