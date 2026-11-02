"""Chapter Ten predicates and conditional Yuan/Ji routes, without strength votes."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from itertools import product
from typing import Any

from .liuyao_metal_change import back_control_condition, outgoing_blocker
from .liuyao_month_break import day_value_exception, month_opposition_applies
from .liuyao_penalty import INTERNAL_KEY, qualify_yin_generation
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong
from .liuyao_stages import query_stage

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-effects-v4.json")
    .read_text(encoding="utf-8")
)


def evaluate(predicate: Any, atoms: dict[str, bool | None]) -> bool | None:
    """Kleene all/any: unknown strength must not become false or true by default."""
    if isinstance(predicate, str):
        return atoms[predicate]
    operator, *arguments = predicate
    values = [evaluate(argument, atoms) for argument in arguments]
    if operator == "all":
        return False if False in values else (None if None in values else True)
    if operator == "any":
        return True if True in values else (None if None in values else False)
    raise ValueError(f"Unknown role predicate operator: {operator}")


def build_role_effects(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    focus: dict[str, Any],
    edges: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    stages: dict[str, dict[str, str]],
    advances: dict[str, str],
    assessment: dict[str, Any],
    control_conditions: dict[str, Any] | None = None,
    clash_conditions: dict[str, Any] | None = None,
    generation_conditions: dict[str, Any] | None = None,
    cessation_conditions: dict[str, Any] | None = None,
    growth_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = PROFILE["source"]
    result: dict[str, Any] = {
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": source["url"] + "#page=51",
        "source_sha256": source["sha256"],
        "lines": [],
        "chains": [],
        "focus_robustness": "not_adjudicated",
        "textual_issues": deepcopy(PROFILE["textual_issues"]),
        "scope": "元神五项支持六项阻碍、忌神五项支持七项阻碍分别核对。匹配只是原文条件事实，未决强弱不能当假或改成月令分数；元忌同动的接续相生路径仍须审合绊、反制及用神有气，不据条数或路径断成败。",
    }
    selected = focus["selected"]
    for issue in result["textual_issues"]:
        if issue["id"] == "five-versus-three-tombs":
            issue["resolution_update"] = {
                "status": "three_locations_explicitly_defined_in_same_edition",
                "sources": [
                    assessment["source_url"].split("#")[0] + f"#page={p}"
                    for p in (100, 127)
                ],
                "scope": "保留第53页五字异文；三墓机制按同版明确定义，不凭五字增造机制",
            }
    if selected is None:
        result["status"] = "requires_selected_focus"
        return result
    if selected["location"] in ("month", "day", "changed"):
        result["status"] = (
            "changed_focus_calendar_only"
            if selected["location"] == "changed"
            else "calendar_focus_not_subject_to_line_control"
        )
        return result
    result["status"] = "condition_evidence_only"
    roles = {r["position"]: r["role"] for r in focus["roles"]}
    active = {
        r["position"]: bool(
            r["change"]
            or conditions[r["position"] - 1]["activity"]
            in ("暗动条件匹配", "冲空条件匹配")
        )
        for r in lines
    }
    activity_values = {
        r["position"]: conditions[r["position"] - 1].get(
            "activity_condition_match", active[r["position"]]
        )
        for r in lines
    }

    def co_motion(position: int, other_role: str) -> bool | None:
        values = [activity_values[p] for p, name in roles.items() if name == other_role]
        other = True if True in values else None if None in values else False
        own = activity_values[position]
        return (
            False if False in (own, other) else None if None in (own, other) else True
        )

    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    control_pairs = {
        (c["source_position"], c["target_position"]): c
        for c in (control_conditions or {}).get("controls", [])
    }
    for row in lines:
        role = roles.get(row["position"])
        if role not in ("元神", "忌神"):
            continue
        position, element = row["position"], row["element"]
        assessed = assessment["lines"][position - 1]
        growth = growth_conditions["lines"][position - 1] if growth_conditions else None
        branch = row["branch"]
        facts = branch_facts(branch, month, day, void)
        changed = row.get("changed_branch") if row["change"] else None
        changed_facts = branch_facts(changed, month, day, void) if changed else None
        back = element_relation(ELEMENTS[changed], element) if changed else None
        actors = [
            {
                "location": loc,
                "branch": b,
                "relation": element_relation(ELEMENTS[b], element),
            }
            for loc, b in (("month", month), ("day", day))
        ] + [
            {
                "location": "visible",
                "position": other["position"],
                "branch": other["branch"],
                "relation": element_relation(other["element"], element),
                "effect_status": (
                    "back_control_obstructs_outgoing_candidate"
                    if conditions[other["position"] - 1].get("outgoing_obstructions")
                    else (
                        "combination_holds_outgoing_candidate"
                        if conditions[other["position"] - 1]["binding_cues"]
                        else "conditional"
                    )
                ),
            }
            for other in lines
            if other["position"] != position and active[other["position"]]
        ]
        control_actors = [a for a in actors if a["relation"] == "克爻"]
        for actor in control_actors:
            if (
                actor["location"] == "day"
                and growth
                and growth["metal_si_exception_applicable"] is True
                and growth["condition_match"] is True
            ):
                actor.update(
                    control_condition_match=False,
                    control_status="metal_si_growth_replaces_calendar_control",
                    control_source_path=growth["source_path"],
                )
            elif actor["location"] == "month" and day_value_exception(
                branch, month, day
            ):
                actor.update(
                    control_condition_match=False,
                    control_status="day_value_excludes_month_only_opposition",
                    control_source_path=f"liuyao_evidence.conditional_analysis.month_break_conditions.lines.{position-1}",
                )
            elif actor["location"] == "visible" and control_pairs:
                scoped = control_pairs[(actor["position"], position)]
                actor.update(
                    control_condition_match=scoped["condition_match"],
                    control_status=scoped["status"],
                    control_source_path=scoped["fact_path"],
                )
        controls = (
            True
            if any(
                a.get("effect_status", "conditional") == "conditional"
                for a in control_actors
            )
            else (
                None
                if any(
                    a.get("effect_status") == "combination_holds_outgoing_candidate"
                    for a in control_actors
                )
                else False
            )
        )
        harm_values = [
            controls,
            facts["is_day_clash"],
            facts["is_month_clash"],
            back == "克爻",
        ]
        moving_supports = [
            a
            for a in actors
            if a["location"] == "visible" and a["relation"] in ("生爻", "比和")
        ]
        adverse = bool(
            changed
            and (
                back == "克爻"
                or (changed_facts is not None and changed_facts["is_month_clash"])
                or stages[element].get(changed) == "绝"
            )
        )
        atoms: dict[str, bool | None] = {
            "active": active[position],
            "static": not active[position],
            "strength_wang": assessed["strength"]["is_supported"],
            "strength_weak": assessed["strength"]["is_weak"],
            "strength_failing": assessed["strength"]["is_failing"],
            "near_calendar": branch in (day, month),
            "calendar_support": any(
                a["location"] in ("day", "month") and a["relation"] in ("生爻", "比和")
                for a in actors
            ),
            "moving_support": (
                True
                if any(
                    a["location"] == "visible" and active[a["position"]]
                    for a in assessed["strength"]["supports"]
                )
                else (
                    None
                    if any(
                        a["effect_status"]
                        != "back_control_obstructs_outgoing_candidate"
                        for a in moving_supports
                    )
                    else False
                )
            ),
            "back_generate": back == "生爻",
            "advance": bool(changed and advances.get(branch) == changed),
            "retreat": bool(changed and advances.get(changed) == branch),
            "day_growth_peak": query_stage(stages, element, day, ["长生", "帝旺"])[
                "condition_match"
            ],
            "day_cessation": query_stage(stages, element, day, ["绝"])[
                "condition_match"
            ],
            "paired_active": active[position]
            and any(
                active[p]
                for p, r in roles.items()
                if r == ("忌神" if role == "元神" else "元神")
            ),
            "chou_active": active[position]
            and any(active[p] for p, r in roles.items() if r == "仇神"),
            "original_or_changed_void": facts["is_xunkong"]
            or bool(changed_facts and changed_facts["is_xunkong"]),
            "void_or_break": facts["is_xunkong"] or facts["is_month_clash"],
            "injured_relation": (
                True
                if True in harm_values
                else (None if None in harm_values else False)
            ),
            "calendar_moving_controls": controls,
            "entered_tomb": assessed["entered_tomb"],
            # 化散 is not a synonym for any clash, and has not been adjudicated.
            "changed_adverse": True if adverse else (None if changed else False),
        }

        progress = conditions[position - 1].get("progress_conditions")
        adjusted_atoms = dict(atoms)
        if progress:
            atom = "advance" if progress["structural_pair"] == "进神" else "retreat"
            adjusted_atoms[atom] = progress["condition_now"]
        conditional_atoms = dict(adjusted_atoms)
        current_month_obstruction = month_opposition_applies(branch, month, day)
        conditional_atoms["void_or_break"] = (
            facts["is_xunkong"] or current_month_obstruction
        )
        penalty = conditions[position - 1].get(INTERNAL_KEY)
        if penalty and penalty["condition_match"] is not False:
            calendar_values = [
                qualify_yin_generation(True, a["branch"], penalty)
                for a in actors
                if a["location"] in ("day", "month")
                and a["relation"] in ("生爻", "比和")
            ]
            conditional_atoms["calendar_support"] = (
                True
                if True in calendar_values
                else None if None in calendar_values else False
            )
        if growth:
            conditional_atoms["day_growth_peak"] = growth["condition_match"]
        cessation = (
            cessation_conditions["lines"][position - 1]
            if cessation_conditions
            else None
        )
        if cessation:
            conditional_atoms["day_cessation"] = cessation["day"]["condition_match"]
            # Preserve separately observed back-control and month-break. HuaSan
            # is still unadjudicated, so no matched cause does not prove false.
            causes = [
                back_control_condition(row, conditions[position - 1]),
                bool(changed and month_opposition_applies(changed, month, day)),
                cessation["changed"]["condition_match"],
            ]
            conditional_atoms["changed_adverse"] = (
                True if True in causes else None if changed else False
            )
        if generation_conditions:
            generation_source = generation_conditions["sources"][position - 1]
            conditional_atoms["back_generate"] = generation_source[
                "back_generation_condition"
            ]
            conditional_atoms["moving_support"] = (
                True
                if any(
                    a["location"] == "visible"
                    and a.get("generation_condition_match") is True
                    for a in assessed["strength"]["supports"]
                )
                else (
                    None
                    if any(
                        a["location"] == "visible"
                        for a in assessed["strength"]["pending_supports"]
                    )
                    else False
                )
            )
        conditional_controls = (
            (
                True
                if any(
                    (
                        a["location"] in ("month", "day")
                        and a.get("control_condition_match") is not False
                    )
                    or a.get("control_condition_match") is True
                    for a in control_actors
                )
                else (
                    None
                    if any(
                        a.get("control_condition_match") is None
                        and a["location"] == "visible"
                        for a in control_actors
                    )
                    else False
                )
            )
            if control_pairs
            or any("control_condition_match" in a for a in control_actors)
            else controls
        )
        conditional_atoms["calendar_moving_controls"] = conditional_controls
        conditional_harms = [
            conditional_controls,
            (
                clash_conditions["lines"][position - 1]["day_clash_harm_condition"]
                if clash_conditions
                else facts["is_day_clash"]
            ),
            current_month_obstruction,
            back_control_condition(row, conditions[position - 1]),
            conditions[position - 1]
            .get(INTERNAL_KEY, {})
            .get("effect_condition_match", False),
        ]
        conditional_atoms["injured_relation"] = (
            True
            if True in conditional_harms
            else None if None in conditional_harms else False
        )
        if (
            not row["change"]
            and "activity_condition_match" in conditions[position - 1]
            and conditions[position - 1].get("activity_condition_match") is None
        ):
            conditional_atoms["active"] = None
            conditional_atoms["static"] = None
        conditional_atoms["paired_active"] = co_motion(
            position, "忌神" if role == "元神" else "元神"
        )
        conditional_atoms["chou_active"] = co_motion(position, "仇神")

        def rule_evidence(spec: dict[str, Any]) -> dict[str, Any]:
            match = evaluate(spec["formula"], atoms)
            adjusted = evaluate(spec["formula"], adjusted_atoms)
            conditional = evaluate(spec["formula"], conditional_atoms)
            return {
                "rule_id": spec["rule_id"],
                "condition": spec["quote"],
                "predicate": deepcopy(spec["formula"]),
                "matched": match,
                "status": (
                    "requires_unresolved_predicates"
                    if match is None
                    else "predicate_checked_not_effectiveness"
                ),
                "source_url": source["url"] + f"#page={spec['pdf_pages'][0]}",
                "progress_adjusted_matched": adjusted,
                "progress_adjusted_status": (
                    "requires_progress_or_other_unresolved_predicates"
                    if adjusted is None
                    else "condition_checked_not_effectiveness"
                ),
                "conditional_matched": conditional,
                "conditional_status": (
                    "requires_unresolved_control_or_other_conditions"
                    if conditional is None
                    else "condition_checked_not_final_effectiveness"
                ),
            }

        specs = [
            r
            for r in PROFILE["rules"]
            if r["role"] == ("yuan" if role == "元神" else "ji")
        ]
        result["lines"].append(
            {
                "position": position,
                "branch": branch,
                "role": role,
                "atom_values": atoms,
                "progress_atom_values": adjusted_atoms,
                "conditional_atom_values": conditional_atoms,
                "growth_source_path": growth["source_path"] if growth else None,
                "cessation_source_path": (
                    cessation["source_path"] if cessation else None
                ),
                "control_source_path": (
                    "liuyao_evidence.conditional_analysis.control_conditions"
                    if control_pairs
                    else None
                ),
                "clash_source_path": (
                    f"liuyao_evidence.conditional_analysis.clash_conditions.lines.{position-1}"
                    if clash_conditions
                    else None
                ),
                "generation_source_path": (
                    f"liuyao_evidence.conditional_analysis.generation_conditions.sources.{position-1}"
                    if generation_conditions
                    else None
                ),
                "progress_source_path": (
                    f"liuyao_evidence.conditional_analysis.lines.{position - 1}.progress_conditions"
                    if progress
                    else None
                ),
                "actors": actors,
                "binding_cues": list(conditions[position - 1]["binding_cues"]),
                "monthly_strength": deepcopy(
                    conditions[position - 1]["monthly_strength"]
                ),
                "supporting_conditions": [
                    rule_evidence(s) for s in specs if s["kind"] == "support"
                ],
                "obstructing_conditions": [
                    rule_evidence(s) for s in specs if s["kind"] == "obstruction"
                ],
                "adjudication": "requires_strength_timing_and_focus_robustness",
                "strength_source_path": f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{position - 1}.strength",
            }
        )
    yuan = [
        r for r in lines if roles.get(r["position"]) == "元神" and active[r["position"]]
    ]
    ji = [
        r for r in lines if roles.get(r["position"]) == "忌神" and active[r["position"]]
    ]
    for harmful, helpful in product(ji, yuan):
        j, y = harmful["position"], helpful["position"]
        bindings = sorted(p for p in (j, y) if conditions[p - 1]["binding_cues"])
        obstructions = sorted(
            p for p in (j, y) if outgoing_blocker(conditions[p - 1]) is True
        )
        pending_obstructions = [
            p for p in (j, y) if outgoing_blocker(conditions[p - 1]) is None
        ]
        blocked = bool(bindings or obstructions)
        chain_id = f"ji-{j}:yuan-{y}:{selected['location']}-{selected['position']}"
        chain = {
            "chain_id": chain_id,
            "positions": [j, y, selected["position"]],
            "focus_location": selected["location"],
            "status": (
                "back_control_obstructs_routing_candidate"
                if obstructions
                else (
                    "yuan_binding_prevents_routing_candidate"
                    if y in bindings
                    else (
                        "ji_binding_prevents_routing_candidate"
                        if j in bindings
                        else "successive_generation_candidate"
                    )
                )
            ),
            "binding_positions": bindings,
            "obstructed_positions": obstructions,
            "uncertainties": ["元神及忌神实际效力未综合裁定", "用神有气有根仍须另审"],
            "source_url": source["url"] + "#page=54",
        }
        if pending_obstructions and not blocked:
            chain["status"] = "own_si_qualification_requires_routing_review"
        result["chains"].append(chain)
        if not blocked and selected["location"] == "visible":
            for edge in edges:
                if (
                    edge["source_kind"] == "base"
                    and edge["source_position"] == j
                    and edge["target_position"] == selected["position"]
                    and edge["relation"] == "克爻"
                ):
                    if edge["effect_status"] == "conditional":
                        edge["effect_status"] = (
                            "direct_control_requires_yuan_routing_review"
                        )
                    edge.setdefault("routing_chain_ids", []).append(chain_id)
    return result
