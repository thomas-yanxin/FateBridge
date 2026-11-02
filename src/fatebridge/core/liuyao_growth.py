"""Named original-book qualification of metal growth at a Si day."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_metal_change import INTERNAL_KEY as OWN_SI_KEY
from .liuyao_metal_change import PROFILE as OWN_SI_PROFILE
from .liuyao_metal_moving import INTERNAL_KEY as METAL_KEY
from .liuyao_metal_moving import PROFILE as MOVING_PROFILE
from .liuyao_metal_moving import moving_growth_qualified
from .liuyao_moving_si import INTERNAL_KEY as MOVING_SI_KEY
from .liuyao_moving_si import PROFILE as MOVING_SI_PROFILE
from .liuyao_moving_si import publish_context
from .liuyao_penalty import INTERNAL_KEY
from .liuyao_relations import ELEMENTS, element_relation
from .liuyao_stages import query_stage

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-growth-v18.json")
    .read_text(encoding="utf-8")
)
METAL_SI_GROWTH_REASON = "已核月令独立生扶，巳日按长生条件"
METAL_SI_MOVING_REASON = "已核有独立根的动土生扶，巳日按长生条件"


def metal_si_month_supported(
    element: str, month: str, day: str, monthly: dict[str, Any]
) -> bool:
    return (
        element == "金"
        and day == "巳"
        and monthly["monthly_supported"] is True
        and element_relation(ELEMENTS[month], element) in ("生爻", "比和")
    )


def metal_si_growth_supported(
    element: str,
    month: str,
    day: str,
    monthly: dict[str, Any],
    moving_support: bool = False,
) -> bool:
    return metal_si_month_supported(element, month, day, monthly) or (
        element == "金" and day == "巳" and moving_support
    )


def build_growth_conditions(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    assessment: dict[str, Any],
    stages: dict[str, dict[str, str]],
    month: str,
    day_ganzhi: str,
    focus: dict[str, Any],
    control_conditions: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for row, c, assessed in zip(lines, conditions, assessment["lines"]):
        p, element = row["position"], row["element"]
        day = day_ganzhi[1]
        raw = query_stage(stages, element, day, ["长生", "帝旺"])
        exceptional = element == "金" and day == "巳"
        monthly = metal_si_month_supported(element, month, day, c["monthly_strength"])
        moving = moving_growth_qualified(c)
        match = (
            True
            if monthly or moving
            else None if exceptional else raw["condition_match"]
        )
        penalty = c.get(INTERNAL_KEY)
        if penalty and penalty["day_yin_growth_applicable"]:
            match = penalty["day_yin_growth_allowed"]
        path = f"liuyao_evidence.conditional_analysis.growth_conditions.lines.{p - 1}"
        strength = assessed["strength"]
        roots = [
            f"liuyao_evidence.conditional_analysis.classical_assessment.lines.{p - 1}.strength.supports.{i}"
            for i, actor in enumerate(strength["supports"])
            if monthly
            and actor["location"] == "month"
            and element_relation(ELEMENTS[actor["branch"]], element) in ("生爻", "比和")
        ]
        rows.append(
            dict(
                position=p,
                branch=row["branch"],
                element=element,
                day_branch=day,
                position_query=raw,
                position_match=raw["condition_match"],
                condition_match=match,
                **(
                    {"condition_match_scope": "day_branch_growth_only"}
                    if MOVING_SI_KEY in c
                    else {}
                ),
                penalty_growth_source_path=(
                    penalty["source_path"]
                    if penalty and penalty["day_yin_growth_applicable"]
                    else None
                ),
                penalty_growth_source_url=(
                    penalty["source_url"]
                    if penalty and penalty["day_yin_growth_applicable"]
                    else None
                ),
                day_yin_growth_excluded=(
                    (None if match is None else not match)
                    if penalty and penalty["day_yin_growth_applicable"]
                    else False
                ),
                metal_si_exception_applicable=exceptional,
                independent_month_support=monthly if exceptional else None,
                **(
                    {"own_changed_si": deepcopy(c[OWN_SI_KEY])}
                    if OWN_SI_KEY in c
                    else {}
                ),
                **(
                    {"moving_support": deepcopy(c[METAL_KEY])} if METAL_KEY in c else {}
                ),
                **(
                    {
                        "moving_si": publish_context(
                            c[MOVING_SI_KEY], control_conditions["controls"]
                        )
                    }
                    if MOVING_SI_KEY in c
                    else {}
                ),
                month_support_fact_paths=roots,
                raw_day_element_relation=element_relation(ELEMENTS[day], element),
                day_control_in_calendar_oppositions=any(
                    a["location"] == "day" and a["branch"] == day
                    for a in strength["oppositions"]
                ),
                other_oppositions=deepcopy(strength["oppositions"]),
                pending_supports=deepcopy(strength["pending_supports"]),
                status=(
                    "si_yin_shen_excludes_day_growth"
                    if penalty
                    and penalty["day_yin_growth_applicable"]
                    and match is False
                    else (
                        "si_yin_shen_day_growth_requires_activity"
                        if penalty
                        and penalty["day_yin_growth_applicable"]
                        and match is None
                        else (
                            "metal_si_month_supported_growth"
                            if monthly
                            else (
                                "metal_si_moving_source_supported_growth"
                                if moving
                                else (
                                    "metal_si_other_support_requires_review"
                                    if exceptional
                                    else raw["status"]
                                )
                            )
                        )
                    )
                ),
                source_path=path,
                source_url=PROFILE["source"]["url"] + "#page=97",
                actual_total_effect_adjudicated=False,
            )
        )
    selected = focus["selected"]
    moving_applicable = any("moving_support" in r for r in rows)
    own_applicable = any("own_changed_si" in r for r in rows)
    moving_si_applicable = any("moving_si" in r for r in rows)
    active_profile = (
        MOVING_SI_PROFILE
        if moving_si_applicable
        else (
            OWN_SI_PROFILE
            if own_applicable
            else MOVING_PROFILE if moving_applicable else PROFILE
        )
    )
    return dict(
        ruleset_id=active_profile["ruleset_id"],
        ruleset_version=active_profile["ruleset_version"],
        source_url=PROFILE["source"]["url"] + "#page=97",
        source_sha256=PROFILE["source"]["sha256"],
        clauses=deepcopy(
            MOVING_SI_PROFILE["clauses"] if moving_si_applicable else PROFILE["clauses"]
        ),
        lines=rows,
        focus=(
            deepcopy(rows[selected["position"] - 1])
            if selected and selected["location"] == "visible"
            else None
        ),
        scope=(
            "卦中实际动巳分别核独立生扶与来源资格，遇长生资格不自动取消普通克制许可；同版第85、97页合并效力未裁定。原火克金、日巳及本位化巳分别列，其他反制不因本项解除。"
            if moving_si_applicable
            else (
                "金爻实际本位化巳另列独立生扶和变支门槛，保留原火克金关系；本项已核长生才排除同一本位巳火的回头克，其他反制及全局效力另审。日巳分支仍按同次日长生结果读取。"
                if own_applicable
                else (
                    "金逢巳日须审独立旺相生扶，已核月令或有独立根的实际动土分支在共享历法作用条件中按长生；原五行火克金关系保留。巳爻寅日另核同次penalty_conditions，三支已核则不计该日长生生扶，申活动未知则保留未知；刑的总作用未裁定。无月扶不证明全局无气，其他未核扶源与变支仍待审；不以本条解除其他克制或断现实成败。"
                    if moving_applicable
                    else "金逢巳日须审独立旺相生扶，已核月令分支在共享历法作用条件中按长生；原五行火克金关系保留。巳爻寅日另核同次penalty_conditions，三支已核则不计该日长生生扶，申活动未知则保留未知；刑的总作用未裁定。无月扶不证明全局无气，其他扶源与变支仍待审；不以本条解除其他克制或断现实成败。"
                )
            )
        ),
    )
