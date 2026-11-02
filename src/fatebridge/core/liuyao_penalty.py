"""Scoped triad presence and growth exclusion, without certifying injury."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_condition

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-penalty-v20.json")
    .read_text(encoding="utf-8")
)
ROOT = "liuyao_evidence.conditional_analysis.penalty_conditions"
INTERNAL_KEY = "_si_yin_shen"


def penalty_context(
    *,
    branch: str,
    month: str,
    day: str,
    position: int | None = None,
    own_changed: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
    source_path: str | None = None,
    subject_kind: str = "visible",
) -> dict[str, Any]:
    actors: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    applicable = branch == "巳"
    if applicable:
        for location, b in (("month", month), ("day", day)):
            if b in ("寅", "申"):
                actors.append(
                    dict(location=location, branch=b, presence_condition_match=True)
                )
        if own_changed in ("寅", "申"):
            actors.append(
                dict(
                    location="changed",
                    position=position,
                    branch=own_changed,
                    presence_condition_match=True,
                )
            )
        for row, c in zip(lines or [], conditions or []):
            p, b = row["position"], row["branch"]
            if (p != position or subject_kind == "hidden") and b in ("寅", "申"):
                active = activity_condition(row, c)
                actor = dict(
                    location="visible",
                    position=p,
                    branch=b,
                    presence_condition_match=active,
                    activity_source_path=f"liuyao_evidence.conditional_analysis.lines.{p-1}.activity_condition_match",
                )
                if active is False:
                    ignored.append(
                        {**actor, "reason": "static_original_not_a_moving_actor"}
                    )
                else:
                    actors.append(actor)
            changed = row.get("changed_branch")
            if changed in ("寅", "申") and (p != position or own_changed is None):
                ignored.append(
                    dict(
                        location="changed",
                        position=p,
                        branch=changed,
                        presence_condition_match=False,
                        reason=(
                            "other_parent_transformation"
                            if row["change"]
                            else "static_changed_chart_label"
                        ),
                    )
                )
    values = []
    for b in ("寅", "申"):
        matches = [a["presence_condition_match"] for a in actors if a["branch"] == b]
        values.append(True if True in matches else None if None in matches else False)
    presence = False if False in values else None if None in values else True
    growth_applicable = applicable and day == "寅"
    allowed = None if presence is None else not presence
    return dict(
        position=position,
        branch=branch,
        subject_kind=subject_kind,
        applicable=applicable,
        condition_match=presence,
        effect_condition_match=None if presence is not False else False,
        yin_generation_allowed=allowed,
        day_yin_growth_applicable=growth_applicable,
        day_yin_growth_allowed=allowed if growth_applicable else None,
        actors=actors,
        ignored_actors=ignored,
        source_path=source_path or (f"{ROOT}.lines.{position-1}" if position else ROOT),
        source_url=PROFILE["source"]["url"] + "#page=98",
        status=(
            "scoped_triad_present_effect_unadjudicated"
            if presence is True
            else (
                "scoped_triad_activity_pending"
                if presence is None
                else "no_scoped_si_yin_shen_triad"
            )
        ),
    )


def attach_penalty_contexts(
    lines: list[dict[str, Any]], conditions: list[dict[str, Any]], month: str, day: str
) -> tuple[bool | None, ...]:
    for row, c in zip(lines, conditions):
        c[INTERNAL_KEY] = penalty_context(
            branch=row["branch"],
            month=month,
            day=day,
            position=row["position"],
            own_changed=row.get("changed_branch") if row["change"] else None,
            lines=lines,
            conditions=conditions,
        )
    return tuple(c[INTERNAL_KEY]["condition_match"] for c in conditions)


def publish_penalty_conditions(
    conditions: list[dict[str, Any]], focus: dict[str, Any]
) -> dict[str, Any]:
    rows = [deepcopy(c[INTERNAL_KEY]) for c in conditions]
    selected = focus["selected"]
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        source_url=PROFILE["source"]["url"] + "#page=98",
        source_sha256=PROFILE["source"]["sha256"],
        clauses=deepcopy(PROFILE["clauses"]),
        precedence=deepcopy(PROFILE["precedence"]),
        lines=rows,
        quotation_errata=deepcopy(PROFILE["quotation_errata"]),
        focus=(
            deepcopy(rows[selected["position"] - 1])
            if selected and selected["location"] == "visible"
            else None
        ),
        scope=PROFILE["scope"],
    )


def qualify_yin_generation(
    value: bool | None, branch: str, context: dict[str, Any]
) -> bool | None:
    """Restrict one Yin-to-Si credit, without changing its raw relation/source."""
    permission = context["yin_generation_allowed"] if branch == "寅" else True
    return (
        False
        if False in (value, permission)
        else None if None in (value, permission) else True
    )


def penalty_explanation(context: dict[str, Any]) -> str | None:
    """Render the final scoped context, without re-deriving actor activity."""
    presence = context["condition_match"]
    if presence is False:
        return None
    if presence is None:
        return (
            "申爻活动资格待审，寅日长生生扶不能先行确认；刑的总作用未裁定"
            if context["day_yin_growth_applicable"]
            else "三支活动资格待审，寅生扶不能先行确认；刑的总作用未裁定"
        )
    if context["day_yin_growth_applicable"]:
        text = "巳寅申三支条件已核，寅日不按长生或同一日生扶计入；刑的总作用未裁定"
        if any(
            a["location"] == "changed" and a["branch"] == "寅"
            for a in context["actors"]
        ):
            text += "；本位变寅亦不计为回头生扶，其他独立生扶仍保留"
        return text
    return "巳寅申三支条件已核，所列寅月、动寅及本位变寅不计为寅生扶；刑的总作用未裁定，其他独立生扶仍保留"
