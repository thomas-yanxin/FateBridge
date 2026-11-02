"""Conditional Zengshan evidence, with explicit focus and day-level candidates.

Relations are not votes. Matching a traditional condition neither certifies
the whole judgment nor predicts an external event.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from importlib.resources import files
from typing import Any

from fatebridge.core.almanac import get_bazi_month_context
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.utils.civil_intervals import METHOD_ID, local_interval_preimages

from .liuyao_activity import activity_candidate, activity_condition
from .liuyao_cessation import build_cessation_conditions
from .liuyao_focus import kinship as kinship
from .liuyao_focus import resolve_focus
from .liuyao_focus import role_against_focus as role_against_focus
from .liuyao_growth import build_growth_conditions
from .liuyao_metal_change import INTERNAL_KEY as OWN_SI_KEY
from .liuyao_metal_change import own_si_context, own_si_pending
from .liuyao_metal_moving import INTERNAL_KEY as METAL_KEY
from .liuyao_metal_moving import moving_growth_qualified, moving_support_context
from .liuyao_month_break import build_month_break_conditions
from .liuyao_moving_si import INTERNAL_KEY as MOVING_SI_KEY
from .liuyao_moving_si import finalize_moving_si
from .liuyao_penalty import (
    INTERNAL_KEY,
    attach_penalty_contexts,
    penalty_explanation,
    publish_penalty_conditions,
)
from .liuyao_relations import (
    ADVANCES,
    BRANCHES,
    COMBINES,
    ELEMENTS,
    GENERATES,
    element_relation,
    xunkong,
)
from .liuyao_rescue import build_back_generation_conditions
from .liuyao_routing import build_routing_conditions
from .liuyao_stages import STAGES as STAGES
from .liuyao_stages import attach_hidden_stage_conditions, stage_knowledge

MANIFEST = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-depth-v2.json")
    .read_text(encoding="utf-8")
)
SOURCES = {k: v["source_url"] for k, v in MANIFEST["sources_by_chapter"].items()}


def clash(branch: str) -> str:
    return BRANCHES[(BRANCHES.index(branch) + 6) % 12]


def month_strength(branch: str, month: str) -> dict[str, Any]:
    element, seasonal = ELEMENTS[branch], ELEMENTS[month]
    if branch == month:
        category = "临月建"
    elif clash(month) == branch:
        category = "月破"
    elif element == seasonal:
        category = "同气次旺"
    elif GENERATES[seasonal] == element:
        category = "相"
    else:
        category = "休囚"
    return {
        "category": category,
        "monthly_supported": category in ("临月建", "同气次旺", "相"),
        "residual_qi": (month == "未" and element == "火")
        or (month == "丑" and element == "水"),
        "scope": "仅节月季令层；月合、日辰、动变及生克制化另列，不合成为总旺衰分数",
    }


def binding_cues(line: dict[str, Any], month: str, day: str) -> list[str]:
    if not line["change"]:
        return []
    old, new = line["branch"], line["changed_branch"]
    cues = []
    if COMBINES[old] == new and day not in (clash(old), clash(new)):
        cues.append("动化合未见日冲开")
    if COMBINES[old] == day:
        cues.append("动逢日合")
    if COMBINES[old] == month and day not in (clash(old), clash(month)):
        cues.append("动逢月合未见日冲开")
    return cues


def timing_candidates(
    *,
    moment: datetime,
    days: int,
    selected: dict[str, Any] | None,
    month: str,
    original_ganzhi: str,
    line: dict[str, Any] | None,
    tombs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if type(days) is not int or not 0 <= days <= 60:
        raise ValueError("timing_days 必须是0至60的整数")
    if not days:
        return {
            "status": "not_requested",
            "windows": [],
            "granularity": "sexagenary_day",
        }
    if selected and selected["location"] not in ("visible", "changed"):
        return {
            "status": "nonvisible_focus_requires_separate_timing_rules",
            "windows": [],
            "granularity": "sexagenary_day",
            "scope": "日月及伏神的取用已明确，但未用可见动静爻的应期表替代出伏或日月专门规则",
        }
    if selected is None or line is None:
        return {
            "status": "requires_unambiguous_visible_focus",
            "windows": [],
            "granularity": "sexagenary_day",
        }
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("日级条件窗口需要带时区的起卦时刻")
    branch = selected["branch"]
    original_void = branch in xunkong(original_ganzhi)
    effective_date = moment.date() + timedelta(days=moment.hour >= 23)
    windows: list[dict[str, Any]] = []
    left_original_xun = False
    calendar_exclusions: list[dict[str, Any]] = []
    for index in range(days):
        date = effective_date + timedelta(days=index)
        wall_start = datetime.combine(date - timedelta(days=1), time(23))
        wall_end = datetime.combine(date, time(23))
        intervals = local_interval_preimages(wall_start, wall_end, moment.tzinfo)
        pillar = "".join(
            BaZiCalendar.calculate_day_pillar(
                date.year, date.month, date.day, apply_late_zi_rollover=False
            )
        )
        day = pillar[1]
        matches = []
        if selected["location"] == "changed" and day == branch:
            matches.append("变爻逢值")
        elif selected["location"] == "visible" and day == branch:
            matches.append("动逢值" if line["change"] else "静逢值")
        if (
            selected["location"] == "visible"
            and line["change"]
            and day == COMBINES[branch]
        ):
            matches.append("动逢合")
        if (
            selected["location"] == "visible"
            and not line["change"]
            and day == clash(branch)
        ):
            matches.append("静逢冲")
        if original_void and day in (branch, clash(branch)):
            matches.append("旬空填实" if day == branch else "旬空逢冲")
        if original_void and not left_original_xun and pillar[0] == "甲" and index > 0:
            matches.append("离开起卦日所在旬")
            left_original_xun = True
        if clash(month) == branch and day == COMBINES[branch]:
            matches.append("原局月破逢合")
        partners = (
            [COMBINES[branch]]
            if COMBINES[branch]
            in (month, original_ganzhi[1], line.get("changed_branch"))
            else []
        )
        if partners and day in (clash(branch), clash(partners[0])):
            matches.append("原局六合逢冲开候选")
        if selected["location"] == "visible" and any(
            day == clash(t["branch"]) and t["status"] != "not_true_tomb_broken"
            for t in (tombs or [])
        ):
            matches.append("三墓关系逢冲开候选")
        if not intervals:
            calendar_exclusions.append(
                dict(
                    effective_date=date.isoformat(),
                    day_ganzhi=pillar,
                    wall_start=wall_start.isoformat(),
                    wall_end=wall_end.isoformat(),
                    matched_rules=list(matches),
                    status="empty_utc_preimage",
                    method=METHOD_ID,
                )
            )
        if not matches:
            continue
        for interval_index, (low, high) in enumerate(intervals, start=1):
            clipped = max(low, moment.astimezone(timezone.utc))
            if clipped >= high:
                continue
            start = clipped.astimezone(moment.tzinfo)
            end = high.astimezone(moment.tzinfo)
            month_start = get_bazi_month_context(start)["branch"]
            month_end = get_bazi_month_context(
                (high - timedelta(microseconds=1)).astimezone(moment.tzinfo)
            )["branch"]
            window: dict[str, Any] = {
                "effective_date": date.isoformat(),
                "day_ganzhi": pillar,
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "matched_rules": list(matches),
                "requires_month_reassessment": month_start != month
                or month_end != month,
            }
            if (
                len(intervals) != 1
                or high - low != timedelta(days=1)
                or low.astimezone(moment.tzinfo).replace(tzinfo=None) != wall_start
                or end.replace(tzinfo=None) != wall_end
            ):
                window["civil_interval"] = {
                    "method": METHOD_ID,
                    "wall_start": wall_start.isoformat(),
                    "wall_end": wall_end.isoformat(),
                    "interval_index": interval_index,
                    "interval_count": len(intervals),
                    "start_utc": clipped.isoformat(),
                    "end_utc": high.isoformat(),
                    "duration_seconds": (high - clipped).total_seconds(),
                    "timezone": getattr(moment.tzinfo, "key", str(moment.tzinfo)),
                    "scope": "沿用当地钟面23点换日的既有规则，保留其全部实际UTC分段。effective_date是日柱标签，不证明该民用日期存在；真实时长不必为24小时，不把分段间隙补成连续窗口。",
                }
            windows.append(window)
    # A rollback across 23:00 can interleave two effective-day labels. Sort by
    # actual instants rather than the civil label or the repeated wall clock.
    windows.sort(
        key=lambda item: datetime.fromisoformat(item["start_at"]).astimezone(
            timezone.utc
        )
    )
    result: dict[str, Any] = {
        "status": "condition_windows_only",
        "granularity": "sexagenary_day",
        "requested_days": days,
        "windows": windows,
        "source_url": SOURCES["26又3"],
        "scope": "仅列明确用爻在起卦条件下逢值冲合、旬界及三墓关系逢冲开的日级候选；墓位关系不等于真墓或事件结果。23:00为历法日界，不是事件预测时刻；不排名、不保证发生，跨节月须重审条件。",
    }
    if calendar_exclusions:
        result["calendar_exclusions"] = calendar_exclusions
    return result


def build_conditional_analysis(
    *,
    lines: list[dict[str, Any]],
    hidden: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    palace: str,
    moment: datetime,
    focus_line: int | None,
    focus_kinship: str | None,
    timing_days: int,
    focus_kind: str | None = None,
    event_horizon: str | None = None,
) -> dict[str, Any]:
    from .liuyao_clash import build_clash_conditions
    from .liuyao_complex import (
        build_hidden_conditions,
        build_three_harmony,
        scan_profile,
    )
    from .liuyao_control import build_control_conditions
    from .liuyao_progression import build_progress_conditions
    from .liuyao_roles import build_role_effects
    from .liuyao_strength import build_classical_assessment
    from .liuyao_void import PROFILE as VOID_PROFILE
    from .liuyao_void import build_void_conditions

    if event_horizon not in (None, "near", "long_term"):
        raise ValueError("event_horizon 必须是 near、long_term 或省略。")
    day = day_ganzhi[1]
    monthly = {r["position"]: month_strength(r["branch"], month) for r in lines}
    binds = {r["position"]: binding_cues(r, month, day) for r in lines}
    outgoing = {
        r["position"]: (
            ["本位变爻回头克，向外作用须先审解救"]
            if r["change"]
            and element_relation(ELEMENTS[r["changed_branch"]], r["element"]) == "克爻"
            else []
        )
        for r in lines
    }
    raw_outgoing = deepcopy(outgoing)
    own_contexts = {
        r["position"]: own_si_context(
            r, monthly[r["position"]], month, day_ganzhi, lines
        )
        for r in lines
    }
    for p, context in own_contexts.items():
        if context is not None:
            outgoing[p] = (
                []
                if context["condition_match"] is True
                else ["本位金化巳的长生或回头克资格待审"]
            )
    rows, edges = [], []
    all_static = not any(line["change"] for line in lines)
    for line in lines:
        position, element = line["position"], line["element"]
        supporting = [
            other["position"]
            for other in lines
            if other["position"] != position
            and other["change"]
            and not binds[other["position"]]
            and not outgoing[other["position"]]
            and element_relation(other["element"], element) in ("生爻", "比和")
        ]
        static_supporting = [
            other["position"]
            for other in lines
            if all_static
            and other["position"] != position
            and monthly[other["position"]]["monthly_supported"]
            and element_relation(other["element"], element) == "生爻"
        ]
        clash_today = clash(day) == line["branch"]
        if line["change"]:
            activity = "明动逢冲不自动判散" if clash_today else "明动"
        elif clash_today and (
            monthly[position]["monthly_supported"] or supporting or static_supporting
        ):
            activity = "暗动条件匹配"
        elif clash_today and line["branch"] in xunkong(day_ganzhi):
            activity = "冲空条件匹配"
        elif clash_today:
            activity = "日破候选需复核生扶"
        else:
            activity = "静爻"
        row = {
            "position": position,
            "monthly_strength": monthly[position],
            "activity": activity,
            "supporting_moving_positions": supporting,
            "supporting_static_positions": static_supporting,
            "binding_cues": binds[position],
            "outgoing_obstructions": outgoing[position],
            "day_stage": STAGES[element].get(day),
            "month_stage": STAGES[element].get(month),
            "efficacy": "not_adjudicated",
        }
        cautions = []
        if element == "金" and day == "巳":
            cautions.append("金生于巳与巳火克金并见；须判旺相生扶，不能见长生即作得生")
        if element == "土" and day == "巳":
            cautions.append("土绝于巳与巳火生土并见；旺相有扶论生不论绝，不直接判真绝")
        if element == "金" and day == "丑":
            cautions.append("金墓于丑亦遇土生；须审动土生扶或冲开，不直接判入墓无用")
        row["stage_cautions"] = cautions
        if own_contexts[position] is not None:
            row[OWN_SI_KEY] = own_contexts[position]
        if line["change"]:
            new = line["changed_branch"]
            row["changed_stage"] = STAGES[element].get(new)
            pair = (
                "进神"
                if ADVANCES.get(line["branch"]) == new
                else ("退神" if ADVANCES.get(new) == line["branch"] else None)
            )
            if pair:
                # Resolve after the same-run strength assessment is built.
                row["progress_conditions"] = {"structural_pair": pair}
            edges.append(
                {
                    "source_kind": "changed",
                    "source_position": position,
                    "target_kind": "base",
                    "target_position": position,
                    "relation": element_relation(ELEMENTS[new], element),
                    "effect_status": "parent_only_conditional",
                    "source_url": SOURCES["15"],
                }
            )
        rows.append(row)
    focus = resolve_focus(
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        lines=lines,
        hidden=hidden,
        palace=palace,
        month=month,
        day=day,
        focus_kind=focus_kind,
    )
    selected_line = (
        lines[focus["selected"]["position"] - 1]
        if focus["selected"] and focus["selected"]["location"] in ("visible", "changed")
        else None
    )
    unresolved_activity: set[int] = set()
    for resolution_pass in range(1, 2 * len(lines) + 3):
        before_metal = tuple(moving_growth_qualified(c) for c in rows)
        before_own_si = tuple(
            c.get(OWN_SI_KEY, {}).get("condition_match", False) for c in rows
        )
        before_penalty = attach_penalty_contexts(lines, rows, month, day)
        back_generation_conditions = build_back_generation_conditions(
            lines, month, day_ganzhi, focus["selected"], rows
        )
        control_conditions = build_control_conditions(
            lines=lines,
            conditions=rows,
            month=month,
            day_ganzhi=day_ganzhi,
            stages=STAGES,
            activity_overrides=unresolved_activity,
            back_generation_conditions=back_generation_conditions,
        )
        for activity in control_conditions["activity_conditions"]:
            rows[activity["position"] - 1]["activity_condition_match"] = activity[
                "activity_condition_match"
            ]
            rows[activity["position"] - 1]["activity_condition_status"] = activity[
                "status"
            ]
        after_penalty = attach_penalty_contexts(lines, rows, month, day)
        back_generation_conditions = build_back_generation_conditions(
            lines, month, day_ganzhi, focus["selected"], rows
        )
        assessment = build_classical_assessment(
            lines=lines,
            conditions=rows,
            month=month,
            day_ganzhi=day_ganzhi,
            focus=focus,
            stages=STAGES,
            control_conditions=control_conditions,
            back_generation_conditions=back_generation_conditions,
        )
        for line, condition in zip(lines, rows):
            p = line["position"]
            own_context = own_si_context(
                line,
                monthly[p],
                month,
                day_ganzhi,
                lines,
                assessment,
                assessment["generation_conditions"],
            )
            if own_context is not None:
                own_context["raw_outgoing_obstructions"] = raw_outgoing[p]
                condition[OWN_SI_KEY] = own_context
                outgoing[p] = (
                    []
                    if own_context["condition_match"] is True
                    else ["本位金化巳的长生或回头克资格待审"]
                )
                condition["outgoing_obstructions"] = outgoing[p]
            context = moving_support_context(
                element=line["element"],
                subject_position=p,
                lines=lines,
                assessment=assessment,
                generation=assessment["generation_conditions"],
                day_ganzhi=day_ganzhi,
                source_path=f"liuyao_evidence.conditional_analysis.growth_conditions.lines.{p - 1}.moving_support",
            )
            if context is not None:
                condition[METAL_KEY] = context
        after_metal = tuple(moving_growth_qualified(c) for c in rows)
        after_own_si = tuple(
            c.get(OWN_SI_KEY, {}).get("condition_match", False) for c in rows
        )
        newly_pending = {
            r["position"]
            for r in assessment["lines"]
            if r["strength"]["day_clash_break_condition"] is None
        }
        if (
            newly_pending <= unresolved_activity
            and before_penalty == after_penalty
            and before_metal == after_metal
            and before_own_si == after_own_si
        ):
            break
        unresolved_activity |= newly_pending
    else:
        raise RuntimeError("日冲活动、三支及金巳长生条件未能在六爻有限闭包内稳定")
    control_conditions["activity_resolution_passes"] = resolution_pass
    finalize_moving_si(lines, rows, assessment, control_conditions, month, day_ganzhi)
    for line, condition in zip(lines, rows):
        if own_contexts and any(c.get(OWN_SI_KEY) for c in rows):
            condition["supporting_moving_positions"] = [
                other["position"]
                for other in lines
                if other["position"] != line["position"]
                and other["change"]
                and not binds[other["position"]]
                and not outgoing[other["position"]]
                and element_relation(other["element"], line["element"])
                in ("生爻", "比和")
            ]
    for edge in edges:
        if edge["source_kind"] == "changed":
            context = rows[edge["source_position"] - 1].get(OWN_SI_KEY)
            if context is not None:
                edge.update(
                    effect_status=(
                        "qualified_own_si_growth"
                        if context["condition_match"] is True
                        else "own_si_growth_or_back_control_pending"
                    ),
                    qualified_back_control_condition=context[
                        "qualified_back_control_condition"
                    ],
                    own_si_growth_source_path=context["source_path"],
                )
    generation_conditions = assessment.pop("generation_conditions")
    generation_pairs = {
        (g["source_position"], g["target_position"]): g
        for g in generation_conditions["generations"]
    }
    controls = {
        (c["source_position"], c["target_position"]): c
        for c in control_conditions["controls"]
    }
    for origin in lines:
        for target in lines:
            if origin["position"] == target["position"]:
                continue
            relation = element_relation(origin["element"], target["element"])
            if relation not in ("生爻", "克爻"):
                continue
            active = activity_candidate(origin, rows[origin["position"] - 1])
            static_condition = (
                all_static
                and monthly[origin["position"]]["monthly_supported"]
                and not monthly[target["position"]]["monthly_supported"]
            )
            control = (
                controls.get((origin["position"], target["position"]))
                if relation == "克爻"
                else None
            )
            if control is not None:
                if not control["emit_edge"]:
                    continue
            elif not active and not static_condition:
                continue
            edges.append(
                {
                    "source_kind": "base",
                    "source_position": origin["position"],
                    "target_kind": "base",
                    "target_position": target["position"],
                    "relation": relation,
                    "effect_status": (
                        control["status"]
                        if control is not None
                        and not active
                        and control["condition_match"] is not True
                        else (
                            (
                                "own_si_growth_or_back_control_pending"
                                if own_si_pending(rows[origin["position"] - 1])
                                else "back_control_obstructs_outgoing_candidate"
                            )
                            if outgoing[origin["position"]]
                            else (
                                "combination_holds_outgoing_candidate"
                                if binds[origin["position"]]
                                else (
                                    "activity_qualification_pending"
                                    if relation == "生爻"
                                    and activity_condition(
                                        origin, rows[origin["position"] - 1]
                                    )
                                    is None
                                    else "conditional"
                                )
                            )
                        )
                    ),
                    **(
                        {
                            "control_condition_match": control["condition_match"],
                            "control_status": control["status"],
                            "control_source_path": control["fact_path"],
                            **(
                                dict(
                                    raw_control_condition_match=control[
                                        "raw_condition_match"
                                    ],
                                    metal_si_growth_condition=control[
                                        "metal_si_growth_condition"
                                    ],
                                    metal_si_growth_source_path=control[
                                        "metal_si_growth_source_path"
                                    ],
                                    metal_si_combined_effect_condition=None,
                                )
                                if "metal_si_growth_condition" in control
                                else {}
                            ),
                        }
                        if control is not None
                        else {}
                    ),
                    "source_url": (
                        VOID_PROFILE["source"]["url"] + "#page=94"
                        if outgoing[origin["position"]]
                        else (
                            SOURCES["9"]
                            if binds[origin["position"]]
                            else (
                                control["source_url"]
                                if control is not None
                                else SOURCES["14"]
                            )
                        )
                    ),
                }
            )
            generation = generation_pairs.get((origin["position"], target["position"]))
            if relation == "生爻" and generation is not None:
                edges[-1].update(
                    generation_condition_match=generation["condition_match"],
                    target_reception_condition=generation["target_reception_condition"],
                    benefit_now=generation["benefit_now"],
                    generation_source_path=generation["source_path"],
                    generation_status=generation["status"],
                    target_reception_status=generation["target_status"],
                )
    clash_conditions = build_clash_conditions(
        lines=lines,
        conditions=rows,
        assessment=assessment,
        month=month,
        day_ganzhi=day_ganzhi,
        focus=focus,
    )
    harmony = build_three_harmony(
        lines=lines,
        conditions=rows,
        month=month,
        day_ganzhi=day_ganzhi,
        shi_line=next(r["position"] for r in lines if r.get("shi_ying") == "世"),
        focus=focus["selected"],
        stages=STAGES,
    )
    hidden_conditions = build_hidden_conditions(
        lines=lines,
        hidden=hidden,
        conditions=rows,
        month=month,
        day_ganzhi=day_ganzhi,
        stages=STAGES,
        strength=month_strength,
        generation_conditions=generation_conditions,
    )
    from .liuyao_hidden import qualify_hidden_reception

    attach_hidden_stage_conditions(
        hidden=hidden_conditions, stages=STAGES, month=month, day_ganzhi=day_ganzhi
    )
    qualify_hidden_reception(
        hidden=hidden_conditions,
        lines=lines,
        conditions=rows,
        generation=generation_conditions,
        assessment=assessment,
        month=month,
        day_ganzhi=day_ganzhi,
        stages=STAGES,
    )
    for line, condition, assessed in zip(lines, rows, assessment["lines"]):
        if condition.get("progress_conditions"):
            condition["progress_conditions"] = build_progress_conditions(
                line=line,
                condition=condition,
                strength=assessed["strength"],
                month=month,
                day_ganzhi=day_ganzhi,
                changed_monthly=month_strength(line["changed_branch"], month),
                stages=STAGES,
                event_horizon=event_horizon,
            )
    cessation_conditions = build_cessation_conditions(
        lines=lines,
        assessment=assessment,
        conditions=rows,
        stages=STAGES,
        day_ganzhi=day_ganzhi,
        focus=focus,
    )
    growth_conditions = build_growth_conditions(
        lines=lines,
        conditions=rows,
        assessment=assessment,
        stages=STAGES,
        month=month,
        day_ganzhi=day_ganzhi,
        focus=focus,
        control_conditions=control_conditions,
    )
    role_effects = build_role_effects(
        lines=lines,
        conditions=rows,
        focus=focus,
        edges=edges,
        month=month,
        day_ganzhi=day_ganzhi,
        stages=STAGES,
        advances=ADVANCES,
        assessment=assessment,
        control_conditions=control_conditions,
        clash_conditions=clash_conditions,
        generation_conditions=generation_conditions,
        cessation_conditions=cessation_conditions,
        growth_conditions=growth_conditions,
    )
    routing_conditions = build_routing_conditions(
        lines=lines,
        conditions=rows,
        focus=focus,
        generation=generation_conditions,
        legacy_chains=role_effects["chains"],
        edges=edges,
        hidden_conditions=hidden_conditions,
    )
    void_conditions = build_void_conditions(
        lines=lines,
        hidden=hidden,
        conditions=rows,
        assessment=assessment,
        month=month,
        day_ganzhi=day_ganzhi,
        focus=focus,
    )
    penalty_conditions = publish_penalty_conditions(rows, focus)
    for row, context in zip(rows, penalty_conditions["lines"]):
        text = penalty_explanation(context)
        if text is not None:
            row["stage_cautions"].append(text)
    moving_si_applicable = any(MOVING_SI_KEY in row for row in rows)
    for row in rows:
        row.pop(INTERNAL_KEY)
        row.pop(METAL_KEY, None)
        row.pop(OWN_SI_KEY, None)
        row.pop(MOVING_SI_KEY, None)
    return {
        "ruleset_id": "zengshan_conditional_v2",
        "ruleset_version": "2.21.2" if moving_si_applicable else "2.20.0",
        "month_break_conditions": build_month_break_conditions(
            lines, assessment, month, day, focus["selected"], hidden_conditions
        ),
        "penalty_conditions": penalty_conditions,
        "growth_conditions": growth_conditions,
        "cessation_conditions": cessation_conditions,
        "stage_knowledge": stage_knowledge(),
        "routing_conditions": routing_conditions,
        "back_generation_conditions": back_generation_conditions,
        "generation_conditions": generation_conditions,
        "lines": rows,
        "interaction_edges": edges,
        "focus": focus,
        "three_harmony": harmony,
        "hidden_conditions": hidden_conditions,
        "role_effects": role_effects,
        "classical_assessment": assessment,
        "control_conditions": control_conditions,
        "clash_conditions": clash_conditions,
        "void_conditions": void_conditions,
        "classical_scan": scan_profile(),
        "timing_candidates": timing_candidates(
            moment=moment,
            days=timing_days,
            selected=focus["selected"],
            month=month,
            original_ganzhi=day_ganzhi,
            line=selected_line,
            tombs=assessment["focus"]["tombs"] if assessment["focus"] else [],
        ),
        "source_revisions": deepcopy(MANIFEST["sources_by_chapter"]),
        "textual_issues": list(MANIFEST["textual_issues"]),
        "scope": "条件证据层；化扶与合待冲保留原典不同条件表述，合绊边只列候选。生旺墓绝位置不直接等于得生入墓真绝，进退配对不等于即时进退，未综合断现实吉凶。",
    }
