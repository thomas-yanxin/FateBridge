"""Declared quiet-context conditions, separate from unseen or uncollected omens."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTEXT_FIELDS = ("quiet_room", "nothing_heard", "nothing_seen")


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    profile: dict[str, Any] = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/meihua/quiet-context-nlc1925-v1.json"
        ).read_text(encoding="utf-8")
    )
    if (
        profile["id"] != "meihua_quiet_context_nlc1925_v1"
        or profile["version"] != "1.0.0"
    ):
        raise ValueError("Unknown selected quiet-context source profile")
    return profile


def quiet_context_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


def ensure_observation_method_context(
    method: str | None, context: dict[str, Any] | None
) -> None:
    """Reject only explicitly conflicting source declarations in the same cast."""
    if context is None:
        return
    if method == "sound_groups" and context.get("nothing_heard") is True:
        raise ValueError("sound_groups声明实际听闻，不能同时声明同次起卦无所闻")
    if method in {"observed_trigrams", "observed_categories"} and all(
        context.get(key) is True for key in CONTEXT_FIELDS
    ):
        raise ValueError(
            "观物起卦声明外部物象，不能同时套用同次静室无所闻见的无外卦条件"
        )


def _seed_calendar_values(seed: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose confirmed seed labels without deriving strength or an actual date."""
    nested = seed.get("casting_method") == "lunar_time_added_count"
    parameters = seed.get("parameters")
    lunar_parameters: dict[str, Any] | None = None
    if nested:
        if not isinstance(parameters, dict) or parameters.get("method") != (
            "lunar_time_added_count"
        ):
            raise ValueError("Quiet-context lunar labels require their original method")
        if seed.get("hour_branch") != parameters.get("hour_branch"):
            raise ValueError("Quiet-context hour must match the original lunar seed")
        lunar_parameters = parameters
    result = []
    for key in ("year_branch", "lunar_month", "lunar_day", "hour_branch"):
        if lunar_parameters is not None and key != "hour_branch":
            value = lunar_parameters[key]
            if seed.get(key) is not None and seed[key] != value:
                raise ValueError("Quiet-context lunar seed labels disagree")
            path = "meihua.seed.parameters." + key
        else:
            value = seed.get(key)
            path = "meihua.seed." + key
        result.append(
            {
                "field": key,
                "value": value,
                "fact_path": path if value is not None else None,
            }
        )
    return result


def _reading(
    cast: dict[str, Any],
    context: dict[str, Any] | None,
    seed: dict[str, Any],
    *,
    fact_prefix: str,
    context_fact_path: str,
    seasonal_strength_path: str | None,
) -> dict[str, Any]:
    values = [context.get(key) if context else None for key in CONTEXT_FIELDS]
    matches = (
        False
        if any(value is False for value in values)
        else True if all(value is True for value in values) else None
    )
    status = (
        "not_collected"
        if context is None
        else (
            "declared_conditions_met"
            if matches is True
            else (
                "declared_conditions_not_met"
                if matches is False
                else "pending_declared_conditions"
            )
        )
    )
    if matches is True:
        summary = (
            "按同次所报静室且无所闻见的条件，所选《静占》不取外卦；"
            "实际内卦与原体用仍另列，原句要求的年月日衰旺合参尚未完整核定。"
        )
    elif matches is False:
        summary = "所报条件不满足所选《静占》语境；不能反推必须有外应或据此定吉凶。"
    else:
        summary = (
            "静室与闻见条件未采集或尚不齐；不把缺项当作确认没有外应，"
            "也不据此取消本次起卦。"
        )
    return {
        "ruleset_id": _profile()["id"],
        "version": _profile()["version"],
        "ruleset": quiet_context_ruleset(),
        "declaration_status": (
            "not_collected" if context is None else "caller_reported_unverified"
        ),
        "reported_context": deepcopy(context),
        "context_fact_path": context_fact_path if context is not None else None,
        "conditions": [
            {
                "field": key,
                "value": value,
                "is_known": value is not None,
                "fact_path": (
                    context_fact_path + "." + key if value is not None else None
                ),
            }
            for key, value in zip(CONTEXT_FIELDS, values, strict=True)
        ],
        "status": status,
        "matches_declared_source_conditions": matches,
        "external_policy_under_selected_declared_context": (
            "do_not_use_external_hexagrams_for_this_quiet_clause"
            if matches is True
            else None
        ),
        "absence_of_all_actual_omens_independently_verified": False,
        "internal_basis": {
            "original_body": {
                "trigram": cast["body_trigram"]["name"],
                "fact_path": fact_prefix + ".body_trigram",
            },
            "original_use": {
                "trigram": cast["use_trigram"]["name"],
                "fact_path": fact_prefix + ".use_trigram",
            },
            "hexagrams": [
                {
                    "role": key,
                    "binary_code": cast[key]["binary_code"],
                    "fact_path": fact_prefix + "." + key,
                }
                for key in ["base_hexagram", "mutual_hexagram", "changed_hexagram"]
            ],
            "known_seed_calendar_values": _seed_calendar_values(seed),
            "available_month_strength_fact_path": seasonal_strength_path,
            "seed_counts_are_year_or_day_strength_calculations": False,
            "complete_year_month_day_strength_synthesis": None,
            "full_selected_quiet_judgement_established": False,
        },
        "mental_stillness_or_casting_trigger_adjudicated": False,
        "casting_eligibility": None,
        "event_time": None,
        "real_outcome": None,
        "changes_registered_forecast_eligibility_or_denominators": False,
        "summary": summary,
    }


def apply_observation_context(
    cast: dict[str, Any],
    interpretation: dict[str, Any],
    context: dict[str, Any] | None,
    *,
    context_fact_path: str,
) -> None:
    """Keep current calculation and each candidate's own held geometry intact."""
    interpretation["observation_context"] = None
    if interpretation["interpretation_topic"] == "weather":
        return
    layer = _reading(
        cast,
        context,
        cast["seed"],
        fact_prefix="meihua",
        context_fact_path=context_fact_path,
        seasonal_strength_path=(
            "meihua.seasonal_strength" if cast.get("seasonal_strength") else None
        ),
    )
    interpretation["observation_context"] = layer
    suffix = layer["summary"] if context is not None else ""
    for index, candidate in enumerate(interpretation.get("casting_readings") or []):
        row = _reading(
            cast["counting_variants"][index],
            context,
            cast["seed"],
            fact_prefix=f"meihua.counting_variants.{index}",
            context_fact_path=context_fact_path,
            seasonal_strength_path=(
                f"interpretation.casting_readings.{index}.seasonal_strength"
                if candidate.get("seasonal_strength")
                else None
            ),
        )
        candidate["observation_context"] = row
        if context is not None:
            suffix += (
                (
                    "原数口径"
                    if candidate["line_sum_basis"] == "raw_counts"
                    else "卦序数口径"
                )
                + "静占条件另核："
                + row["summary"]
            )
    if suffix:
        interpretation["comprehensive_judgement"] += suffix
