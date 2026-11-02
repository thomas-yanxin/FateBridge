"""Grounded classical support and three tomb locations, with explicit conflicts."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_candidate, activity_condition
from .liuyao_generation import (
    build_generation_conditions,
    generation_sources,
    target_admission,
)
from .liuyao_growth import (
    METAL_SI_GROWTH_REASON,
    METAL_SI_MOVING_REASON,
    metal_si_growth_supported,
    metal_si_month_supported,
)
from .liuyao_metal_change import INTERNAL_KEY as OWN_SI_KEY
from .liuyao_metal_change import back_control_condition
from .liuyao_metal_moving import moving_growth_qualified
from .liuyao_month_break import day_value_exception, month_opposition_applies
from .liuyao_moving_si import actor_reason
from .liuyao_penalty import INTERNAL_KEY, penalty_context, qualify_yin_generation
from .liuyao_relations import (
    COMBINES,
    ELEMENTS,
    branch_facts,
    element_relation,
    xunkong,
)
from .liuyao_rescue import build_back_generation_conditions

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-strength-v5.json")
    .read_text(encoding="utf-8")
)


def source_url(page: int) -> str:
    return str(PROFILE["source"]["url"]) + f"#page={page}"


def active(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    return activity_candidate(row, condition)


def calendar_conditions(
    *,
    branch: str,
    month: str,
    day_ganzhi: str,
    monthly: dict[str, Any],
    stages: dict[str, dict[str, str]],
    penalty: dict[str, Any] | None = None,
    metal_moving_support: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """One calendar-fact source shared by strength and control prerequisites."""
    b, element = branch, ELEMENTS[branch]
    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    qualified_metal_growth = metal_si_growth_supported(
        element, month, day, monthly, metal_moving_support
    )
    penalty = (
        penalty
        if penalty is not None
        else penalty_context(branch=b, month=month, day=day)
    )
    day_growth_allowed = (
        penalty["day_yin_growth_allowed"]
        if penalty["day_yin_growth_applicable"]
        else True
    )
    supports: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    harms: list[dict[str, Any]] = []

    def add_support(
        kind: str, branch: str, reason: str, position: int | None = None
    ) -> None:
        supports.append(
            {
                "location": kind,
                "position": position,
                "branch": branch,
                "reason": reason,
            }
        )

    if monthly["monthly_supported"]:
        qualified_month = qualify_yin_generation(True, month, penalty)
        if qualified_month is True:
            add_support("month", month, "月令旺相层有扶")
        elif qualified_month is None:
            pending.append(
                dict(
                    location="month",
                    position=None,
                    branch=month,
                    reason="三支活动待审，寅月生扶不能先行确认",
                )
            )
    if COMBINES[month] == b:
        add_support("month", month, "月合有扶")
    daily_relation = element_relation(ELEMENTS[day], element)
    if daily_relation in ("生爻", "比和") and day_growth_allowed is True:
        add_support("day", day, "日辰生扶")
    if COMBINES[day] == b:
        add_support("day", day, "日合扶起条件")
    if stages[element].get(day) in ("长生", "帝旺"):
        if day_growth_allowed is not True:
            if day_growth_allowed is None:
                pending.append(
                    dict(
                        location="day",
                        position=None,
                        branch=day,
                        reason="申爻活动前提待审，寅日长生生扶不能先行确认",
                    )
                )
        elif element == "金" and day == "巳" and not qualified_metal_growth:
            pending.append(
                {
                    "location": "day",
                    "position": None,
                    "branch": day,
                    "reason": "金生巳与火克金并见，须先判生扶",
                }
            )
        else:
            add_support(
                "day",
                day,
                (
                    (
                        METAL_SI_GROWTH_REASON
                        if metal_si_month_supported(element, month, day, monthly)
                        else METAL_SI_MOVING_REASON
                    )
                    if qualified_metal_growth
                    else "已校核日长生帝旺"
                ),
            )
    for location, calendar_branch in (("month", month), ("day", day)):
        facts = branch_facts(b, month, calendar_branch, void)
        relation = element_relation(ELEMENTS[calendar_branch], element)
        if location == "month" and day_value_exception(b, month, day):
            # The retained raw month category is not this qualified opposition.
            # Other moving and transformed control is collected independently.
            continue
        if (
            relation == "克爻" and not (location == "day" and qualified_metal_growth)
        ) or (location == "month" and facts["is_month_clash"]):
            harms.append(
                {
                    "location": location,
                    "position": None,
                    "branch": calendar_branch,
                    "reason": (
                        "月破"
                        if location == "month" and facts["is_month_clash"]
                        else "日月克爻"
                    ),
                    "grounded": True,
                }
            )
    if penalty["condition_match"] is not False:
        harms.append(
            dict(
                location=(
                    "day"
                    if day in ("寅", "申")
                    else "month" if month in ("寅", "申") else "pattern"
                ),
                position=None,
                branch=(
                    day
                    if day in ("寅", "申")
                    else month if month in ("寅", "申") else b
                ),
                pattern_actor_branches=sorted({a["branch"] for a in penalty["actors"]}),
                pattern_subject_branch=b,
                reason="巳寅申三支条件已列，刑的总作用未裁定",
                grounded=False,
                harm_condition_match=None,
                penalty_source_path=penalty["source_path"],
            )
        )
    return {"supports": supports, "pending_supports": pending, "oppositions": harms}


def build_classical_assessment(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    focus: dict[str, Any],
    stages: dict[str, dict[str, str]],
    control_conditions: dict[str, Any] | None = None,
    back_generation_conditions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    all_static = not any(r["change"] for r in lines)
    back_generation_conditions = (
        back_generation_conditions
        or build_back_generation_conditions(
            lines, month, day_ganzhi, conditions=conditions
        )
    )
    back_supports = {r["position"]: r for r in back_generation_conditions["sources"]}
    monthly_qualified = {
        r["position"]: qualify_yin_generation(
            conditions[r["position"] - 1]["monthly_strength"]["monthly_supported"],
            month,
            conditions[r["position"] - 1].get(INTERNAL_KEY)
            or penalty_context(
                branch=r["branch"],
                month=month,
                day=day,
                position=r["position"],
                own_changed=r.get("changed_branch") if r["change"] else None,
                lines=lines,
                conditions=conditions,
            ),
        )
        for r in lines
    }
    observations: dict[int, dict[str, Any]] = {}
    controls = {
        (r["source_position"], r["target_position"]): r
        for r in (control_conditions or {}).get("controls", [])
    }
    for row in lines:
        p, b, element = row["position"], row["branch"], row["element"]
        c = conditions[p - 1]
        calendar = calendar_conditions(
            branch=b,
            month=month,
            day_ganzhi=day_ganzhi,
            monthly=c["monthly_strength"],
            metal_moving_support=moving_growth_qualified(c),
            stages=stages,
            penalty=c.get(INTERNAL_KEY)
            or penalty_context(
                branch=b,
                month=month,
                day=day,
                position=p,
                own_changed=row.get("changed_branch") if row["change"] else None,
                lines=lines,
                conditions=conditions,
            ),
        )
        supports = calendar["supports"]
        pending = calendar["pending_supports"]
        harms = calendar["oppositions"]
        excluded_back: list[dict[str, Any]] = []
        excluded_back_controls: list[dict[str, Any]] = []
        if row["change"]:
            changed = row["changed_branch"]
            back = element_relation(ELEMENTS[changed], element)
            cf = branch_facts(changed, month, day, void)
            obstructed = (
                (cf["is_xunkong"] and not cf["is_day_clash"])
                or cf["is_month_clash"]
                and month_opposition_applies(changed, month, day)
            )
            # A same-element transformation is the same line's progression,
            # not an independent root. Otherwise an unassisted weak line can
            # bootstrap its own strength solely by advancing or retreating.
            if back == "生爻":
                support = back_supports[p]
                target = (
                    supports
                    if support["condition_match"] is True
                    else (
                        excluded_back
                        if support["condition_match"] is False
                        else pending
                    )
                )
                target.append(
                    {
                        "location": "changed",
                        "position": p,
                        "branch": changed,
                        "reason": (
                            "本位变爻回头生扶"
                            if support["condition_match"] is True
                            else (
                                "巳寅申特定条款排除本位寅生扶"
                                if support["condition_match"] is False
                                else "回头生扶门槛或三支活动待审"
                            )
                        ),
                        "back_generation_condition": support["condition_match"],
                        "back_generation_source_path": support["source_path"],
                    }
                )
            elif back == "克爻":
                qualified_back = back_control_condition(row, c)
                actor = {
                    "location": "changed",
                    "position": p,
                    "branch": changed,
                    "reason": "本位变爻回头克",
                    "grounded": not obstructed and qualified_back is True,
                }
                if OWN_SI_KEY in c:
                    actor.update(
                        harm_condition_match=qualified_back,
                        qualification_source_path=c[OWN_SI_KEY]["source_path"],
                    )
                    if qualified_back is None:
                        actor["reason"] = "本位金化巳的长生或回头克资格待审"
                if qualified_back is False:
                    actor["reason"] = (
                        "金爻实际化巳，独立生扶已核；本项按长生而不作回头克"
                    )
                    excluded_back_controls.append(actor)
                else:
                    harms.append(actor)
        possible_supports: list[dict[str, Any]] = []
        blocked_supports: list[dict[str, Any]] = excluded_back
        blocked_oppositions: list[dict[str, Any]] = excluded_back_controls
        for other in lines:
            op = other["position"]
            if op == p:
                continue
            oc = conditions[op - 1]
            moving = active(other, oc)
            static_allowed = all_static and monthly_qualified[op] is True
            relation = element_relation(other["element"], element)
            if (moving and relation in ("生爻", "比和")) or (
                static_allowed and relation == "生爻"
            ):
                (
                    blocked_supports
                    if oc.get("outgoing_obstructions")
                    else possible_supports
                ).append(
                    {
                        "location": "visible",
                        "position": op,
                        "branch": other["branch"],
                        "reason": (
                            "回头克来源暂不能作为向外生扶"
                            if oc.get("outgoing_obstructions")
                            else ("明暗动生扶" if moving else "全静旺爻相生")
                        ),
                        "held": bool(oc["binding_cues"]),
                        "activity_pending": moving
                        and not other["change"]
                        and oc.get("activity_condition_match", True) is not True,
                    }
                )
            if relation == "克爻" and controls:
                control = controls[(op, p)]
                actor = {
                    "location": "visible",
                    "position": op,
                    "branch": other["branch"],
                    "reason": "按动静对象与受克传递核对的克制条件",
                    "control_condition_match": control["condition_match"],
                    "control_status": control["status"],
                    "control_source_path": control["fact_path"],
                    "grounded": control["condition_match"] is True,
                }
                if "metal_si_growth_condition" in control:
                    actor.update(
                        metal_si_growth_condition=control["metal_si_growth_condition"],
                        qualification_source_path=control[
                            "metal_si_growth_source_path"
                        ],
                    )
                    actor["reason"] = actor_reason(control)
                (
                    blocked_oppositions
                    if control["condition_match"] is False
                    else harms
                ).append(actor)
            elif (
                not controls
                and not oc.get("outgoing_obstructions")
                and relation == "克爻"
                and (moving or (static_allowed and monthly_qualified[p] is not True))
            ):
                harms.append(
                    {
                        "location": "visible",
                        "position": op,
                        "branch": other["branch"],
                        "reason": "原卦爻克制候选",
                        "grounded": False,
                    }
                )
        facts = branch_facts(b, month, day, void)
        pending_day_clash = (
            facts["is_day_clash"]
            and not row["change"]
            and not facts["is_xunkong"]
            and activity_condition(row, c) is not True
        )
        if pending_day_clash:
            harms.append(
                {
                    "location": "day",
                    "position": None,
                    "branch": day,
                    "reason": "静爻日冲的破与暗动前提待审",
                    "grounded": False,
                    "day_clash_break_condition": None,
                    "clash_source_path": f"liuyao_evidence.conditional_analysis.clash_conditions.lines.{p - 1}",
                }
            )
        observations[p] = {
            "penalty": c.get(INTERNAL_KEY)
            or penalty_context(
                branch=b,
                month=month,
                day=day,
                position=p,
                own_changed=row.get("changed_branch") if row["change"] else None,
                lines=lines,
                conditions=conditions,
            ),
            "supports": supports,
            "pending_supports": pending,
            "harms": harms,
            "possible_supports": possible_supports,
            "blocked_supports": blocked_supports,
            "blocked_oppositions": blocked_oppositions,
            "pending_day_clash": pending_day_clash,
        }

    # Distinguish outgoing generation from unopposed total strength. A source
    # with its own valid back-generation can still generate while calendar
    # injury remains. Receiving void/break/rootlessness is a separate gate.
    grounded = {
        p
        for p, o in observations.items()
        if o["supports"]
        and not o["harms"]
        and target_admission(lines[p - 1], o, month, day_ganzhi)[0] is True
    }
    sources: dict[int, dict[str, Any]] = {}

    def support_match(actor: dict[str, Any], target_position: int) -> bool | None:
        source_position = actor["position"]
        target_context = conditions[target_position - 1].get(
            INTERNAL_KEY
        ) or penalty_context(
            branch=lines[target_position - 1]["branch"],
            month=month,
            day=day,
            position=target_position,
            own_changed=(
                lines[target_position - 1].get("changed_branch")
                if lines[target_position - 1]["change"]
                else None
            ),
            lines=lines,
            conditions=conditions,
        )
        if (
            element_relation(
                lines[source_position - 1]["element"],
                lines[target_position - 1]["element"],
            )
            == "生爻"
        ):
            generation = sources[source_position]["condition_match"]
            reception = target_admission(
                lines[target_position - 1],
                observations[target_position],
                month,
                day_ganzhi,
            )[0]
            return qualify_yin_generation(
                (
                    False
                    if False in (generation, reception)
                    else None if None in (generation, reception) else True
                ),
                actor["branch"],
                target_context,
            )
        # Peer support is not the chapter-ten outgoing-generation rule.
        return (
            True
            if source_position in grounded
            and not actor["held"]
            and not actor["activity_pending"]
            else None
        )

    changed = True
    resolution_passes = 0
    while changed:
        resolution_passes += 1
        sources = generation_sources(
            lines=lines,
            conditions=conditions,
            observations=observations,
            grounded=grounded,
            month=month,
            day_ganzhi=day_ganzhi,
        )
        changed = False
        for p, o in observations.items():
            if p in grounded or o["harms"]:
                continue
            if any(support_match(a, p) is True for a in o["possible_supports"]):
                grounded.add(p)
                changed = True
    generation_conditions = build_generation_conditions(
        lines=lines,
        sources=sources,
        observations=observations,
        month=month,
        day_ganzhi=day_ganzhi,
        resolution_passes=resolution_passes,
        selected=focus["selected"],
    )
    generation_pairs = {
        (g["source_position"], g["target_position"]): g
        for g in generation_conditions["generations"]
    }
    strengths: dict[int, dict[str, Any]] = {}
    for row in lines:
        p = row["position"]
        o = observations[p]
        supports, pending = list(o["supports"]), list(o["pending_supports"])
        blocked_supports = [
            a for a in o["blocked_supports"] if a["location"] == "changed"
        ]
        blocked_positions = {a["position"] for a in o["blocked_supports"]}
        for actor in o["possible_supports"] + [
            a for a in o["blocked_supports"] if a["location"] != "changed"
        ]:
            pair = generation_pairs.get((actor["position"], p))
            if pair:
                actor = {
                    **actor,
                    "generation_condition_match": pair["condition_match"],
                    "target_reception_condition": pair["target_reception_condition"],
                    "benefit_now": pair["benefit_now"],
                    "generation_source_path": pair["source_path"],
                }
            match = (
                False
                if actor["position"] in blocked_positions
                else support_match(actor, p)
            )
            (
                supports
                if match is True
                else blocked_supports if match is False else pending
            ).append({**actor, "source_grounded": actor["position"] in grounded})
        harms = deepcopy(o["harms"])
        facts = branch_facts(row["branch"], month, day, void)
        if not facts["is_day_clash"]:
            day_break, break_status = False, "no_day_clash"
        elif row["change"]:
            day_break, break_status = False, "moving_not_static_day_break"
        elif facts["is_xunkong"]:
            day_break, break_status = False, "day_void_filling_takes_priority"
        elif activity_condition(row, conditions[p - 1]) is True:
            day_break, break_status = False, "qualified_dark_activity_not_day_break"
        elif not supports and not pending and monthly_qualified[p] is not True:
            day_break, break_status = (
                True,
                "unassisted_static_day_break_condition_matched",
            )
        else:
            day_break, break_status = None, "static_clash_strength_requires_review"
        for harm in harms:
            if "day_clash_break_condition" in harm:
                harm["day_clash_break_condition"] = day_break
                harm["grounded"] = day_break is True
                harm["reason"] = (
                    "静爻日破条件匹配" if day_break else "静爻日冲与生扶前提仍待审"
                )
        for harm in harms:
            if harm["location"] == "visible":
                hp = harm["position"]
                if "control_condition_match" not in harm:
                    harm["grounded"] = (
                        hp in grounded and not conditions[hp - 1]["binding_cues"]
                    )
        weak = (
            not supports
            and not pending
            and monthly_qualified[p] is not True
            and any(h["grounded"] for h in harms)
        )
        strong = p in grounded
        status = (
            "supported_unopposed"
            if strong
            else (
                (
                    "day_broken_unsupported"
                    if day_break is True
                    else "harmed_unsupported"
                )
                if weak
                else (
                    "contested_or_pending"
                    if supports or pending or harms
                    else "unresolved_no_grounded_support"
                )
            )
        )
        facts = branch_facts(row["branch"], month, day, void)
        strengths[p] = {
            "status": status,
            "is_supported": True if strong else (False if weak else None),
            "is_weak": True if weak else (False if strong else None),
            "is_failing": (
                True
                if weak
                and facts["is_month_clash"]
                and element_relation(ELEMENTS[day], row["element"]) == "克爻"
                else (False if strong else None)
            ),
            "supports": supports,
            "pending_supports": pending,
            "blocked_supports": blocked_supports,
            "blocked_oppositions": deepcopy(o["blocked_oppositions"]),
            "day_clash_break_condition": day_break,
            "day_clash_break_status": break_status,
            "oppositions": harms,
            "source_url": source_url(99),
            "scope": "只裁定有根生扶且无已列反制、或无扶而符合受克或静爻日破的明确分支；日扶与日冲并见、扶克并见及来源效力未明保持未知。不是全局吉凶分数。",
        }

    assessments = []
    for row in lines:
        p, b = row["position"], row["branch"]
        tomb = next(k for k, v in stages[row["element"]].items() if v == "墓")
        candidates: list[dict[str, Any]] = []
        if day == tomb:
            candidates.append({"location": "day", "position": None, "branch": tomb})
        candidates.extend(
            {
                "location": "moving",
                "position": r["position"],
                "branch": tomb,
                "activity_condition_match": activity_condition(
                    r, conditions[r["position"] - 1]
                ),
            }
            for r in lines
            if r["position"] != p
            and r["branch"] == tomb
            and active(r, conditions[r["position"] - 1])
        )
        if row["change"] and row["changed_branch"] == tomb:
            candidates.append({"location": "changed", "position": p, "branch": tomb})
        for candidate in candidates:
            breakers: list[dict[str, Any]] = []
            pending_breakers: list[dict[str, Any]] = []
            ignored_breakers: list[dict[str, Any]] = []
            for location, branch, position in [
                ("month", month, None),
                ("day", day, None),
                *[
                    ("visible", r["branch"], r["position"])
                    for r in lines
                    if active(r, conditions[r["position"] - 1])
                ],
            ]:
                if not branch_facts(tomb, month, branch, void)["is_day_clash"]:
                    continue
                actor = {"location": location, "position": position, "branch": branch}
                # Do not manufacture original-line attacks on a changed line or
                # a calendar deity. Day-tomb opening needs its separate context.
                if candidate["location"] == "changed" and location == "visible":
                    ignored_breakers.append(
                        {**actor, "reason": "原爻不能跨入变爻作用域"}
                    )
                elif candidate["location"] == "day":
                    pending_breakers.append(
                        {**actor, "reason": "超出当前日墓或变爻作用范围"}
                    )
                elif location in ("month", "day") or (
                    position in grounded
                    and not conditions[position - 1]["binding_cues"]
                    and activity_condition(
                        lines[position - 1], conditions[position - 1]
                    )
                    is True
                ):
                    breakers.append(actor)
                else:
                    pending_breakers.append(
                        {**actor, "reason": "动爻冲墓关系尚待来源效力裁定"}
                    )
            if breakers:
                truth, status = False, "not_true_tomb_broken"
            elif strengths[p]["is_supported"] is True:
                truth, status = False, "not_true_tomb_supported"
            elif (
                pending_breakers
                or (
                    tomb in void
                    and not branch_facts(tomb, month, day, void)["is_day_clash"]
                )
                or (
                    candidate["location"] == "moving"
                    and candidate.get("activity_condition_match") is not True
                )
            ):
                truth, status = None, "tomb_break_or_void_requires_review"
            elif strengths[p]["is_weak"] is True:
                truth, status = True, "true_tomb_conditions_matched"
            else:
                truth, status = None, "requires_strength_resolution"
            candidate.update(
                {
                    "breakers": breakers,
                    "pending_breakers": pending_breakers,
                    "ignored_breakers": ignored_breakers,
                    "is_xunkong": tomb in void,
                    "is_true_tomb": truth,
                    "status": status,
                    "source_url": source_url(127),
                }
            )
        entered = (
            True
            if any(c["is_true_tomb"] is True for c in candidates)
            else (None if any(c["is_true_tomb"] is None for c in candidates) else False)
        )
        assessments.append(
            {
                "position": p,
                "branch": b,
                "strength": strengths[p],
                "tomb_branch": tomb,
                "month_tomb_relation": month == tomb,
                "tombs": candidates,
                "entered_tomb": entered,
            }
        )
    selected = focus["selected"]
    return {
        "generation_conditions": generation_conditions,
        "ruleset_id": PROFILE["ruleset_id"],
        "ruleset_version": PROFILE["ruleset_version"],
        "source_url": source_url(99),
        "source_sha256": PROFILE["source"]["sha256"],
        "lines": assessments,
        "focus": (
            deepcopy(assessments[selected["position"] - 1])
            if selected and selected["location"] == "visible"
            else None
        ),
        "resolution_notes": deepcopy(PROFILE["resolution_notes"]),
        "scope": "明爻有根生扶和日墓、动墓、本位化墓；月墓关系另列，不混入三墓。克生冲合须按作用范围与效力审查，未决分支不作通过；本层不输出事件吉凶。",
    }
