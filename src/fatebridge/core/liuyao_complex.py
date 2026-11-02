"""Scan-backed formation paths and flying/hidden conditions, without votes."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from itertools import combinations
from typing import Any, Callable

from .liuyao_activity import activity_candidate, activity_condition
from .liuyao_month_break import month_opposition_applies
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong

SCAN: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-scan-v3.json")
    .read_text(encoding="utf-8")
)
GROUPS = (("申子辰", "水"), ("巳酉丑", "金"), ("寅午戌", "火"), ("亥卯未", "木"))


def scan_url(page: int) -> str:
    return str(SCAN["source"]["url"]) + f"#page={page}"


def scan_profile() -> dict[str, Any]:
    return deepcopy(SCAN)


def _active(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    return activity_candidate(row, condition)


def build_three_harmony(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    shi_line: int,
    focus: dict[str, Any] | None,
    stages: dict[str, dict[str, str]],
) -> dict[str, Any]:
    active = {r["position"]: _active(r, conditions[r["position"] - 1]) for r in lines}
    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    candidates: list[dict[str, Any]] = []

    def member(row: dict[str, Any], changed: bool = False) -> dict[str, Any]:
        branch = row["changed_branch"] if changed else row["branch"]
        return {
            "location": "changed" if changed else "visible",
            "position": row["position"],
            "branch": branch,
            "element": ELEMENTS[branch],
            "activity": (
                "变爻" if changed else conditions[row["position"] - 1]["activity"]
            ),
            "activity_condition_match": (
                True
                if changed
                else activity_condition(row, conditions[row["position"] - 1])
            ),
            "day_void_fill_condition": bool(
                branch_facts(branch, month, day, void)["is_xunkong"]
                and branch_facts(branch, month, day, void)["is_day_clash"]
            ),
            "outgoing_obstructions": (
                []
                if changed
                else list(
                    conditions[row["position"] - 1].get("outgoing_obstructions", [])
                )
            ),
        }

    def append(
        group: str,
        element: str,
        pattern: str,
        members: list[dict[str, Any]],
        missing: list[str] | None = None,
    ) -> None:
        missing = missing or []
        obstructions = []
        for m in members:
            facts = branch_facts(m["branch"], month, day, void)
            for flag, label in (
                ("is_xunkong", "旬空待填"),
                ("is_month_clash", "月破待实"),
            ):
                if facts[flag] and not (
                    (flag == "is_xunkong" and facts["is_day_clash"])
                    or (
                        flag == "is_month_clash"
                        and not month_opposition_applies(m["branch"], month, day)
                    )
                ):
                    obstructions.append(
                        {
                            "condition": label,
                            "location": m["location"],
                            "position": m["position"],
                            "branch": m["branch"],
                        }
                    )
            for location, branch in (("month", month), ("day", day)):
                if stages[m["element"]].get(branch) == "墓":
                    obstructions.append(
                        {
                            "condition": "墓位关系待审冲开",
                            "location": m["location"],
                            "position": m["position"],
                            "branch": m["branch"],
                            "actor_location": location,
                            "actor_branch": branch,
                        }
                    )
        count = sum(
            active[m["position"]] for m in members if m["location"] == "visible"
        )
        if missing:
            status = "awaiting_missing_branch"
        elif count == 0:
            status = "static_three_branches_only"
        elif count == 1:
            status = "single_active_text_requires_review"
        else:
            status = (
                "awaiting_fill_or_tomb_review"
                if obstructions
                else "formation_conditions_matched"
            )
        completions = [
            {"location": loc, "branch": b}
            for loc, b in (("month", month), ("day", day))
            if b in missing
        ]
        if missing and completions:
            status = "day_month_completion_candidate"
        structural_status = status
        pending_activity = sorted(
            {
                m["position"]
                for m in members
                if m["location"] == "visible"
                and active[m["position"]]
                and m["activity_condition_match"] is None
            }
        )
        confirmed_activity = sorted(
            {
                m["position"]
                for m in members
                if m["location"] == "visible" and m["activity_condition_match"] is True
            }
        )
        if pending_activity:
            status = "formation_requires_activity_resolution"
        candidates.append(
            {
                "candidate_id": group
                + ":"
                + pattern
                + ":"
                + ",".join(
                    f"{m['location']}-{m['position']}-{m['branch']}" for m in members
                ),
                "group_branches": list(group),
                "element": element,
                "pattern": pattern,
                "members": members,
                "active_positions": sorted(
                    {
                        m["position"]
                        for m in members
                        if m["location"] == "visible" and active[m["position"]]
                    }
                ),
                "qualified_active_positions": confirmed_activity,
                "unresolved_activity_positions": pending_activity,
                "structural_status": structural_status,
                "missing_branches": missing,
                "calendar_completions": completions,
                "obstructions": obstructions,
                "status": status,
                "contains_shi": any(m["position"] == shi_line for m in members),
                "relation_to_focus": (
                    element_relation(element, focus["element"]) if focus else None
                ),
            }
        )

    for group, element in GROUPS:
        for triple in combinations(lines, 3):
            if {r["branch"] for r in triple} == set(group):
                append(
                    group, element, "base_three_branches", [member(r) for r in triple]
                )
        for pair in combinations(lines, 2):
            branches = {r["branch"] for r in pair}
            if (
                len(branches) != 2
                or not branches < set(group)
                or not all(active[r["position"]] for r in pair)
            ):
                continue
            missing = sorted(set(group) - branches)
            if not any(r["branch"] in missing for r in lines):
                append(
                    group,
                    element,
                    "two_base_branches_waiting",
                    [member(r) for r in pair],
                    missing,
                )
        for left, right, label in ((0, 2, "inner_changed"), (3, 5, "outer_changed")):
            endpoints = [lines[left], lines[right]]
            if not all(r["change"] for r in endpoints):
                continue
            for transformed in endpoints:
                members = [*(member(r) for r in endpoints), member(transformed, True)]
                if {m["branch"] for m in members} == set(group):
                    append(group, element, label, members)
    for candidate in candidates:
        if candidate["pattern"] != "two_base_branches_waiting":
            continue
        anchors = {m["position"] for m in candidate["members"]}
        completion_paths = [
            p
            for p in candidates
            if p["pattern"] in ("inner_changed", "outer_changed")
            and p["element"] == candidate["element"]
            and {m["position"] for m in p["members"] if m["location"] == "visible"}
            == anchors
        ]
        if completion_paths:
            candidate["completion_paths"] = [
                p["candidate_id"] for p in completion_paths
            ]
            candidate["status"] = (
                "completed_by_scoped_changed_path"
                if any(
                    p["status"] == "formation_conditions_matched"
                    for p in completion_paths
                )
                else "changed_completion_requires_fill_or_review"
            )
    relations = [
        {
            "source_id": outer["candidate_id"],
            "target_id": inner["candidate_id"],
            "relation": element_relation(outer["element"], inner["element"]),
            "scope": "局五行之间的方向；强弱及生克有效性另审",
        }
        for outer in candidates
        if outer["pattern"] == "outer_changed"
        for inner in candidates
        if inner["pattern"] == "inner_changed"
    ]
    return {
        "candidates": candidates,
        "relations": relations,
        "source_url": scan_url(78),
        "scope": "仅按本卦三支、两动缺一待补、内初三及外四六动变列路径。静三支不自动成局；空破墓保留待审；同一支局的多路径不是多票支持，也不代表全局吉凶。首句一动成局条件未明，不强补其余条件。",
    }


def build_hidden_conditions(
    *,
    lines: list[dict[str, Any]],
    hidden: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    month: str,
    day_ganzhi: str,
    stages: dict[str, dict[str, str]],
    strength: Callable[[str, str], dict[str, Any]],
    generation_conditions: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    day, void = day_ganzhi[1], xunkong(day_ganzhi)
    moving = [r for r in lines if _active(r, conditions[r["position"] - 1])]
    calendar = [
        {"location": "month", "branch": month},
        {"location": "day", "branch": day},
    ]

    def actors(target: str, rule: str) -> list[dict[str, Any]]:
        found = []
        for actor in [
            *calendar,
            *(
                {
                    "location": "visible",
                    "position": r["position"],
                    "branch": r["branch"],
                }
                for r in moving
            ),
        ]:
            relation = element_relation(ELEMENTS[actor["branch"]], ELEMENTS[target])
            clash = branch_facts(target, month, actor["branch"], void)["is_day_clash"]
            if (rule == "generates" and relation == "生爻") or (
                rule == "strikes" and (relation == "克爻" or clash)
            ):
                row = {
                    **actor,
                    "relation": "支冲" if clash and rule == "strikes" else relation,
                }
                if actor["location"] == "visible":
                    row["effect_status"] = (
                        "back_control_obstructs_outgoing_candidate"
                        if conditions[actor["position"] - 1].get(
                            "outgoing_obstructions"
                        )
                        else (
                            "combination_holds_outgoing_candidate"
                            if conditions[actor["position"] - 1]["binding_cues"]
                            else (
                                "activity_qualification_pending"
                                if activity_condition(
                                    lines[actor["position"] - 1],
                                    conditions[actor["position"] - 1],
                                )
                                is None
                                else "conditional"
                            )
                        )
                    )
                    if rule == "generates" and generation_conditions:
                        source = generation_conditions["sources"][actor["position"] - 1]
                        row["generation_condition_match"] = source["condition_match"]
                        row["generation_source_path"] = source["source_path"]
                        row["effect_status"] = (
                            "conditional"
                            if source["condition_match"] is True
                            else (
                                row["effect_status"]
                                if row["effect_status"] != "conditional"
                                else (
                                    "generation_source_requires_resolution"
                                    if source["condition_match"] is None
                                    else "generation_source_condition_not_matched"
                                )
                            )
                        )
                found.append(row)
        return found

    def actor_match(actors: list[dict[str, Any]]) -> bool | None:
        if any(a.get("effect_status", "conditional") == "conditional" for a in actors):
            return True
        if any(
            a.get("effect_status")
            in (
                "combination_holds_outgoing_candidate",
                "activity_qualification_pending",
                "generation_source_requires_resolution",
            )
            for a in actors
        ):
            return None
        return False

    results = []
    for h in hidden:
        branch = h["branch"]
        fly = lines[h["position"] - 1]["branch"]
        if h.get("flying_branch", fly) != fly:
            raise ValueError("伏神记录的飞神与本卦同位原爻不一致")
        monthly, flying_monthly = strength(branch, month), strength(fly, month)
        generated = actors(branch, "generates")
        flying_struck = actors(fly, "strikes")
        hidden_struck = [
            a for a in actors(branch, "strikes") if a["location"] != "visible"
        ]
        fly_relation = element_relation(ELEMENTS[fly], ELEMENTS[branch])
        hidden_facts, fly_facts = branch_facts(branch, month, day, void), branch_facts(
            fly, month, day, void
        )
        hidden_tombs = [
            {"location": loc, "branch": b, "relation": stages[ELEMENTS[branch]].get(b)}
            for loc, b in (("month", month), ("day", day), ("flying", fly))
            if stages[ELEMENTS[branch]].get(b) in ("墓", "绝")
        ]
        weak_flying = []
        if fly_facts["is_xunkong"]:
            weak_flying.append("旬空")
        if fly_facts["is_month_clash"]:
            weak_flying.append("月破")
        if not flying_monthly["monthly_supported"]:
            weak_flying.append("月令休囚层")
        if any(stages[ELEMENTS[fly]].get(b) in ("墓", "绝") for b in (month, day)):
            weak_flying.append("日月墓绝位关系")

        def condition(
            rule: str,
            name: str,
            matched: bool | None,
            selected: list[dict[str, Any]] | None = None,
            status: str = "relation_checked",
            notes: str = "",
        ) -> dict[str, Any]:
            return {
                "rule_id": rule,
                "condition": name,
                "matched": matched,
                "status": status,
                "actors": selected or [],
                "notes": notes,
            }

        supports = [
            condition(
                "hidden_calendar_generates",
                "伏神得日月生",
                any(a["location"] in ("day", "month") for a in generated),
                [a for a in generated if a["location"] in ("day", "month")],
            ),
            condition(
                "hidden_strength",
                "伏神旺相",
                None,
                status="requires_total_strength",
                notes="月令支持是一个输入，不替代总旺衰裁定",
            ),
            condition(
                "flying_generates_hidden",
                "伏神得飞神生",
                fly_relation == "生爻"
                and not conditions[h["position"] - 1].get("outgoing_obstructions"),
                [
                    {
                        "location": "flying",
                        "position": h["position"],
                        "branch": fly,
                        "relation": fly_relation,
                        "effect_status": (
                            "back_control_obstructs_outgoing_candidate"
                            if conditions[h["position"] - 1].get(
                                "outgoing_obstructions"
                            )
                            else "conditional"
                        ),
                    }
                ],
            ),
            condition(
                "moving_generates_hidden",
                "伏神得动爻生",
                actor_match([a for a in generated if a["location"] == "visible"]),
                [a for a in generated if a["location"] == "visible"],
                notes="保留生的方向；回头克来源不作可用生扶，合绊保留未知，仍须总旺衰裁定",
            ),
            condition(
                "flying_struck",
                "日月动爻冲克飞神",
                actor_match(flying_struck),
                flying_struck,
            ),
            condition(
                "flying_weak",
                "飞神空破休囚墓绝",
                None,
                status="candidate_relations_only",
                notes="、".join(weak_flying) or "未见已校核关系，仍须判总旺衰",
            ),
        ]
        obstructions = [
            condition(
                "hidden_no_qi",
                "伏神休囚无气",
                None,
                status="requires_total_strength",
                notes="月令休囚不等于无气",
            ),
            condition(
                "hidden_calendar_struck",
                "伏神被日月冲克",
                bool(hidden_struck),
                hidden_struck,
            ),
            condition(
                "strong_flying_controls",
                "旺相飞神克伏",
                None,
                status="requires_total_strength",
                notes=f"飞伏五行关系为{fly_relation}；飞神月令层为{flying_monthly['category']}",
            ),
            condition(
                "hidden_tomb_cessation",
                "伏神墓绝于日月飞爻",
                bool(hidden_tombs) if ELEMENTS[branch] != "火" else None,
                hidden_tombs,
                (
                    "table_gap_or_relation"
                    if ELEMENTS[branch] == "火"
                    else "position_relation_only"
                ),
                "墓绝位关系不直接等于入墓真绝",
            ),
            condition(
                "weak_hidden_void_break",
                "休囚伏神旬空月破",
                None,
                status="requires_total_strength",
                notes=f"月令层{monthly['category']}；旬空{hidden_facts['is_xunkong']}；月破{hidden_facts['is_month_clash']}",
            ),
        ]
        results.append(
            {
                "position": h["position"],
                "branch": branch,
                "flying_branch": fly,
                "monthly_strength": monthly,
                "flying_monthly_strength": flying_monthly,
                "supporting_conditions": supports,
                "obstructing_conditions": obstructions,
                "table_gaps": (
                    ["火的帝旺、绝四位表未完成校勘"]
                    if ELEMENTS[branch] == "火" or ELEMENTS[fly] == "火"
                    else []
                ),
                "adjudication": "requires_total_strength_and_interaction_resolution",
                "source_url": scan_url(110),
                "scope": "六项支持、五项阻碍分别取证；不以数量相减断能否出伏，也不把有支持条件直接作吉断。",
            }
        )
    return results
