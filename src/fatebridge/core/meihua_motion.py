"""Selected NLC1925 motion clauses; never infer omen valence from movement."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.meihua_roles import ROLES


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/meihua/motion-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if profile["id"] != "meihua_motion_nlc1925_v1" or profile["version"] != "1.0.0":
        raise ValueError("Unknown selected Meihua motion profile")
    return profile


def motion_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def _reading(
    stages: list[dict[str, Any]],
    external: dict[str, Any] | None,
    *,
    fact_prefix: str,
    interpretation_prefix: str,
    observer_activity: str | None,
    observer_fact_path: str,
) -> dict[str, Any]:
    if [r["role"] for r in stages] != list(ROLES):
        raise ValueError("Motion requires all four actual auxiliary roles")
    rules = {r["id"]: r for r in _profile()["rules"]}
    inner = [
        {
            "role": "body",
            "trigram": stages[0]["body"],
            "motion": "static",
            "fact_path": fact_prefix + ".body_trigram",
            "rule_id": "inner_roles",
        }
    ]
    inner.extend(
        {
            "role": r["role"],
            "trigram": r["trigram"],
            "motion": "active" if r["role"] in {"use", "changed_use"} else "static",
            "fact_path": r["fact_path"],
            "rule_id": "inner_roles",
        }
        for r in stages
    )
    observer_rule = (
        rules.get("observer_" + observer_activity) if observer_activity else None
    )
    observer = {
        "activity": observer_activity,
        "declaration": (
            {
                "value": observer_activity,
                "status": "caller_reported_unverified",
                "fact_path": observer_fact_path,
            }
            if observer_activity
            else None
        ),
        "rule_id": observer_rule["id"] if observer_rule else None,
        "quote": observer_rule["quote"] if observer_rule else None,
        "original_pdf_indices": (
            deepcopy(observer_rule["pdf_indices"]) if observer_rule else []
        ),
        "relative_wording": (
            observer_rule["relative_wording"] if observer_rule else None
        ),
        "scope": "observer_activity_only_not_mental_stillness_or_omen_valence",
    }
    rows = []
    for index, observation in enumerate(
        external["reported_observations"] if external else []
    ):
        motion = observation.get("motion")
        motion_met = None if motion is None else motion == "moving"
        clauses = [
            {
                "rule_id": rule_id,
                "quote": rules[rule_id]["quote"],
                "original_pdf_indices": deepcopy(rules[rule_id]["pdf_indices"]),
                "required_omen_valence": valence,
                "motion_condition_met": motion_met,
                "omen_condition_met": None,
                "full_clause_applies": False if motion_met is False else None,
                "relative_wording": "速",
                "event_time": None,
            }
            for rule_id, valence in [
                ("moving_favorable", "favorable"),
                ("moving_unfavorable", "unfavorable"),
            ]
        ]
        rows.append(
            {
                "record_index": index,
                "motion": motion,
                "declaration_status": (
                    "not_collected" if motion is None else "caller_reported_unverified"
                ),
                "reported_fact_path": f"{interpretation_prefix}.external_omens.reported_observations.{index}",
                "qualification_fact_path": f"{interpretation_prefix}.external_omens.observations.{index}",
                "omen_valence": None,
                "omen_valence_status": "not_computed_not_a_caller_prediction_input",
                "moving_clauses": clauses,
                "stationary_source_wording": (
                    deepcopy(rules["stationary_not_yet"])
                    if motion == "stationary"
                    else None
                ),
                "event_time": None,
            }
        )
    summary = ""
    if observer_activity and observer_rule is not None:
        activity_label = {"seated": "坐", "walking": "行", "standing": "立"}[
            observer_activity
        ]
        summary += f"所报占者活动为{activity_label}，所选原句作“{observer_rule['quote']}”，仅保留相对迟速。"
    if any(r["motion"] is not None for r in rows):
        summary += "外应动静按逐条所报事实保留，不从水土或器物类别推定；动而吉／凶的速应句尚缺外应吉凶综合判断，问吉事或问不吉之事不能替代。"
        if any(r["motion"] == "stationary" for r in rows):
            summary += "所报不动对应原句“吉凶之未见”，不据此断无事发生或取消本次起卦。"
    if summary:
        summary = (
            "体互静、用变动是内卦符号角色，不等同现场运动。"
            + summary
            + "三项未综合为日期、持续时间或现实结局。"
        )
    return {
        "ruleset_id": _profile()["id"],
        "version": _profile()["version"],
        "ruleset": motion_ruleset(),
        "reference_body": "original_static_body_of_this_candidate",
        "inner_roles": inner,
        "inner_role_motion_scope": "source_symbolic_roles_not_physical_movement",
        "observer": observer,
        "external_motion": rows,
        "casting_trigger_adjudicated": False,
        "mental_stillness_adjudicated": False,
        "motion_axes_synthesis": "not_computed",
        "duration": None,
        "event_time": None,
        "combined_outcome": None,
        "independent_verified_observations": 0,
        "summary": summary,
    }


def apply_motion_context(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    *,
    observer_activity: str | None = None,
    observer_fact_path: str = "input_normalized.observer_activity",
) -> None:
    """Read held facts and declarations, without recasting or making a net verdict."""
    interpretation["motion_context"] = None
    if observer_activity not in {None, "seated", "walking", "standing"}:
        raise ValueError("Unknown reported observer activity")
    if interpretation["interpretation_topic"] == "weather":
        if observer_activity is not None:
            raise ValueError("Selected human motion clauses do not apply to weather")
        return
    layer = _reading(
        cast["stage_relations"],
        interpretation.get("external_omens"),
        fact_prefix="meihua",
        interpretation_prefix="interpretation",
        observer_activity=observer_activity,
        observer_fact_path=observer_fact_path,
    )
    interpretation["motion_context"] = layer
    suffix = layer["summary"]
    for index, candidate in enumerate(interpretation.get("casting_readings") or []):
        row = _reading(
            candidate["stage_relations"],
            candidate.get("external_omens"),
            fact_prefix=f"meihua.counting_variants.{index}",
            interpretation_prefix=f"interpretation.casting_readings.{index}",
            observer_activity=observer_activity,
            observer_fact_path=observer_fact_path,
        )
        candidate["motion_context"] = row
        if row["summary"]:
            label = (
                "原数口径"
                if candidate["line_sum_basis"] == "raw_counts"
                else "卦序数口径"
            )
            suffix += label + "动静另核：" + row["summary"]
    if suffix:
        interpretation["comprehensive_judgement"] += suffix
