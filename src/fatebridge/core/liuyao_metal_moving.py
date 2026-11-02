"""Prove a moving-earth root without assuming the queried metal's Si growth."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_relations import ELEMENTS, element_relation

INTERNAL_KEY = "_metal_si_moving_support"
PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-metal-moving-v34.json")
    .read_text(encoding="utf-8")
)


def prove_moving_earth_sources(
    *,
    subject_position: int | None,
    lines: list[dict[str, Any]],
    assessment: dict[str, Any],
    generation: dict[str, Any],
    source_path: str,
    profile: dict[str, Any],
    scope: str,
) -> dict[str, Any] | None:
    candidates = [
        r
        for r in lines
        if r["element"] == "土" and r["change"] and r["position"] != subject_position
    ]
    if not candidates:
        return None
    rows = {r["position"]: r for r in lines}
    sources = {r["position"]: r for r in generation["sources"]}
    pairs = {
        (r["source_position"], r["target_position"]): r
        for r in generation["generations"]
    }
    strengths = {r["position"]: r["strength"] for r in assessment["lines"]}
    proofs: dict[int, list[dict[str, Any]]] = {}
    # Calendar and actual returned-generation anchors have no dependency on
    # the queried visible metal. Never use a final source_grounded bit alone.
    for p in sorted(rows):
        if p == subject_position:
            continue
        own_element = rows[p]["element"]
        for i, actor in enumerate(strengths[p]["supports"]):
            location, branch = actor["location"], actor["branch"]
            if (
                location == "day" and branch == "巳" and own_element in ("金", "土")
            ) or (own_element == "土" and location == "changed" and branch == "巳"):
                continue
            calendar_anchor = location in ("month", "day") and element_relation(
                ELEMENTS[branch], own_element
            ) in ("生爻", "比和")
            returned_anchor = (
                location == "changed" and actor.get("back_generation_condition") is True
            )
            if calendar_anchor or returned_anchor:
                proofs[p] = [
                    dict(
                        position=p,
                        location=location,
                        branch=branch,
                        kind=(
                            "calendar" if calendar_anchor else "actual_back_generation"
                        ),
                        source_path=(
                            f"liuyao_evidence.conditional_analysis.classical_assessment."
                            f"lines.{p-1}.strength.supports.{i}"
                        ),
                    )
                ]
                break
    changed = True
    while changed:
        changed = False
        for p in sorted(rows):
            if p == subject_position or p in proofs:
                continue
            for i, actor in enumerate(strengths[p]["supports"]):
                q = actor.get("position")
                if actor["location"] != "visible" or q not in proofs:
                    continue
                source = sources[q]
                if (
                    source["condition_match"] is not True
                    or source["activity_condition_match"] is not True
                ):
                    continue
                relation = element_relation(rows[q]["element"], rows[p]["element"])
                pair = pairs.get((q, p))
                if relation == "生爻":
                    admitted = pair is not None and pair["benefit_now"] is True
                else:
                    admitted = (
                        relation == "比和"
                        and actor.get("source_grounded") is True
                        and not actor.get("held")
                        and not actor.get("activity_pending")
                    )
                if admitted:
                    proofs[p] = [
                        *deepcopy(proofs[q]),
                        dict(
                            position=p,
                            location="visible",
                            branch=rows[q]["branch"],
                            source_position=q,
                            kind="qualified_moving_support",
                            source_path=(
                                f"liuyao_evidence.conditional_analysis.classical_assessment."
                                f"lines.{p-1}.strength.supports.{i}"
                            ),
                        ),
                    ]
                    changed = True
                    break
    published = []
    for row in sorted(candidates, key=lambda r: r["position"]):
        p = row["position"]
        source = sources[p]
        complete = p in proofs
        match = (
            source["condition_match"] is True
            and source["activity_condition_match"] is True
            and complete
        )
        published.append(
            dict(
                source_position=p,
                source_branch=row["branch"],
                source_condition_match=source["condition_match"],
                activity_condition_match=source["activity_condition_match"],
                source_generation_path=source["source_path"],
                independent_root_proven=complete,
                root_proof=deepcopy(proofs.get(p, [])),
                condition_match=match,
                status=(
                    "qualified_moving_earth_with_independent_root"
                    if match
                    else (
                        "moving_earth_source_not_matched"
                        if source["condition_match"] is False
                        else (
                            "moving_earth_qualification_pending"
                            if source["condition_match"] is None
                            or source["activity_condition_match"] is not True
                            else "moving_earth_independent_root_not_proven"
                        )
                    )
                ),
            )
        )
    return dict(
        ruleset_id=profile["ruleset_id"],
        ruleset_version=profile["ruleset_version"],
        source_url=profile["source"]["url"] + "#page=97",
        source_sha256=profile["source"]["sha256"],
        source_path=source_path,
        condition_match=any(r["condition_match"] for r in published),
        excluded_target_position=subject_position,
        candidates=published,
        successful_positions=[
            r["source_position"] for r in published if r["condition_match"]
        ],
        scope=scope,
    )


def moving_support_context(
    *,
    element: str,
    subject_position: int | None,
    lines: list[dict[str, Any]],
    assessment: dict[str, Any],
    generation: dict[str, Any],
    day_ganzhi: str,
    source_path: str,
) -> dict[str, Any] | None:
    if element != "金" or day_ganzhi[1] != "巳":
        return None
    return prove_moving_earth_sources(
        subject_position=subject_position,
        lines=lines,
        assessment=assessment,
        generation=generation,
        source_path=source_path,
        profile=PROFILE,
        scope="只核已获向外生扶资格且有独立根的实际动土；未证明不等于全局无扶。排除被判断金爻及金巳日长生、土巳日或本位巳变支自证；不解除受方空破、回头克或其他反制。",
    )


def moving_growth_qualified(condition: dict[str, Any]) -> bool:
    return condition.get(INTERNAL_KEY, {}).get("condition_match") is True
