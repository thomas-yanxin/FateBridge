"""Qualify hidden reception without certifying emergence or resolving conflicts."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_condition
from .liuyao_growth import PROFILE as GROWTH_PROFILE
from .liuyao_growth import metal_si_growth_supported, metal_si_month_supported
from .liuyao_metal_change import outgoing_blocker
from .liuyao_metal_moving import PROFILE as MOVING_GROWTH_PROFILE
from .liuyao_metal_moving import moving_growth_qualified, moving_support_context
from .liuyao_month_break import day_value_exception, month_opposition_applies
from .liuyao_penalty import INTERNAL_KEY, penalty_context, qualify_yin_generation
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong
from .liuyao_strength import calendar_conditions

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-hidden-v14.json")
    .read_text(encoding="utf-8")
)


def qualify_hidden_reception(
    *,
    hidden: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    generation: dict[str, Any],
    assessment: dict[str, Any],
    month: str,
    day_ganzhi: str,
    stages: dict[str, dict[str, str]],
) -> None:
    """Attach a bounded gate to each hidden target, never to its flying row."""
    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    for i, h in enumerate(hidden):
        p, branch, fly = h["position"], h["branch"], h["flying_branch"]
        source = generation["sources"][p - 1]
        row, c = lines[p - 1], conditions[p - 1]
        if row["branch"] != fly:
            raise ValueError("伏神受生门槛的飞神与同位原爻不一致")
        hidden_moving = moving_support_context(
            element=ELEMENTS[branch],
            subject_position=None,
            lines=lines,
            assessment=assessment,
            generation=generation,
            day_ganzhi=day_ganzhi,
            source_path=f"liuyao_evidence.conditional_analysis.hidden_conditions.{i}.reception.moving_support",
        )
        if hidden_moving is not None:
            hidden_moving.update(
                application_source_url=PROFILE["source"]["url"] + "#page=110",
                application_source_sha256=PROFILE["source"]["sha256"],
                application_interpretation="将同版第110页伏神得动爻生与第97页金逢巳条款合用；这是明示的跨章适用，不是原文逐字描述本开发结构，也不等于已出伏或全局受益。",
            )
        hidden_growth = metal_si_growth_supported(
            ELEMENTS[branch],
            month,
            day,
            h["monthly_strength"],
            hidden_moving is not None and hidden_moving["condition_match"] is True,
        )
        fly_growth = metal_si_growth_supported(
            ELEMENTS[fly], month, day, c["monthly_strength"], moving_growth_qualified(c)
        )
        hf = branch_facts(branch, month, day, void)
        ff = branch_facts(fly, month, day, void)
        relation = element_relation(ELEMENTS[fly], ELEMENTS[branch])
        hidden_penalty = penalty_context(
            branch=branch,
            month=month,
            day=day,
            position=p,
            lines=lines,
            conditions=conditions,
            subject_kind="hidden",
            source_path=f"liuyao_evidence.conditional_analysis.hidden_conditions.{i}.reception.penalty",
        )
        fly_calendar = calendar_conditions(
            branch=fly,
            month=month,
            day_ganzhi=day_ganzhi,
            monthly=h["flying_monthly_strength"],
            metal_moving_support=moving_growth_qualified(c),
            stages=stages,
            penalty=c.get(INTERNAL_KEY),
        )
        fly_strength = assessment["lines"][p - 1]["strength"]
        if relation != "生爻":
            fg, fs = False, "flying_direction_does_not_generate_hidden"
        elif outgoing_blocker(c) is None:
            fg, fs = None, "own_si_growth_or_back_control_pending"
        elif c.get("outgoing_obstructions"):
            fg, fs = False, "own_back_control_obstructs_flying_generation"
        elif ff["is_xunkong"] and not ff["is_day_clash"]:
            fg, fs = None, "flying_current_void_waits_for_filling"
        elif month_opposition_applies(fly, month, day):
            fg, fs = None, "flying_month_break_requires_resolution"
        elif (
            source["status"] == "static_outside_current_all_static_generation_scope"
            and fly_calendar["supports"]
            and not fly_calendar["oppositions"]
            and not fly_calendar["pending_supports"]
            and not fly_strength["oppositions"]
            and fly_strength["day_clash_break_condition"] is False
            and not c["binding_cues"]
        ):
            # Chapter28 names the flying position independently of motion. This
            # exception does not license ordinary static-to-moving generation.
            fg, fs = True, "static_flying_calendar_support_unopposed"
        else:
            fg, fs = source["condition_match"], source["status"]
        raw_flying_match = fg
        fg = qualify_yin_generation(fg, fly, hidden_penalty)
        if fg is not raw_flying_match:
            fs = (
                "hidden_si_yin_generation_excluded"
                if fg is False
                else "hidden_si_yin_generation_activity_pending"
            )
        flying = dict(
            condition_match=fg,
            raw_condition_match=raw_flying_match,
            penalty_source_path=hidden_penalty["source_path"],
            status=fs,
            raw_relation_match=relation == "生爻",
            source_path=f"liuyao_evidence.conditional_analysis.hidden_conditions.{i}.reception.flying_generation",
            generation_source_path=source["source_path"],
            source_generation_condition_match=source["condition_match"],
            source_generation_status=source["status"],
        )
        old = next(
            r
            for r in h["supporting_conditions"]
            if r["rule_id"] == "flying_generates_hidden"
        )
        old.update(
            raw_relation_match=relation == "生爻",
            qualified_matched=fg,
            qualification_status=fs,
            qualification_source_path=flying["source_path"],
            notes="五行生向保留；飞神自身旬空、月破、合绊及回头克分别检查，不以飞空引拔替代飞神已能生伏。",
        )
        for actor in old["actors"]:
            actor.update(
                generation_condition_match=fg,
                generation_source_path=flying["source_path"],
            )
        supports: list[str] = []
        pending: list[str] = []
        blocked: list[str] = []
        calendar = calendar_conditions(
            branch=branch,
            month=month,
            day_ganzhi=day_ganzhi,
            monthly=h["monthly_strength"],
            metal_moving_support=hidden_moving is not None
            and hidden_moving["condition_match"] is True,
            stages=stages,
            penalty=hidden_penalty,
        )
        if hidden_penalty["applicable"]:
            generated_condition = next(
                r
                for r in h["supporting_conditions"]
                if r["rule_id"] == "hidden_calendar_generates"
            )
            generation_values: list[bool | None] = []
            for actor in generated_condition["actors"]:
                value = qualify_yin_generation(True, actor["branch"], hidden_penalty)
                actor.update(
                    generation_condition_match=value,
                    generation_source_path=hidden_penalty["source_path"],
                )
                generation_values.append(value)
            generated_condition.update(
                qualified_matched=(
                    True
                    if True in generation_values
                    else None if None in generation_values else False
                ),
                qualification_status=hidden_penalty["status"],
                qualification_source_path=hidden_penalty["source_path"],
            )
        calendar_support = bool(calendar["supports"])
        if calendar_support:
            supports.append("calendar_support")
        for key, rule_id, target, monthly, path in (
            (
                "supporting_conditions",
                "flying_struck",
                fly,
                c["monthly_strength"],
                f"liuyao_evidence.conditional_analysis.growth_conditions.lines.{p-1}",
            ),
            (
                "obstructing_conditions",
                "hidden_calendar_struck",
                branch,
                h["monthly_strength"],
                f"liuyao_evidence.conditional_analysis.hidden_conditions.{i}.reception.calendar_growth_rule_applied",
            ),
        ):
            metal_exception = (
                fly_growth if rule_id == "flying_struck" else hidden_growth
            )
            month_exception = day_value_exception(target, month, day)
            if not metal_exception and not month_exception:
                continue
            if month_exception:
                kind = "flying" if rule_id == "flying_struck" else "hidden"
                path = f"liuyao_evidence.conditional_analysis.month_break_conditions.hidden.{i}.{kind}"
            condition = next(v for v in h[key] if v["rule_id"] == rule_id)
            values: list[bool | None] = []
            for actor in condition["actors"]:
                if (
                    metal_exception
                    and actor["location"] == "day"
                    and actor["branch"] == "巳"
                ) or (
                    month_exception
                    and actor["location"] == "month"
                    and actor["branch"] == month
                ):
                    actor.update(
                        control_condition_match=False,
                        control_status=(
                            "day_value_excludes_month_only_opposition"
                            if month_exception
                            else "metal_si_growth_replaces_calendar_control"
                        ),
                        control_source_path=path,
                    )
                    values.append(False)
                else:
                    status = actor.get("effect_status", "conditional")
                    values.append(
                        True
                        if status == "conditional"
                        else (
                            None
                            if status
                            in (
                                "combination_holds_outgoing_candidate",
                                "activity_qualification_pending",
                                "generation_source_requires_resolution",
                            )
                            else False
                        )
                    )
            condition.update(
                qualified_matched=(
                    True if True in values else None if None in values else False
                ),
                qualification_status="metal_si_growth_replaces_calendar_strike",
                qualification_source_path=path,
            )
        if fg is True:
            supports.append("qualified_flying_generation")
        generators = next(
            r
            for r in h["supporting_conditions"]
            if r["rule_id"] == "moving_generates_hidden"
        )["actors"]
        for actor in generators:
            raw_generation = actor.get("generation_condition_match")
            actor.update(
                raw_generation_condition_match=raw_generation,
                generation_condition_match=qualify_yin_generation(
                    raw_generation, actor["branch"], hidden_penalty
                ),
                penalty_source_path=hidden_penalty["source_path"],
            )
        moving_rule = next(
            r
            for r in h["supporting_conditions"]
            if r["rule_id"] == "moving_generates_hidden"
        )
        moving_values = [a.get("generation_condition_match") for a in generators]
        moving_rule.update(
            qualified_matched=(
                True
                if True in moving_values
                else None if None in moving_values else False
            ),
            qualification_source_path=hidden_penalty["source_path"],
        )
        generated = [
            a["position"]
            for a in generators
            if a.get("generation_condition_match") is True
        ]
        waiting = [
            a["position"]
            for a in generators
            if a.get("generation_condition_match") is None
        ]
        if generated:
            supports.append("qualified_moving_generation")
        release = month_opposition_applies(fly, month, day) or (
            ff["is_xunkong"] and not ff["is_day_clash"]
        )
        if release:
            supports.append("flying_void_or_month_break_release")
        if any(
            (
                element_relation(ELEMENTS[b], ELEMENTS[fly]) == "克爻"
                and any(
                    a["location"] == location and a["branch"] == b
                    for a in source["retained_calendar_oppositions"]
                )
            )
            or (
                branch_facts(fly, month, b, void)["is_day_clash"]
                and not (location == "month" and day_value_exception(fly, month, day))
            )
            for location, b in (("month", month), ("day", day))
        ):
            supports.append("calendar_strikes_flying")
        calendar_harm = (
            month_opposition_applies(branch, month, day) or hf["is_day_clash"]
        ) or bool(calendar["oppositions"])
        possible_controls = [
            r["position"]
            for r in lines
            if activity_condition(r, conditions[r["position"] - 1]) is not False
            and outgoing_blocker(conditions[r["position"] - 1]) is not True
            and (
                element_relation(r["element"], ELEMENTS[branch]) == "克爻"
                or branch_facts(branch, month, r["branch"], void)["is_day_clash"]
            )
        ]
        strong_flying_control = (
            relation == "克爻"
            and source["strength_supported_unopposed"]
            and not release
            and not c.get("outgoing_obstructions")
            and not c["binding_cues"]
            and "calendar_strikes_flying" not in supports
        )
        # Neither list is a vote. A positive route and an opposing clause stay
        # unresolved; no priority is invented between chapter28's six and five.
        no_root = (
            not supports
            and not calendar["pending_supports"]
            and not any(
                a.get("harm_condition_match", True) is None
                for a in calendar["oppositions"]
            )
            and not h["stage_conditions"]["has_relevant_unknown"]
            and not waiting
            and fg is not None
        )
        if hf["is_month_clash"] and hf["day_element_relation"] == "克爻" and no_root:
            blocked.append("hidden_month_broken_day_controlled_without_root")
        if strong_flying_control and no_root:
            blocked.append("unopposed_strong_flying_control_without_hidden_support")
        if hf["is_xunkong"]:
            pending.append("hidden_current_void_requires_resolution")
        if month_opposition_applies(branch, month, day):
            pending.append("hidden_month_break_requires_resolution")
        if calendar_harm:
            pending.append("hidden_calendar_opposition_requires_resolution")
        if relation == "克爻" and not c.get("outgoing_obstructions"):
            pending.append("flying_control_requires_global_resolution")
        if possible_controls:
            pending.append("moving_control_of_hidden_requires_resolution")
        if h["stage_conditions"]["hidden_tomb_cessation"]["condition_match"] is True:
            pending.append("hidden_tomb_or_cessation_position_not_adjudicated")
        if h["stage_conditions"]["has_relevant_unknown"]:
            pending.append("fire_stage_table_gap")
        if not supports:
            pending.append("hidden_support_not_established")
        elif not (calendar_support or fg is True or generated):
            pending.append("hidden_independent_root_not_established")
        match = False if blocked else None if pending else True
        h["reception"] = dict(
            ruleset_id=PROFILE["ruleset_id"],
            ruleset_version=PROFILE["ruleset_version"],
            condition_match=match,
            status=(
                "listed_hidden_reception_matched"
                if match is True
                else (
                    "listed_hidden_reception_not_matched"
                    if match is False
                    else "hidden_reception_requires_resolution"
                )
            ),
            source_path=f"liuyao_evidence.conditional_analysis.hidden_conditions.{i}.reception",
            source_url=PROFILE["source"]["url"] + "#page=110",
            source_sha256=PROFILE["source"]["sha256"],
            clauses=deepcopy(PROFILE["clauses"]),
            textual_issues=deepcopy(PROFILE["textual_issues"]),
            flying_generation=flying,
            penalty=hidden_penalty,
            support_reasons=supports,
            calendar_support_reasons=[s["reason"] for s in calendar["supports"]],
            calendar_growth_rule_applied=hidden_growth,
            **({"moving_support": hidden_moving} if hidden_moving is not None else {}),
            calendar_growth_source_url=(
                GROWTH_PROFILE["source"]["url"] + "#page=97" if hidden_growth else None
            ),
            calendar_growth_ruleset_id=(
                (
                    GROWTH_PROFILE["ruleset_id"]
                    if metal_si_month_supported(
                        ELEMENTS[branch], month, day, h["monthly_strength"]
                    )
                    else MOVING_GROWTH_PROFILE["ruleset_id"]
                )
                if hidden_growth
                else None
            ),
            flying_growth_source_path=(
                f"liuyao_evidence.conditional_analysis.growth_conditions.lines.{p-1}"
                if fly_growth
                else None
            ),
            pending_calendar_support_reasons=[
                s["reason"] for s in calendar["pending_supports"]
            ],
            pending_reasons=pending,
            blocking_reasons=blocked,
            supporting_positions=generated,
            pending_generation_positions=waiting,
            possible_control_positions=possible_controls,
            is_current_void=hf["is_xunkong"],
            is_month_break=hf["is_month_clash"],
            stage_condition_source_path=h["stage_conditions"]["source_path"],
            stage_ruleset_id=h["stage_conditions"]["ruleset_id"],
            stage_unknown_is_relevant=h["stage_conditions"]["has_relevant_unknown"],
            adjudication="listed_reception_conditions_not_final_emergence",
            scope=PROFILE["scope"]
            + " 阶段缺项依stage_conditions逐项关联；已核位置不被缺项抹去，与本次承受无关的飞神阶段未知不否定独立已核支持。",
        )
