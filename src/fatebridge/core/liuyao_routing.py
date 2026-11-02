"""Qualify successive-generation paths without certifying final relief."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from itertools import product
from typing import Any

from .liuyao_activity import activity_condition
from .liuyao_metal_change import outgoing_blocker
from .liuyao_penalty import qualify_yin_generation
from .liuyao_relations import element_relation

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-routing-v13.json")
    .read_text(encoding="utf-8")
)


def all_conditions(values: list[bool | None]) -> bool | None:
    return False if False in values else None if None in values else True


def any_conditions(values: list[bool | None]) -> bool | None:
    return True if True in values else None if None in values else False


def build_routing_conditions(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    focus: dict[str, Any],
    generation: dict[str, Any],
    legacy_chains: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    hidden_conditions: list[dict[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        source_url=PROFILE["source"]["url"] + "#page=54",
        source_sha256=PROFILE["source"]["sha256"],
        clauses=deepcopy(PROFILE["clauses"]),
        textual_issues=deepcopy(PROFILE["textual_issues"]),
        routes=[],
        focus=None,
        adjudication="successive_generation_conditions_not_final_relief",
        scope="元忌活动资格、忌生元、元受生、元生用、用神承受门槛及合绊回头克分项合取；多条路径按或合并，不按条数投票。路径门槛匹配不等于直接克制已消失、全局化解或现实成功。伏神承受条件未裁定时保留未知，不借飞神的同位条件；保留原始路径与直接克制方向。",
    )
    selected = focus["selected"]
    if selected is None:
        result["status"] = "requires_selected_focus"
        return result
    if selected["location"] not in ("visible", "hidden"):
        result["status"] = "focus_scope_not_supported"
        result["focus"] = dict(
            location=selected["location"],
            position=selected["position"],
            condition_match=None,
            status="focus_scope_not_supported",
        )
        return result
    result["status"] = "route_conditions_only"
    rows = {r["position"]: r for r in lines}
    cs = {c["position"]: c for c in conditions}
    roles = {r["position"]: r["role"] for r in focus["roles"]}
    activity = {p: activity_condition(row, cs[p]) for p, row in rows.items()}
    candidates = {
        role: [
            p for p in sorted(rows) if roles.get(p) == role and activity[p] is not False
        ]
        for role in ("元神", "忌神")
    }
    pairs = {
        (p["source_position"], p["target_position"]): p
        for p in generation["generations"]
    }
    sources = {s["position"]: s for s in generation["sources"]}
    legacy = {c["chain_id"]: (i, c) for i, c in enumerate(legacy_chains)}
    for j, y in product(candidates["忌神"], candidates["元神"]):
        first = pairs.get((j, y))
        if (
            first is None
            or element_relation(rows[y]["element"], selected["element"]) != "生爻"
        ):
            raise ValueError("元忌角色与接续相生方向不一致")
        f = selected["position"]
        second = pairs.get((y, f)) if selected["location"] == "visible" else None
        hidden_reception = (
            next(
                (
                    h["reception"]
                    for h in hidden_conditions
                    if h["position"] == f and h["branch"] == selected["branch"]
                ),
                None,
            )
            if selected["location"] == "hidden"
            else None
        )
        if selected["location"] == "visible" and second is None:
            raise ValueError("元神至明爻用神缺少同向生扶关系")
        bindings = [p for p in (j, y) if cs[p]["binding_cues"]]
        obstructions = [p for p in (j, y) if outgoing_blocker(cs[p]) is True]
        pending_obstructions = [p for p in (j, y) if outgoing_blocker(cs[p]) is None]
        stages: list[dict[str, Any]] = []

        def add(
            id: str,
            label: str,
            value: bool | None,
            paths: list[str],
            reason: str | None = None,
        ) -> None:
            stages.append(
                dict(
                    id=id,
                    label=label,
                    matched=value,
                    status=(
                        "condition_matched"
                        if value is True
                        else (
                            "condition_not_matched"
                            if value is False
                            else "requires_resolution"
                        )
                    ),
                    source_paths=paths,
                    reason=reason,
                )
            )

        add(
            "ji_activity",
            "忌神活动资格",
            activity[j],
            [
                f"liuyao_evidence.conditional_analysis.lines.{j-1}.activity_condition_match"
            ],
        )
        add(
            "yuan_activity",
            "元神活动资格",
            activity[y],
            [
                f"liuyao_evidence.conditional_analysis.lines.{y-1}.activity_condition_match"
            ],
        )
        add(
            "ji_generation",
            "忌神生元资格",
            first["condition_match"],
            [first["source_path"]],
            first["status"],
        )
        add(
            "yuan_reception",
            "元神当前受生门槛",
            all_conditions(
                [
                    first["target_reception_condition"],
                    first["target_yin_generation_allowed"],
                ]
            ),
            [first["source_path"]],
            first["target_status"],
        )
        add(
            "yuan_generation",
            "元神生用资格",
            all_conditions(
                [
                    sources[y]["condition_match"],
                    (
                        second["target_yin_generation_allowed"]
                        if second
                        else (
                            qualify_yin_generation(
                                True, rows[y]["branch"], hidden_reception["penalty"]
                            )
                            if hidden_reception
                            else None
                        )
                    ),
                ]
            ),
            [
                sources[y]["source_path"],
                (
                    second["source_path"]
                    if second
                    else (
                        hidden_reception["source_path"]
                        if hidden_reception
                        else "liuyao_evidence.conditional_analysis.hidden_conditions"
                    )
                ),
            ],
            (
                "target_yin_generation_excluded"
                if second and second["target_yin_generation_allowed"] is False
                else sources[y]["status"]
            ),
        )
        add(
            "focus_reception",
            "用神当前承受门槛",
            (
                second["target_reception_condition"]
                if second
                else (hidden_reception["condition_match"] if hidden_reception else None)
            ),
            [
                (
                    second["source_path"]
                    if second
                    else (
                        hidden_reception["source_path"]
                        if hidden_reception
                        else "liuyao_evidence.conditional_analysis.hidden_conditions"
                    )
                )
            ],
            (
                second["target_status"]
                if second
                else (
                    hidden_reception["status"]
                    if hidden_reception
                    else "hidden_target_reception_not_adjudicated"
                )
            ),
        )
        permission = (
            False
            if bindings or obstructions
            else None if pending_obstructions else True
        )
        permission_reason = (
            "back_control_blocks_current_route"
            if obstructions
            else (
                "combination_blocks_current_route"
                if bindings
                else (
                    "own_si_qualification_requires_routing_review"
                    if pending_obstructions
                    else "no_listed_permission_obstruction"
                )
            )
        )
        add(
            "routing_permission",
            "无所列合绊及回头克阻断",
            permission,
            [f"liuyao_evidence.conditional_analysis.lines.{p-1}" for p in (j, y)],
            permission_reason,
        )
        match = all_conditions([s["matched"] for s in stages])
        status = (
            "routing_conditions_matched"
            if match is True
            else (
                "routing_conditions_not_matched"
                if match is False
                else "routing_conditions_require_review"
            )
        )
        chain_id = f"ji-{j}:yuan-{y}:{selected['location']}-{f}"
        path = f"liuyao_evidence.conditional_analysis.routing_conditions.routes.{len(result['routes'])}"
        route = dict(
            chain_id=chain_id,
            positions=[j, y, f],
            focus_location=selected["location"],
            condition_match=match,
            status=status,
            conditions=stages,
            blocked_conditions=[s["id"] for s in stages if s["matched"] is False],
            pending_conditions=[s["id"] for s in stages if s["matched"] is None],
            binding_positions=bindings,
            obstructed_positions=obstructions,
            source_path=path,
            source_url=result["source_url"],
            legacy_source_path=None,
        )
        if chain_id in legacy:
            i, raw = legacy[chain_id]
            route["legacy_source_path"] = (
                f"liuyao_evidence.conditional_analysis.role_effects.chains.{i}"
            )
            raw.update(
                route_condition_match=match, route_status=status, route_source_path=path
            )
        result["routes"].append(route)
    for edge in edges:
        if (
            selected["location"] != "visible"
            or edge["source_kind"] != "base"
            or edge["target_kind"] != "base"
            or edge["target_position"] != selected["position"]
            or edge["relation"] != "克爻"
        ):
            continue
        routes = [
            r for r in result["routes"] if r["positions"][0] == edge["source_position"]
        ]
        if not routes:
            continue
        value = any_conditions([r["condition_match"] for r in routes])
        edge.update(
            qualified_routing_condition=value,
            qualified_routing_status=(
                "routing_conditions_matched_not_final_relief"
                if value is True
                else (
                    "no_qualified_route_from_this_controller"
                    if value is False
                    else "routing_sources_or_target_unresolved"
                )
            ),
            conditional_routing_chain_ids=[
                r["chain_id"] for r in routes if r["condition_match"] is not False
            ],
            rejected_routing_chain_ids=[
                r["chain_id"] for r in routes if r["condition_match"] is False
            ],
        )
    value = any_conditions([r["condition_match"] for r in result["routes"]])
    result["focus"] = dict(
        location=selected["location"],
        position=selected["position"],
        condition_match=value,
        status=(
            "no_co_motion_route_candidates"
            if not result["routes"]
            else (
                "routing_conditions_matched_not_final_relief"
                if value is True
                else (
                    "no_current_qualified_route"
                    if value is False
                    else "routing_sources_or_target_unresolved"
                )
            )
        ),
    )
    return result
