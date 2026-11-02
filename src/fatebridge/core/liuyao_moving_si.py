"""Target-specific moving-Si growth; raw fire/metal relations stay intact."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_metal_moving import prove_moving_earth_sources
from .liuyao_relations import ELEMENTS, element_relation

INTERNAL_KEY = "_metal_moving_si_growth"
PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-moving-si-v40.json")
    .read_text(encoding="utf-8")
)


def moving_si_context(
    row: dict[str, Any],
    monthly: dict[str, Any],
    month: str,
    day_ganzhi: str,
    lines: list[dict[str, Any]],
    assessment: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    actors = [r for r in lines if r["change"] and r["branch"] == "巳"]
    if row["element"] != "金" or not actors:
        return None
    p = row["position"]
    path = f"liuyao_evidence.conditional_analysis.growth_conditions.lines.{p - 1}.moving_si"
    roots = []
    for location, branch in [("month", month), ("day", day_ganzhi[1])]:
        relation = element_relation(ELEMENTS[branch], "金")
        if relation not in ("生爻", "比和") or (
            location == "month" and monthly["monthly_supported"] is not True
        ):
            continue
        actor_path = None
        if assessment is not None:
            supports = assessment["lines"][p - 1]["strength"]["supports"]
            i = next(
                i
                for i, a in enumerate(supports)
                if a["location"] == location and a["branch"] == branch
            )
            actor_path = f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p - 1}.strength.supports.{i}"
        roots.append(
            dict(
                location=location,
                branch=branch,
                relation=relation,
                source_path=actor_path,
            )
        )
    moving = None
    if assessment is not None:
        moving = prove_moving_earth_sources(
            subject_position=p,
            lines=lines,
            assessment=assessment,
            generation=assessment["generation_conditions"],
            source_path=path + ".moving_support",
            profile=PROFILE,
            scope="只核金爻以外的有独立根实际动土，不以动巳信用或该金爻自证。",
        )
    support = True if roots or moving and moving["condition_match"] is True else None
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        position=p,
        branch=row["branch"],
        actual_si_positions=[r["position"] for r in actors],
        textual_encounter_condition=True,
        support_condition_match=support,
        calendar_supports=roots,
        **({"moving_support": moving} if moving is not None else {}),
        source_path=path,
        source_url=PROFILE["source"]["url"] + "#page=97",
        source_sha256=PROFILE["source"]["sha256"],
        actual_total_effect_adjudicated=False,
        scope="实际动巳的遇长生资格与普通克制许可分列；同版第85页仍有金得日扶而称巳克的明例，合并效力未裁定。独立生扶未核不等于无气，其他午火、日月、空破及受方门槛另审。",
    )


def contextual_pair(
    source: dict[str, Any], target: dict[str, Any], condition: dict[str, Any]
) -> bool:
    return bool(
        source["change"]
        and source["branch"] == "巳"
        and target["element"] == "金"
        and INTERNAL_KEY in condition
    )


def qualify_control(
    source: dict[str, Any],
    target: dict[str, Any],
    condition: dict[str, Any],
    source_admission: bool | None,
    raw_match: bool | None,
    raw_status: str,
) -> tuple[bool | None, str, dict[str, Any]]:
    if not contextual_pair(source, target, condition):
        return raw_match, raw_status, {}
    context = condition[INTERNAL_KEY]
    i = context["actual_si_positions"].index(source["position"])
    growth = (
        False
        if source_admission is False
        else (
            True
            if source_admission is True and context["support_condition_match"] is True
            else None
        )
    )
    status = (
        "moving_si_growth_and_control_effect_unresolved"
        if growth is True
        else (
            raw_status
            if raw_match is False
            else "moving_si_growth_or_control_requires_review"
        )
    )
    return (
        raw_match,
        raw_status,
        dict(
            raw_condition_match=raw_match,
            raw_status=raw_status,
            metal_si_growth_condition=growth,
            source_control_admission=source_admission,
            metal_si_growth_source_path=context["source_path"] + f".sources.{i}",
            metal_si_ruleset_id=PROFILE["ruleset_id"],
            metal_si_ruleset_version=PROFILE["ruleset_version"],
            metal_si_combined_effect_condition=None,
            metal_si_effect_status=status,
        ),
    )


def publish_context(
    context: dict[str, Any], controls: list[dict[str, Any]]
) -> dict[str, Any]:
    result = deepcopy(context)
    sources = []
    for i, position in enumerate(context["actual_si_positions"]):
        control = next(
            c
            for c in controls
            if c["source_position"] == position
            and c["target_position"] == context["position"]
        )
        sources.append(
            dict(
                source_position=position,
                source_branch="巳",
                raw_relation="克爻",
                raw_control_condition=control["raw_condition_match"],
                source_control_admission=control["source_control_admission"],
                growth_condition_match=control["metal_si_growth_condition"],
                qualified_control_condition=control["condition_match"],
                combined_effect_condition=control["metal_si_combined_effect_condition"],
                control_source_path=control["fact_path"],
                source_path=context["source_path"] + f".sources.{i}",
                status=control["metal_si_effect_status"],
            )
        )
    result["sources"] = sources
    values = [s["growth_condition_match"] for s in sources]
    result["condition_match"] = (
        True if True in values else None if None in values else False
    )
    result["combined_effect_adjudicated"] = False
    result["cross_passage_source_urls"] = [
        PROFILE["source"]["url"] + "#page=85",
        PROFILE["source"]["url"] + "#page=97",
    ]
    return result


def actor_reason(control: dict[str, Any]) -> str:
    if control["metal_si_growth_condition"] is True:
        return "普通克制许可与动巳遇长生资格并见，合并效力待审"
    if control["condition_match"] is True:
        return "普通克制许可按原条件保留，动巳长生资格待审"
    if control["condition_match"] is None:
        return "普通克制许可或动巳长生资格待审"
    return "实际动巳来源未匹配当前作用门槛"


def finalize_moving_si(
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    assessment: dict[str, Any],
    control_conditions: dict[str, Any],
    month: str,
    day_ganzhi: str,
) -> None:
    """Add distinct predicates after ordinary permissions have stabilized."""
    by_position = {r["position"]: r for r in lines}
    for row, condition in zip(lines, conditions):
        context = moving_si_context(
            row, condition["monthly_strength"], month, day_ganzhi, lines, assessment
        )
        if context is not None:
            condition[INTERNAL_KEY] = context
    controls = {}
    for control in control_conditions["controls"]:
        p, q = control["source_position"], control["target_position"]
        if not contextual_pair(by_position[p], by_position[q], conditions[q - 1]):
            continue
        _, _, extra = qualify_control(
            by_position[p],
            by_position[q],
            conditions[q - 1],
            control["source_control_admission"],
            control["raw_condition_match"],
            control["raw_status"],
        )
        control.update(extra)
        controls[p, q] = control
    for assessed in assessment["lines"]:
        q = assessed["position"]
        for actor in (
            assessed["strength"]["oppositions"]
            + assessed["strength"]["blocked_oppositions"]
        ):
            key = (actor.get("position"), q)
            if actor["location"] != "visible" or key not in controls:
                continue
            control = controls[key]
            actor.update(
                metal_si_growth_condition=control["metal_si_growth_condition"],
                metal_si_combined_effect_condition=None,
                qualification_source_path=control["metal_si_growth_source_path"],
            )
            actor["reason"] = actor_reason(control)
