"""Selected 求名 supplement; literal 時序/方道 never become event dates."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_roles import LABELS, ROLES


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/reputation-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_reputation_supplement_nlc1925_v1"
        or profile["version"] != "1.0.0"
        or len(profile["rules"]) != 5
        or set(profile["time_classes"]) != set("乾坤震巽坎离艮兑")
        or set(profile["fangdao_classes"]) != set("乾坤震巽坎离艮兑")
    ):
        raise ValueError("Unknown or incomplete selected reputation supplement")
    return profile


def reputation_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _source_rule(rule_id: str) -> dict[str, Any]:
    return deepcopy(next(r for r in _profile()["rules"] if r["id"] == rule_id))


def _time_reference(trigram: str) -> dict[str, Any]:
    profile = _profile()
    return {
        **deepcopy(profile["time_classes"][trigram]),
        "source": deepcopy(profile["source"]),
        "comparison_source": deepcopy(profile["comparison_sources"]["volume1"]),
        "calendar_anchor": None,
        "calendar_month_basis": None,
        "numeric_day_count": None,
        "candidate_event_dates": None,
    }


def _reading(
    cast: dict[str, Any],
    stages: list[dict[str, Any]],
    control: dict[str, Any],
    seasonal: dict[str, Any] | None,
    context: dict[str, Any] | None,
    *,
    fact_prefix: str,
    interpretation_prefix: str,
    context_fact_path: str,
) -> dict[str, Any]:
    profile = _profile()
    if [r["role"] for r in stages] != list(ROLES):
        raise ValueError("Reputation supplement requires four actual auxiliary roles")
    body = cast["body_trigram"]["name"]
    qualifications = control["qualifications"]
    if [r["role"] for r in qualifications] != list(ROLES):
        raise ValueError("Reputation countercontrol must retain this candidate's roles")
    strengths = {
        r["role"]: (i, r)
        for i, r in enumerate(seasonal["trigrams"] if seasonal else [])
    }
    strength_prefix = (
        fact_prefix + ".seasonal_strength"
        if fact_prefix == "meihua"
        else interpretation_prefix + ".seasonal_strength"
    )
    roles = []
    for i, row in enumerate(stages):
        if row["body"] != body or not row["fact_path"].startswith(fact_prefix + "."):
            raise ValueError("Reputation facts must use this candidate's original body")
        qualification = qualifications[i]
        if (
            qualification["target_fact_path"],
            qualification["original_relation_to_body"],
        ) != (row["fact_path"], row["relation"]):
            raise ValueError("Reputation and countercontrol facts must remain bound")
        strength = strengths.get(row["role"])
        roles.append(
            {
                "role": row["role"],
                "trigram": row["trigram"],
                "relation": row["relation"],
                "trigram_fact_path": row["fact_path"] + ".name",
                "relation_fact_path": f"{fact_prefix}.stage_relations.{i}.relation",
                "countercontrol_qualification": deepcopy(qualification),
                "countercontrol_fact_path": f"{interpretation_prefix}.internal_countercontrol.qualifications.{i}",
                "seasonal_strength": strength[1]["strength"] if strength else None,
                "strength_fact_path": (
                    f"{strength_prefix}.trigrams.{strength[0]}.strength"
                    if strength
                    else None
                ),
            }
        )
    supporters = [r for r in roles if r["relation"] == "用生体"]
    attackers = [r for r in roles if r["relation"] == "用克体"]
    office = context.get("currently_in_office") if context is not None else None
    appointment = (
        context.get("seeking_official_appointment") if context is not None else None
    )
    if any(
        value is not None and type(value) is not bool for value in [office, appointment]
    ):
        raise ValueError("Reputation declarations must be booleans or unknown")
    office_applies = (
        False if not attackers or office is False else True if office is True else None
    )
    support_times = [
        {**deepcopy(row), "time_reference": _time_reference(row["trigram"])}
        for row in supporters
    ]
    attacker_times = [
        {
            **deepcopy(row),
            "selected_office_clause_applies": office_applies,
            "time_reference": _time_reference(row["trigram"]),
        }
        for row in attackers
    ]
    line = cast["seed"]["moving_line"] if "seed" in cast else cast["moving_line"]
    position = "lower" if line <= 3 else "upper"
    changed = cast["changed_hexagram"][position]["name"]
    path = f"{fact_prefix}.changed_hexagram.{position}"
    if (stages[-1]["trigram"], stages[-1]["fact_path"]) != (changed, path):
        raise ValueError("Reputation direction must use this candidate's changed use")
    direction = deepcopy(profile["fangdao_classes"][changed])
    no_attacker = {
        "source_rule": _source_rule("without_attacker"),
        "selected_internal_scope_matches": not bool(attackers),
        "known_internal_attacker_roles": [r["role"] for r in attackers],
        "full_source_clause_applies": False if attackers else None,
        "full_inner_outer_absence_authenticated": False,
        "body_time_reference": _time_reference(body) if not attackers else None,
        "body_fact_path": fact_prefix + ".body_trigram.name",
    }
    direction.update(
        source_rule=_source_rule("appointment_direction"),
        declared_appointment_condition_met=appointment,
        selected_policy_applies=appointment,
        full_source_clause_applies=False if appointment is False else None,
        selected_role="changed_use",
        selected_trigram=changed,
        trigram_fact_path=path + ".name",
        moving_line=line,
        direction_role_uniquely_adjudicated=False,
        selected_table_symbol=direction["quote"],
        comparison_source=deepcopy(profile["comparison_sources"]["volume1"]),
        single_geographic_direction=None,
        geographic_reference_origin=None,
        actual_appointment_location=None,
        numeric_bearing=None,
    )
    summary = f"求名补充沿用本候选原体{body}，按四个实际内卦辅助角色另核。"
    if support_times:
        summary += (
            "生体角色的原文时序分别为："
            + "；".join(
                f"{LABELS[r['role']]}{r['trigram']}《{r['time_reference']['quote']}》"
                for r in support_times
            )
            + "。"
        )
    else:
        summary += "所列内卦角色未见生体，不据此单独断名不成。"
    summary += (
        "本次已有内卦克体，無尅體之卦的必要条件不满足。"
        if attackers
        else "所列内卦未见克体；完整内外无克体范围未确认，未把名易就句当成确定成就。"
    )
    if office_applies is True:
        summary += (
            "所报为原文在任情境且内卦见克体，满足所选在任句的明示条件；克体角色时序为："
            + "；".join(
                f"{LABELS[r['role']]}{r['trigram']}《{r['time_reference']['quote']}》"
                for r in attacker_times
            )
            + "。原句为史料条件记录，不是现实处分、失职或灾祸判断。"
        )
    elif office is None:
        summary += "在任声明未采集或未知，不从已就业、题篇或问句补成在任。"
    elif office is False:
        summary += "所报不属于原文在任情境，此在任句不适用。"
    else:
        summary += "虽已报在任，所列内卦未见克体，该句的存在条件不满足。"
    if appointment is True:
        summary += f"所报求职任，按明示变用经卦读法取{changed}，所选方道栏作“{direction['quote']}”。"
        if direction["source_direction_conflict"]:
            summary += "同本地理另记東南、固定转录方道亦作東南，差异未裁定。"
        summary += "这只是所选文字类象，未核实际任所或地理原点。"
    elif appointment is False:
        summary += "所报非求原文职任，未将求名泛化为任所判断。"
    else:
        summary += "未确认所问为原文职任，方道仅列条件候选。"
    summary += "各数字、年月日時用法与全章综合未唯一裁定；初始条款、受制、旺衰均保留，未算应验日期、概率或现实结果。"
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": reputation_ruleset(),
        "source": deepcopy(profile["source"]),
        "comparison_sources": deepcopy(profile["comparison_sources"]),
        "original_body": body,
        "body_fact_path": fact_prefix + ".body_trigram.name",
        "context_declaration": (
            {
                "status": "caller_declared_unverified",
                "value": deepcopy(context),
                "fact_path": context_fact_path,
                "label_is_not_parsed": True,
            }
            if context is not None
            else {"status": "not_collected", "value": None, "fact_path": None}
        ),
        "actual_roles": roles,
        "support_time_source_rule": _source_rule("completion_time"),
        "support_time_references": support_times,
        "no_attacker_qualification": no_attacker,
        "office_qualification": {
            "source_rule": _source_rule("in_office"),
            "declared_currently_in_office": office,
            "has_internal_attacker": bool(attackers),
            "selected_clause_applies": office_applies,
            "condition_scope": "declared_source_context_and_actual_existential_inner_attacker_only",
            "real_personnel_or_hazard_verdict": None,
        },
        "attacker_time_source_rule": _source_rule("office_time"),
        "attacker_time_references": attacker_times,
        "appointment_direction": direction,
        "multiple_roles_are_independent_observations": False,
        "net_effect": None,
        "event_time": None,
        "candidate_event_dates": None,
        "success_probability": None,
        "real_outcome": None,
        "summary": summary,
    }


def apply_reputation_supplement(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    context_fact_path: str,
) -> None:
    """Enrich only the explicit chapter; questions never choose context or source."""
    if interpretation["interpretation_topic"] != "reputation":
        if context is not None:
            raise ValueError(
                "Reputation context requires interpretation_topic=reputation"
            )
        return
    selected = _reading(
        cast,
        cast["stage_relations"],
        interpretation["internal_countercontrol"],
        cast.get("seasonal_strength"),
        context,
        fact_prefix="meihua",
        interpretation_prefix="interpretation",
        context_fact_path=context_fact_path,
    )
    interpretation["topic_reading"]["chapter_qualifications"] = selected
    interpretation["traditional_judgement"] += selected["summary"]
    suffix = selected["summary"]
    for index, row in enumerate(interpretation.get("casting_readings") or []):
        layer = _reading(
            cast["counting_variants"][index],
            row["stage_relations"],
            row["internal_countercontrol"],
            row["seasonal_strength"],
            context,
            fact_prefix=f"meihua.counting_variants.{index}",
            interpretation_prefix=f"interpretation.casting_readings.{index}",
            context_fact_path=context_fact_path,
        )
        row["topic_clause"]["chapter_qualifications"] = layer
        row["traditional_judgement"] += layer["summary"]
        label = "原数口径" if row["line_sum_basis"] == "raw_counts" else "卦序数口径"
        suffix += label + "求名补充另核：" + layer["summary"]
    interpretation["evidence_scope"]["reputation_supplement"] = (
        "selected_NLC1925_supplement_and_literal_time_fangdao_references; "
        "caller_declarations_unverified, source_variants_and_role_scope_retained; "
        "not_full_chapter_synthesis_or_actual_event_time"
    )
    interpretation["comprehensive_judgement"] += suffix
