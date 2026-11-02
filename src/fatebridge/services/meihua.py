"""Explicit-source Mei Hua application service; never substitute the clock."""

from typing import Any, Optional

from fatebridge.core.divination import build_meihua_interpretation
from fatebridge.core.meihua import build_meihua_evidence
from fatebridge.core.meihua_casting import cast_explicit_meihua, explicit_ruleset
from fatebridge.core.meihua_external import apply_external_omens
from fatebridge.core.meihua_general_variants import (
    build_general_casting_readings,
    general_casting_summary,
)
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.core.zhouyi import classical_hexagram
from fatebridge.utils.errors import calculation_guard


@calculation_guard("梅花显式起卦")
def calculate_meihua_cast(
    *,
    casting: dict[str, Any],
    season_month_branch: Optional[str] = None,
    question: Optional[str] = None,
    interpretation_topic: str = "general",
    weather_context: Optional[dict[str, Any]] = None,
    external_observations: Optional[list[dict[str, Any]]] = None,
    matter_scenario: Optional[str] = None,
    observer_activity: Optional[str] = None,
    observation_context: Optional[dict[str, Any]] = None,
    day_qi_context: Optional[dict[str, Any]] = None,
    response_context: Optional[dict[str, Any]] = None,
    reputation_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    from fatebridge.core.meihua_day_qi import normalize_day_qi_context

    normalized_day_qi = normalize_day_qi_context(day_qi_context, interpretation_topic)
    options = MeihuaInterpretationOptions.model_validate(
        {
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
            **(
                {"reputation_context": reputation_context}
                if reputation_context is not None
                else {}
            ),
            **(
                {"response_context": response_context}
                if response_context is not None
                else {}
            ),
            **(
                {"observation_context": observation_context}
                if observation_context is not None
                else {}
            ),
            **(
                {"observer_activity": observer_activity}
                if observer_activity is not None
                else {}
            ),
            **(
                {"matter_scenario": matter_scenario}
                if matter_scenario is not None
                else {}
            ),
            **(
                {"external_observations": external_observations}
                if external_observations is not None
                else {}
            ),
        }
    )
    from fatebridge.core.meihua_observation import ensure_observation_method_context

    normalized_observation = (
        options.observation_context.model_dump(mode="json")
        if observation_context is not None and options.observation_context is not None
        else None
    )
    ensure_observation_method_context(casting.get("method"), normalized_observation)
    cast, trace = cast_explicit_meihua(casting)
    for key in [
        "base_hexagram",
        "changed_hexagram",
        "mutual_hexagram",
        "cuo_hexagram",
        "zong_hexagram",
    ]:
        cast[key]["meaning_source_kind"] = "modern_editorial_summary"
        cast[key]["classical"] = classical_hexagram(cast[key]["binary_code"])
    cast.update(
        build_meihua_evidence(
            cast,
            lunar_year=None,
            is_leap_month=False,
            timezone_name=None,
            month_branch=season_month_branch,
            casting_trace=trace,
            selected_ruleset=(
                explicit_ruleset(casting_method="observed_categories")
                if cast["seed"]["casting_method"] == "observed_categories"
                else explicit_ruleset()
            ),
            calendar_policy={
                "context_status": (
                    "caller_supplied_month_branch"
                    if season_month_branch is not None
                    else "not_supplied"
                ),
                "date_basis": "no_civil_datetime_supplied",
                "hour_basis": (
                    "caller_supplied_branch"
                    if "hour_branch" in cast["seed"]
                    else "not_used_for_cast"
                ),
                "true_solar_time_applied": False,
                "rule_kind": "explicit_inputs_no_clock_fallback",
            },
        )
    )
    if cast["seed"]["casting_method"] == "lunar_time_added_count":
        cast["calendar_policy"].update(
            lunar_input_basis="caller_confirmed_nominal_month_day_and_year_branch",
            absolute_lunar_year=None,
            is_leap_month=None,
            actual_month_length_validated=False,
            added_count_basis="caller_confirmed_count_not_automatic_glyph_strokes",
        )
    cast["evidence_scope"]["implemented"][0] = cast["seed"]["casting_method"]
    cast["evidence_scope"]["not_implemented"] = [
        "single_sound_count",
        "automatic_observation_classification",
        "automatic_historical_tones",
        "automatic_glyph_strokes",
        "external_omens_interpretation",
        "exact_event_timing",
        "all_topic_judgements",
    ]
    if season_month_branch is None:
        cast["evidence_scope"]["implemented"].remove("season")
        cast["evidence_scope"]["missing_context"] = ["season_month_branch"]
    interpretation = build_meihua_interpretation(
        cast,
        question or "",
        interpretation_topic=interpretation_topic,
        weather_context=weather_context,
    )
    if interpretation_topic == "weather":
        # Shared audit fields remain projectable while weather keeps its own
        # no-body/use candidate interpretation in interpretation.weather.
        interpretation["casting_readings"] = None
        interpretation["casting_comparison"] = None
        cast["evidence_scope"][
            "interpretation_basis"
        ] = "weather_rules_without_body_use"
        cast["evidence_scope"]["implemented"].append("selected_weather_clauses")
    elif interpretation_topic == "general":
        interpretation.update(build_general_casting_readings(cast, season_month_branch))
        if interpretation["casting_readings"]:
            interpretation["comprehensive_judgement"] = general_casting_summary(
                interpretation["casting_readings"]
            )
        interpretation["evidence_scope"]["counting_candidate_readings"] = (
            "各候选沿用自身本互变、固定原体和同一已报节月，分别引用实际动爻经文；"
            "不以所选口径的旺衰、生克或爻辞代替另一候选。"
        )
    else:
        cast["evidence_scope"][
            "interpretation_basis"
        ] = "selected_nlc1925_topic_initial_body_use_clause"
        cast["evidence_scope"]["implemented"].append("selected_topic_clauses")
        if interpretation_topic == "wealth":
            cast["evidence_scope"]["implemented"].append("selected_wealth_components")
        if interpretation_topic == "lost_property":
            cast["evidence_scope"]["implemented"].append(
                "selected_lost_property_changed_use_location_symbols"
            )
    interpretation["evidence_scope"]["no_universal_relation_verdict"] = True
    if cast["seed"].get("count_boundary_status") == "convention_changes_result":
        cast["evidence_scope"][
            "calculation_status"
        ] = "conditional_on_declared_convention"
        interpretation["status"] = "conditional_on_declared_convention"
        interpretation["evidence_scope"]["counting_convention"] = (
            "原物数与上卦卦序数取爻有分歧，时数均保留原时支数且只加一次；"
            if cast["seed"]["casting_method"] == "object_count"
            else (
                "原字数与两卦卦序数取爻有分歧，不加时数；"
                if cast["seed"]["casting_method"] == "text_count"
                else "原声数与卦序数取爻有分歧；"
            )
        ) + "本次按seed.line_sum_basis，另法动爻保留在seed.alternate_moving_line，不认定为原文唯一规则。"
        interpretation["comprehensive_judgement"] = (
            interpretation["evidence_scope"]["counting_convention"]
            + interpretation["comprehensive_judgement"]
        )
    tone_basis = cast["seed"].get("text_tone_basis")
    if tone_basis is not None:
        cast["evidence_scope"]["text_tone_basis"] = tone_basis
        interpretation["evidence_scope"]["text_tone_basis"] = tone_basis
        cast["evidence_scope"][
            "calculation_status"
        ] = "conditional_on_reported_tone_categories"
        interpretation["status"] = "conditional_on_reported_tone_categories"
        comparison = tone_basis["selected_example_comparison"]["status"]
        comparison_note = (
            "所报类别与所选今日动静如何原例一致，仅说明类别一致，未鉴定唯一古音。"
            if comparison == "matches_selected_example_categories"
            else (
                "所报类别与所选今日动静如何原例不同，本次不是该原例取音的复现。"
                if comparison == "differs_from_selected_example_categories"
                else "未将本次类别认证为某部韵书或所选原例的取音。"
            )
        )
        interpretation["comprehensive_judgement"] = (
            "字占按所报平上去入类别计算；音系和来源未由本工具独立核验。"
            + comparison_note
            + interpretation["comprehensive_judgement"]
        )
    text_basis = cast["seed"].get("text_count_basis")
    if text_basis is not None:
        cast["evidence_scope"]["text_count_basis"] = text_basis
        interpretation["evidence_scope"]["text_count_basis"] = text_basis
        if (
            text_basis["range_status"]
            == "software_extension_exact_textual_extent_unadjudicated"
        ):
            if cast["seed"].get("count_boundary_status") != "convention_changes_result":
                cast["evidence_scope"][
                    "calculation_status"
                ] = "conditional_on_textual_extent"
                interpretation["status"] = "conditional_on_textual_extent"
            interpretation["comprehensive_judgement"] = (
                "所选影印作百余字，精确上限未裁定；本次数量超过100，按明示软件扩展计算，"
                "不能据此宣称该数量范围已获原文唯一裁定。"
                + interpretation["comprehensive_judgement"]
            )
    apply_external_omens(
        cast,
        interpretation,
        (
            [
                item.model_dump(mode="json", exclude_none=True)
                for item in options.external_observations
            ]
            if external_observations is not None
            and options.external_observations is not None
            else None
        ),
    )
    from fatebridge.core.meihua_stage_emphasis import apply_stage_emphasis

    apply_stage_emphasis(
        cast,
        interpretation,
        matter_scenario=(
            options.matter_scenario if matter_scenario is not None else None
        ),
        scenario_fact_path="input_normalized.matter_scenario",
    )
    from fatebridge.core.meihua_motion import apply_motion_context

    apply_motion_context(
        cast,
        interpretation,
        observer_activity=(
            options.observer_activity if observer_activity is not None else None
        ),
        observer_fact_path="input_normalized.observer_activity",
    )
    from fatebridge.core.meihua_timing import apply_postheaven_count_reference

    apply_postheaven_count_reference(cast, interpretation)
    from fatebridge.core.meihua_observation import apply_observation_context

    apply_observation_context(
        cast,
        interpretation,
        normalized_observation,
        context_fact_path="input_normalized.observation_context",
    )
    from fatebridge.core.meihua_day_qi import apply_day_qi, reported_day_qi_context

    apply_day_qi(
        cast,
        interpretation,
        (
            reported_day_qi_context(normalized_day_qi)
            if normalized_day_qi is not None
            else None
        ),
        declared_fact_path="input_normalized.day_qi_context.day_branch",
    )
    from fatebridge.core.meihua_situational import apply_situational_responses

    normalized_response = (
        options.response_context.model_dump(mode="json")
        if response_context is not None and options.response_context is not None
        else None
    )
    apply_situational_responses(
        cast,
        interpretation,
        normalized_response,
        context_fact_path="input_normalized.response_context",
    )
    observation_basis = cast["seed"].get("observation_basis")
    if observation_basis is not None:
        cast["evidence_scope"][
            "calculation_status"
        ] = "conditional_on_reported_observation"
        cast["evidence_scope"]["not_implemented"].append(
            "full_observation_trigger_adjudication"
        )
        interpretation["status"] = "conditional_on_reported_observation"
        interpretation["evidence_scope"][
            "observation_basis"
        ] = "selected_declared_subject_and_direction_not_independent_scene_verification"
        interpretation["comprehensive_judgement"] = (
            observation_basis["summary"] + interpretation["comprehensive_judgement"]
        )
    from fatebridge.core.meihua_trigram_symbols import apply_trigram_relation_symbols

    apply_trigram_relation_symbols(cast, interpretation)
    from fatebridge.core.meihua_reputation import apply_reputation_supplement

    normalized_reputation = (
        options.reputation_context.model_dump(mode="json", exclude_none=True)
        if reputation_context is not None and options.reputation_context is not None
        else None
    )
    apply_reputation_supplement(
        cast,
        interpretation,
        context=normalized_reputation,
        context_fact_path="input_normalized.reputation_context",
    )
    from fatebridge.core.meihua_qi_days import apply_qi_day_timing_references

    apply_qi_day_timing_references(cast, interpretation)
    from fatebridge.core.meihua_qi_branches import apply_qi_branch_timing_references

    apply_qi_branch_timing_references(cast, interpretation)
    return {
        "analysis_type": "梅花显式起卦",
        "input_normalized": {
            **(
                {"reputation_context": normalized_reputation}
                if reputation_context is not None
                else {}
            ),
            **(
                {"response_context": normalized_response}
                if response_context is not None
                else {}
            ),
            **(
                {"day_qi_context": normalized_day_qi}
                if day_qi_context is not None
                else {}
            ),
            **(
                {"observation_context": normalized_observation}
                if observation_context is not None
                else {}
            ),
            **(
                {"observer_activity": observer_activity}
                if observer_activity is not None
                else {}
            ),
            **(
                {"matter_scenario": matter_scenario}
                if matter_scenario is not None
                else {}
            ),
            "casting": cast["seed"]["parameters"],
            "season_month_branch": season_month_branch,
            "question": question or "",
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
        },
        "meihua": cast,
        "interpretation": interpretation,
        "summary": interpretation["comprehensive_judgement"],
    }
