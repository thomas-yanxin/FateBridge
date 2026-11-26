"""Explicit-source Mei Hua application service; never substitute the clock."""

from pydantic import JsonValue

from fatebridge.core.divination import build_meihua_interpretation
from fatebridge.core.meihua.casting import cast_explicit_meihua
from fatebridge.core.meihua.relations import (
    build_meihua_evidence,
    ensure_observation_method_context,
)
from fatebridge.core.meihua.texts import explicit_ruleset
from fatebridge.core.meihua.topics import (
    apply_day_qi,
    apply_external_omens,
    apply_motion_context,
    apply_observation_context,
    apply_reputation_supplement,
    apply_situational_responses,
    build_general_casting_readings,
    general_casting_summary,
    normalize_day_qi_context,
    reported_day_qi_context,
)
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.core.zhouyi import classical_hexagram
from fatebridge.utils.errors import calculation_guard


@calculation_guard("梅花显式起卦")
def calculate_meihua_cast(
    *,
    casting: dict[str, JsonValue],
    season_month_branch: str | None = None,
    question: str | None = None,
    interpretation_topic: str = "general",
    weather_context: dict[str, JsonValue] | None = None,
    external_observations: list[dict[str, JsonValue]] | None = None,
    matter_scenario: str | None = None,
    observer_activity: str | None = None,
    observation_context: dict[str, JsonValue] | None = None,
    day_qi_context: dict[str, JsonValue] | None = None,
    response_context: dict[str, JsonValue] | None = None,
    reputation_context: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    """Cast and interpret an explicit-input Meihua hexagram."""
    normalized_day_qi = normalize_day_qi_context(day_qi_context, interpretation_topic)
    options = MeihuaInterpretationOptions.model_validate(
        {
            "interpretation_topic": interpretation_topic,
            "weather_context": weather_context,
            "reputation_context": reputation_context,
            "response_context": response_context,
            "observation_context": observation_context,
            "observer_activity": observer_activity,
            "matter_scenario": matter_scenario,
            "external_observations": external_observations,
        }
    )

    normalized_observation = (
        options.observation_context.model_dump(mode="json")
        if options.observation_context is not None
        else None
    )
    ensure_observation_method_context(casting.get("method"), normalized_observation)
    cast, trace = cast_explicit_meihua(casting)
    for key in ("base_hexagram", "changed_hexagram"):
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
            },
        )
    )
    cast["evidence_scope"]["implemented"][0] = cast["seed"]["casting_method"]
    if season_month_branch is None:
        cast["evidence_scope"]["implemented"].remove("season")
        cast["evidence_scope"]["missing_context"] = ["season_month_branch"]

    interpretation = build_meihua_interpretation(
        cast,
        interpretation_topic=interpretation_topic,
        weather_context=weather_context,
    )
    if interpretation_topic == "weather":
        interpretation["casting_readings"] = None
        interpretation["casting_comparison"] = None
        cast["evidence_scope"]["implemented"].append("selected_weather_clauses")
    elif interpretation_topic == "general":
        interpretation.update(build_general_casting_readings(cast, season_month_branch))
        if interpretation["casting_readings"]:
            interpretation["comprehensive_judgement"] = general_casting_summary(
                interpretation["casting_readings"]
            )
    else:
        cast["evidence_scope"]["implemented"].append("selected_topic_clauses")

    if cast["seed"].get("count_boundary_status") == "convention_changes_result":
        interpretation["status"] = "conditional_on_declared_convention"
    if cast["seed"].get("text_tone_basis") is not None:
        interpretation["status"] = "conditional_on_reported_tone_categories"
    if cast["seed"].get("observation_basis") is not None:
        interpretation["status"] = "conditional_on_reported_observation"

    apply_external_omens(
        cast,
        interpretation,
        (
            [
                item.model_dump(mode="json", exclude_none=True)
                for item in options.external_observations
            ]
            if options.external_observations is not None
            else None
        ),
    )
    apply_motion_context(
        cast,
        interpretation,
        observer_activity=options.observer_activity,
        observer_fact_path="input_normalized.observer_activity",
    )
    apply_observation_context(
        cast,
        interpretation,
        normalized_observation,
        context_fact_path="input_normalized.observation_context",
    )
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
    normalized_response = (
        options.response_context.model_dump(mode="json")
        if options.response_context is not None
        else None
    )
    apply_situational_responses(
        cast,
        interpretation,
        normalized_response,
        context_fact_path="input_normalized.response_context",
    )
    normalized_reputation = (
        options.reputation_context.model_dump(mode="json", exclude_none=True)
        if options.reputation_context is not None
        else None
    )
    apply_reputation_supplement(
        cast,
        interpretation,
        context=normalized_reputation,
        context_fact_path="input_normalized.reputation_context",
    )
    if options.matter_scenario is not None and interpretation_topic != "weather":
        interpretation["stage_emphasis"] = {
            "matter_scenario": options.matter_scenario,
            "scenario_fact_path": "input_normalized.matter_scenario",
        }

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
