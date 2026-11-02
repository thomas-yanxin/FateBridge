"""Version-pinned daily research hypotheses with source dayparts retained.

This is an explicitly assumed study bridge from symbolic readings to next-day
rainfall, not a classical date calculation or a production weather forecast.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.meihua_weather_time_scope import compare_weather_time_scopes
from fatebridge.validation.meihua_weather_policy_v2 import canonical_sha256

POLICY_ID = "qualified_scope_aware_daily_rain_clear_v3"
POLICY_VERSION = "1.0.0"
_SIGNS = {"rain", "clear"}
_UNMAPPED = {"variable", "rain_stopping", "snow"}
_QUALIFIED = {
    "matched",
    "qualified_by_source_control",
    "conditional_on_unresolved_control",
    "conditional_on_unresolved_frequency",
    "multiple_qualifications",
}


def scope_aware_weather_label(
    weather: dict[str, Any],
    *,
    expected_profile_sha256: str,
    expected_control_profile_sha256: str,
) -> dict[str, Any]:
    """Map only the predeclared hypotheses; never inspect rainfall outcomes.

    Partial-day clear is not a daily negative. Rain at one assigned daypart is
    a daily positive hypothesis; unspecified clear retains the explicitly
    declared older study proxy. Date assignment is a test assumption throughout.
    """
    profile = weather["ruleset"]
    if (
        weather["ruleset_id"] != "meihua_weather_v1"
        or weather["version"] != "1.7.0"
        or profile["id"] != weather["ruleset_id"]
        or profile["version"] != weather["version"]
        or canonical_sha256(profile) != expected_profile_sha256
        or canonical_sha256(weather["control_profile"])
        != expected_control_profile_sha256
    ):
        raise ValueError("The v3 policy requires its pinned1.7.0 and control profiles")
    if weather["single_forecast"] is not None:
        raise ValueError("Research policy cannot consume a fabricated engine forecast")
    if weather.get("casting_variants") or weather.get("casting_variant_traces"):
        raise ValueError("The time-cast study cannot choose among counting candidates")
    rules = {r["id"]: r for r in profile["rules"]}
    traces = weather["rule_trace"]
    if (
        len(rules) != 40
        or len(traces) != 40
        or {r["rule_id"] for r in traces} != set(rules)
    ):
        raise ValueError("Every pinned research rule trace is required exactly once")
    confirmed: set[str] = set()
    possible: set[str] = set()
    confirmed_unmapped: set[str] = set()
    possible_unmapped: set[str] = set()
    supporting: dict[str, list[str]] = {"rain": [], "clear": []}
    qualified_daypart_clear = []
    possible_daypart_clear = []
    uncertain_rules = []
    unmapped_rules = []
    for row in traces:
        rid = row["rule_id"]
        rule = rules[rid]
        if row["tags"] != rule["tags"] or row["time_scope"] != rule.get(
            "time_scope", "unspecified"
        ):
            raise ValueError(
                "Research tags or time scope disagree with pinned source rule"
            )
        raw, effective = row["status"], row["effective_status"]
        if (
            raw not in {"matched", "pending_context", "not_met"}
            or (raw != "matched" and effective != raw)
            or (raw == "matched" and effective not in _QUALIFIED)
        ):
            raise ValueError("Unknown or inconsistent research trace status")
        tags = set(row["tags"])
        groups = []
        for name in ["effective_tags", "controlled_tags", "conditional_tags"]:
            values = row[name]
            if (
                not isinstance(values, list)
                or any(not isinstance(t, str) for t in values)
                or len(set(values)) != len(values)
                or not set(values) <= tags
            ):
                raise ValueError("Invalid research tag qualification")
            groups.append(set(values))
        active, controlled, conditional = groups
        if controlled & conditional or active & controlled:
            raise ValueError("Controlled and conditional signs cannot be conflated")
        if raw != "matched" and any(groups):
            raise ValueError("Unmatched traces cannot supply active signs")
        if raw == "matched":
            if active != tags - controlled:
                raise ValueError("Research policy cannot drop or inject active signs")
            if (effective == "matched") != (not controlled and not conditional):
                raise ValueError(
                    "Effective qualification status disagrees with tag groups"
                )
        if raw == "not_met":
            continue
        usable, uncertain = (
            (set(), tags)
            if raw == "pending_context"
            else (active - conditional, conditional)
        )
        if row["time_scope"] != "unspecified":
            if "clear" in usable:
                qualified_daypart_clear.append(rid)
            if "clear" in uncertain:
                possible_daypart_clear.append(rid)
            # Partial-day clear does not assert absence of rain elsewhere today.
            usable = usable - {"clear"}
            uncertain = uncertain - {"clear"}
        confirmed.update(usable & _SIGNS)
        possible.update(uncertain & _SIGNS)
        confirmed_unmapped.update(usable & _UNMAPPED)
        possible_unmapped.update(uncertain & _UNMAPPED)
        for sign in usable & _SIGNS:
            supporting[sign].append(rid)
        if uncertain & (_SIGNS | _UNMAPPED):
            uncertain_rules.append(rid)
        if (usable | uncertain) & _UNMAPPED:
            unmapped_rules.append(rid)
    if weather["time_scope_comparison"] != compare_weather_time_scopes(traces):
        raise ValueError("Complete source time-scope comparison must be retained")
    reasons = []
    if not confirmed:
        reasons.append("no_qualified_daily_categorical_hypothesis")
    elif len(confirmed) > 1:
        reasons.append("conflicting_qualified_daily_hypotheses")
    elif possible & (_SIGNS - confirmed):
        reasons.append("possible_opposing_daily_hypothesis")
    if confirmed_unmapped:
        reasons.append("matched_unmapped_window_or_precipitation_type")
    if possible_unmapped:
        reasons.append("possible_unmapped_window_or_precipitation_type")
    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "label": "abstain" if reasons else ("rain" if "rain" in confirmed else "dry"),
        "reason_codes": reasons,
        "qualified_daily_hypotheses": sorted(confirmed),
        "possible_daily_hypotheses": sorted(possible),
        "qualified_unmapped_tags": sorted(confirmed_unmapped),
        "possible_unmapped_tags": sorted(possible_unmapped),
        "supporting_rule_ids": {k: sorted(v) for k, v in supporting.items()},
        "qualified_daypart_clear_not_full_day_dry": sorted(qualified_daypart_clear),
        "possible_daypart_clear_not_daily_opposition": sorted(possible_daypart_clear),
        "uncertain_rule_ids": sorted(uncertain_rules),
        "unmapped_window_rule_ids": sorted(unmapped_rules),
        "target_date_and_rainfall_threshold_are_research_assumptions": True,
        "unspecified_clear_to_daily_dry_is_research_proxy": True,
        "engine_single_forecast": weather["single_forecast"],
        "research_operationalization_only": True,
        "prediction_efficacy_established": False,
    }
