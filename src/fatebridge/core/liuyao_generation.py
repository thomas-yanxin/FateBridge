"""Outgoing generation conditions and target admission are separate facts."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files
from typing import Any

from .liuyao_activity import activity_condition
from .liuyao_metal_change import outgoing_blocker
from .liuyao_month_break import day_value_exception, month_opposition_applies
from .liuyao_penalty import qualify_yin_generation
from .liuyao_relations import ELEMENTS, branch_facts, element_relation, xunkong

PROFILE: dict[str, Any] = json.loads(
    files("fatebridge.data")
    .joinpath("classical/liuyao-generation-v11.json")
    .read_text(encoding="utf-8")
)


def target_admission(
    row: dict[str, Any], observation: dict[str, Any], month: str, day_ganzhi: str
) -> tuple[bool | None, str]:
    facts = branch_facts(row["branch"], month, day_ganzhi[1], xunkong(day_ganzhi))
    if (
        facts["is_month_clash"]
        and element_relation(ELEMENTS[day_ganzhi[1]], row["element"]) == "克爻"
        and not observation["supports"]
        and not observation["pending_supports"]
    ):
        return False, "month_broken_day_controlled_without_independent_root"
    if facts["is_xunkong"] and not facts["is_day_clash"]:
        return None, "target_current_void_waits_for_filling"
    if facts["is_month_clash"] and day_value_exception(
        row["branch"], month, day_ganzhi[1]
    ):
        if observation["harms"]:
            return None, "day_value_month_break_other_controls_require_resolution"
        return True, "day_value_excludes_month_only_admission_obstruction"
    if month_opposition_applies(row["branch"], month, day_ganzhi[1]):
        return None, "target_month_break_requires_resolution"
    return True, "no_listed_target_admission_obstruction"


def generation_sources(
    *,
    lines: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    observations: dict[int, dict[str, Any]],
    grounded: set[int],
    month: str,
    day_ganzhi: str,
) -> dict[int, dict[str, Any]]:
    all_static = not any(r["change"] for r in lines)
    sources = {}
    for row in lines:
        p = row["position"]
        c, o = conditions[p - 1], observations[p]
        facts = branch_facts(row["branch"], month, day_ganzhi[1], xunkong(day_ganzhi))
        activity = activity_condition(row, c)
        back_support = next(
            (a for a in o["supports"] if a["location"] == "changed"), None
        )
        back_pending = any(a["location"] == "changed" for a in o["pending_supports"])
        back_condition = True if back_support else None if back_pending else False
        calendar_harms = [a for a in o["harms"] if a["location"] in ("day", "month")]
        if outgoing_blocker(c) is None:
            match, status = None, "own_si_growth_or_back_control_pending"
        elif c.get("outgoing_obstructions"):
            match, status = False, "own_back_control_obstructs_generation"
        elif activity is None:
            match, status = None, "generation_activity_requires_resolution"
        elif activity is False and not (
            all_static
            and (
                c["monthly_strength"]["monthly_supported"]
                or day_value_exception(row["branch"], month, day_ganzhi[1])
            )
        ):
            match, status = None, "static_outside_current_all_static_generation_scope"
        elif c["binding_cues"]:
            match, status = None, "generation_binding_requires_release"
        elif facts["is_xunkong"] and not facts["is_day_clash"]:
            match, status = None, "source_current_void_waits_for_filling"
        elif month_opposition_applies(row["branch"], month, day_ganzhi[1]):
            match, status = None, "source_month_break_requires_resolution"
        elif any(a["location"] == "visible" for a in o["harms"]):
            match, status = None, "generation_competing_control_requires_resolution"
        elif p in grounded:
            match, status = True, "grounded_source_generation_condition_matched"
        elif activity is True and back_condition is True:
            match, status = True, "own_back_generation_licenses_original_generation"
        elif (
            calendar_harms
            and any(a.get("harm_condition_match", True) is True for a in calendar_harms)
            and not o["supports"]
            and not o["pending_supports"]
            and not o["possible_supports"]
        ):
            match, status = (
                False,
                "unsupported_controlled_source_generation_not_matched",
            )
        else:
            match, status = None, "generation_support_requires_resolution"
        sources[p] = dict(
            position=p,
            branch=row["branch"],
            condition_match=match,
            status=status,
            activity_condition_match=activity,
            back_generation_condition=back_condition,
            back_generation_source_path=f"liuyao_evidence.conditional_analysis.back_generation_conditions.sources.{p-1}",
            strength_supported_unopposed=p in grounded,
            retained_calendar_oppositions=deepcopy(calendar_harms),
            source_path=f"liuyao_evidence.conditional_analysis.generation_conditions.sources.{p-1}",
        )
    return sources


def source_explanation(source: dict[str, Any]) -> str:
    """Describe the computed source gate; do not re-adjudicate its predicates."""
    if source["condition_match"] is True:
        return "本爻向外生扶的来源资格已匹配；具体生向与受方条件仍须分别核对。"
    if source["condition_match"] is False:
        if source["status"] == "own_back_control_obstructs_generation":
            return "本爻受本位回头克，向外生扶受阻；另有生扶不自动解除该阻碍。"
        return "本爻未匹配所列向外生扶条件；不据此推永久无用或现实失败。"
    return "本爻向外生扶的来源资格仍待审；不能把待审写成不生，也不能当作已生。"


def target_explanation(reception: bool | None) -> str:
    """Receiving eligibility never certifies a particular source or benefit."""
    if reception is True:
        return "作为受生爻，未见所列当前承受障碍；这不证明某一来源已能生扶。"
    if reception is False:
        return "作为受生爻，本项月破日克且无已核独立根，不能据有生即认定受益。"
    return "作为受生爻，当前承受门槛仍待审；不以来源有力代替受方资格。"


def pair_qualification_explanation(pair: dict[str, Any]) -> str | None:
    """Read the target-specific gate and final path, without recalculating them."""
    permission = pair["target_yin_generation_allowed"]
    if permission is True:
        return None
    qualification = (
        "巳寅申限定条款排除这一路寅木生扶"
        if permission is False
        else "巳寅申所涉活动前提待审，这一路寅木生扶不能先行确认"
    )
    verdict = (
        "本条生扶路径条件未匹配"
        if pair["benefit_now"] is False
        else (
            "本条生扶路径条件仍待审"
            if pair["benefit_now"] is None
            else "本条生扶路径条件已匹配"
        )
    )
    return f"{qualification}；{verdict}；刑的总作用仍未裁定"


def build_generation_conditions(
    *,
    lines: list[dict[str, Any]],
    sources: dict[int, dict[str, Any]],
    observations: dict[int, dict[str, Any]],
    month: str,
    day_ganzhi: str,
    resolution_passes: int,
    selected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for source in lines:
        for target in lines:
            if (
                source["position"] == target["position"]
                or element_relation(source["element"], target["element"]) != "生爻"
            ):
                continue
            s = sources[source["position"]]
            reception, target_status = target_admission(
                target, observations[target["position"]], month, day_ganzhi
            )
            match = s["condition_match"]
            # Assessment has the same resolved activity context; use it rather
            # than reconstructing pending dark actors from row labels.
            context = observations[target["position"]]["penalty"]
            yin_permission = qualify_yin_generation(True, source["branch"], context)
            benefit = (
                False
                if False in (match, reception, yin_permission)
                else None if None in (match, reception, yin_permission) else True
            )
            pairs.append(
                dict(
                    source_position=source["position"],
                    target_position=target["position"],
                    source_branch=source["branch"],
                    target_branch=target["branch"],
                    relation="生爻",
                    condition_match=match,
                    status=s["status"],
                    target_reception_condition=reception,
                    target_status=target_status,
                    benefit_now=benefit,
                    target_yin_generation_allowed=yin_permission,
                    penalty_source_path=context["source_path"],
                    source_condition_path=s["source_path"],
                    source_path=f"liuyao_evidence.conditional_analysis.generation_conditions.generations.{len(pairs)}",
                    source_url=PROFILE["source"]["url"] + "#page=52",
                )
            )
            if note := pair_qualification_explanation(pairs[-1]):
                pairs[-1]["qualification_explanation"] = note
    focus = None
    if selected and selected["location"] == "visible":
        p = selected["position"]
        reception, status = target_admission(
            lines[p - 1], observations[p], month, day_ganzhi
        )
        focus = dict(
            position=p,
            branch=lines[p - 1]["branch"],
            source_condition_match=sources[p]["condition_match"],
            source_status=sources[p]["status"],
            source_condition_path=sources[p]["source_path"],
            source_explanation=source_explanation(sources[p]),
            target_reception_condition=reception,
            target_status=status,
            target_explanation=target_explanation(reception),
            scope="仅为本爻作为生源与受方的两项当前资格；不新增生向，不综合总效力。实际变爻、伏神及日月主体不借本爻的资格。",
        )
    return dict(
        ruleset_id=PROFILE["ruleset_id"],
        ruleset_version=PROFILE["ruleset_version"],
        source_url=PROFILE["source"]["url"] + "#page=52",
        source_sha256=PROFILE["source"]["sha256"],
        clauses=deepcopy(PROFILE["clauses"]),
        textual_issues=deepcopy(PROFILE["textual_issues"]),
        sources=list(sources.values()),
        generations=pairs,
        focus=focus,
        support_resolution_passes=resolution_passes,
        adjudication="generation_conditions_separate_from_strength_and_target_reception",
        scope="能向外生扶、整体旺相无伤与受生爻目下能受生分开核对。本位回头生可支持原爻向外生扶，不删除原日月克制；空破、合绊、回头克、多动制化及用神无根另审。变爻仍只生克本位原爻，不能跨位直生他爻。不按生扶条数或路径断现实成败。",
    )
