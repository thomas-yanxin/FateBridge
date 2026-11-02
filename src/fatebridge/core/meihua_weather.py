"""Source-scoped weather symbols, without body/use or invented rule voting."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .meihua_weather_attributions import build_weather_attributions
from .meihua_weather_cast_variants import augment_weather_cast_variants
from .meihua_weather_controls import (
    assess_weather_controls,
    qualify_weather_rules,
    weather_control_profile,
    weather_frequency_views,
)
from .meihua_weather_frequency import (
    assess_weather_frequency,
    qualify_weather_frequency,
)
from .meihua_weather_time_scope import compare_weather_time_scopes
from .requests.meihua import MeihuaWeatherContext


@lru_cache(maxsize=1)
def _profile() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data/meihua/weather-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def weather_ruleset() -> dict[str, Any]:
    return deepcopy(_profile())


@lru_cache(maxsize=1)
def _research_validation() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1]
        / "data/meihua/weather-research-validation-v1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def build_weather_interpretation(
    meihua: dict[str, Any], context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Interpret the chosen cast and every actual retained counting alternative."""
    result = _build_weather_one(meihua, context)
    augment_weather_cast_variants(result, meihua, context, _build_weather_one)
    return result


def _build_weather_one(
    meihua: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    fact_prefix: str = "meihua",
) -> dict[str, Any]:
    """Evaluate every selected clause; missing conditions never become false facts."""
    confirmed = MeihuaWeatherContext.model_validate(context or {}).model_dump()
    profile = weather_ruleset()
    hexagrams = [
        (key, meihua[key])
        for key in ["base_hexagram", "mutual_hexagram", "changed_hexagram"]
    ]
    slots = [
        {"path": f"{fact_prefix}.{key}.{position}", "trigram": value[position]["name"]}
        for key, value in hexagrams
        for position in ["upper", "lower"]
    ]
    counts = Counter(row["trigram"] for row in slots)
    frequency_views = weather_frequency_views(
        slots, meihua["seed"]["moving_line"], fact_prefix=fact_prefix
    )
    traces = []
    for rule in profile["rules"]:
        conditions = rule["conditions"]
        checks: list[dict[str, Any]] = []
        for name in conditions.get("present", []):
            checks.append(
                {"condition": "present", "trigram": name, "met": counts[name] > 0}
            )
        for name in conditions.get("absent", []):
            checks.append(
                {"condition": "absent", "trigram": name, "met": counts[name] == 0}
            )
        if "present_any" in conditions:
            names = conditions["present_any"]
            matched_paths = [slot["path"] for slot in slots if slot["trigram"] in names]
            checks.append(
                {
                    "condition": "any_present",
                    "trigrams": names,
                    "matched_paths": matched_paths,
                    "met": bool(matched_paths),
                }
            )
        if "many" in conditions:
            name = conditions["many"]
            threshold = confirmed["many_min_count"]
            checks.append(
                {
                    "condition": "many",
                    "trigram": name,
                    "count": counts[name],
                    "declared_threshold": threshold,
                    "frequency_assessment": assess_weather_frequency(
                        name, frequency_views, threshold
                    ),
                    "met": (
                        counts[name] >= threshold
                        if threshold is not None
                        else False if counts[name] < 2 else None
                    ),
                }
            )
        for name in ["season", "prior_condition"]:
            if name in conditions:
                actual = confirmed[name]
                required = conditions[name]
                checks.append(
                    {
                        "condition": name,
                        "required": required,
                        "actual": actual,
                        "met": (
                            (
                                actual in required
                                if name == "season" and isinstance(required, list)
                                else actual == required
                            )
                            if actual is not None
                            else None
                        ),
                    }
                )
        if "pairs" in conditions:
            matched_paths = [
                f"{fact_prefix}.{key}"
                for key, value in hexagrams
                if [value["upper"]["name"], value["lower"]["name"]]
                in conditions["pairs"]
            ]
            checks.append(
                {
                    "condition": "same_hexagram_pair",
                    "required_upper_lower": conditions["pairs"],
                    "matched_paths": matched_paths,
                    "met": bool(matched_paths),
                }
            )
        states = [row["met"] for row in checks]
        status = (
            "not_met"
            if False in states
            else "pending_context" if None in states else "matched"
        )
        traces.append(
            {
                "rule_id": rule["id"],
                "kind": rule["kind"],
                "status": status,
                "time_scope": rule.get("time_scope", "unspecified"),
                "conditions": checks,
                "tags": rule["tags"],
                "traditional_reading": rule["reading"],
            }
        )
    controls = assess_weather_controls(frequency_views, confirmed["many_min_count"])
    qualify_weather_rules(traces, profile["rules"], controls)
    qualify_weather_frequency(traces)
    matched = [row for row in traces if row["status"] == "matched"]
    source_rules = {rule["id"]: rule for rule in profile["rules"]}
    selected_readings = []
    for row in matched:
        rule = source_rules[row["rule_id"]]
        fact_paths: set[str] = set()
        for condition in row["conditions"]:
            if "trigram" in condition:
                fact_paths.update(
                    slot["path"]
                    for slot in slots
                    if slot["trigram"] == condition["trigram"]
                )
            fact_paths.update(condition.get("matched_paths", []))
            if condition["condition"] == "many":
                fact_paths.add("interpretation.weather.context.many_min_count")
            if condition["condition"] in {"season", "prior_condition"}:
                fact_paths.add(
                    "interpretation.weather.context." + condition["condition"]
                )
        selected_readings.append(
            {
                "rule_id": row["rule_id"],
                "time_scope": row["time_scope"],
                "effective_status": row["effective_status"],
                "reading": row["effective_reading"],
                "controlled_tags": row["controlled_tags"],
                "conditional_tags": row["conditional_tags"],
                "control_checks": row["control_checks"],
                "frequency_assessment": row["frequency_assessment"],
                "qualification_reasons": row["qualification_reasons"],
                "fact_paths": sorted(fact_paths),
                "source_id": rule["source_id"],
                "section": rule["section"],
                "quote": rule["quote"],
                "source_witnesses": deepcopy(rule.get("source_witnesses", [])),
                "textual_status": rule.get(
                    "textual_status", "fixed_transcription_only"
                ),
            }
        )
    time_scopes = compare_weather_time_scopes(traces)
    conflicts = time_scopes["unspecified_time_conflicts"]
    pending = [row["rule_id"] for row in traces if row["status"] == "pending_context"]
    readings = "".join(row["effective_reading"] + "。" for row in matched)
    summary = (
        "按卷二天时占，不以体用生克判断天气；本、互、变的上下卦逐项取象。"
        + (readings or "本次未命中已实现的条件条款。")
        + ("原始通象中的不同条款全部保留；制约条件随条列明。" if conflicts else "")
        + ("部分条款仍待已确认季节、前期天气或明示的多字阈值。" if pending else "")
        + (
            "朝暮分别保留，不把朝晴暮雨当成同一时段的矛盾；未定时段的通象也不自动解释为全天。"
            if time_scopes["has_explicit_daypart_readings"]
            else ""
        )
        + "这些是所选原文的条件性象义，未定位日期、地点或钟时区间，也未形成经验证的气象预测。"
    )
    attributions = build_weather_attributions(slots, confirmed["season"])
    summary += "\n" + attributions["summary"]
    return {
        "interpretation_topic": "weather",
        "question_domain": {
            "key": "weather",
            "label": "天时",
            "focus": "全卦天气象义及其实际条件",
        },
        "weather": {
            "ruleset_id": profile["id"],
            "version": profile["version"],
            "ruleset": profile,
            "context": confirmed,
            "trigram_slots": slots,
            "trigram_counts": {name: counts[name] for name in "乾兑离震巽坎艮坤"},
            "frequency_views": frequency_views,
            "control_profile": weather_control_profile(),
            "controls": controls,
            "rule_trace": traces,
            "selected_readings": selected_readings,
            "matched_rule_ids": [row["rule_id"] for row in matched],
            "pending_rule_ids": pending,
            "conflicts": conflicts,
            "time_scope_comparison": time_scopes,
            "single_forecast": None,
            "symbolic_attributions": attributions,
            "research_validation": deepcopy(_research_validation()),
        },
        "evidence_scope": {
            "classical_coverage": "selected_weather_clauses_only",
            "body_use_applied": False,
            "cuo_zong_applied": False,
            "stage_sequence_is_forecast_timing": False,
            "weather_observations": "caller_context_only_no_measurements_fetched",
            "not_implemented": profile["unresolved"],
            "weather_controls": "direct_source_controls_with_explicit_scope_candidates",
            "weather_many_scope": "six_position_raw_result_qualified_by_five_role_sensitivity",
            "weather_textual_evidence": "固定转录与影印所选字句分别列出，包含多雨与必雨等差异；目读由助手完成，未作独立专家或全章字义认证。",
            "weather_seasonal_text_basis": "新增秋金晴、冬坎雪、春土雨三句按卷二固定转录1441921计算；所选文明书局冬句无坎之水、春句坤兌与转录坤艮不同，字形和主语不静默补齐。",
            "weather_daypart_scope": "仅按离在艮上暮雨朝晴保留朝暮原文时段；不换算具体钟时、日出日落或日期，不把未定时段当全天，不以此裁定离互艮宫。",
            "weather_attributions_scope": "另列文明书局本霜雪霰雹、日电虹霓及既有雷类象的明示季令核对；不是实况、制化综合或旧研究标签映射，旧研究不认证此补充的预测效力。",
            "real_world_efficacy": "not_established",
            "research_validation_scope": "specified_historical_policy_cohorts_only_no_prospective_or_global_prediction_acceptance",
        },
        "comprehensive_judgement": summary,
    }
