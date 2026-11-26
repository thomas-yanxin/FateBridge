"""Version-pinned research labels; never an engine forecast or probability."""

from __future__ import annotations

import hashlib
import json
from typing import Any

POLICY_ID = "qualified_unambiguous_rain_clear_v2"
_SIGNS = {"rain", "clear"}
_UNMAPPED = {"variable", "rain_stopping", "snow"}
_QUALIFIED = {
    "matched",
    "qualified_by_source_control",
    "conditional_on_unresolved_control",
    "conditional_on_unresolved_frequency",
    "multiple_qualifications",
}


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def qualified_weather_label(
    weather: dict[str, Any], *, expected_profile_sha256: str
) -> dict[str, Any]:
    """Use complete actual traces; unsupported/missing data are errors, not wins.

    The calling study must pin the profile and target/window beforehand. Possible
    same-direction signs reinforce no categorical decision; possible opposite or
    unmapped-window signs prevent one. Nothing here reads weather observations.
    """
    profile = weather["ruleset"]
    if (
        weather["ruleset_id"] != "meihua_weather_v1"
        or weather["version"] != "1.5.0"
        or profile["id"] != weather["ruleset_id"]
        or profile["version"] != weather["version"]
        or canonical_sha256(profile) != expected_profile_sha256
    ):
        raise ValueError("The v2 research policy requires its pinned1.5.0 profile")
    rules = {r["id"]: r for r in profile["rules"]}
    if weather["single_forecast"] is not None:
        raise ValueError("The pinned engine has no certified single forecast")
    traces = weather["rule_trace"]
    if len(traces) != len(rules) or {r["rule_id"] for r in traces} != set(rules):
        raise ValueError("Research labels require every rule trace exactly once")
    confirmed: set[str] = set()
    possible: set[str] = set()
    confirmed_unmapped: set[str] = set()
    possible_unmapped: set[str] = set()
    supports: dict[str, list[str]] = {"rain": [], "clear": []}
    uncertain_rules = []
    unmapped_rules = []
    for row in traces:
        rid = row["rule_id"]
        if row["tags"] != rules[rid]["tags"]:
            raise ValueError("Research trace tags disagree with the pinned rule")
        raw = row["status"]
        effective = row["effective_status"]
        if (
            raw not in {"matched", "pending_context", "not_met"}
            or (raw != "matched" and effective != raw)
            or (raw == "matched" and effective not in _QUALIFIED)
        ):
            raise ValueError("Unknown or inconsistent research trace status")
        tags = set(row["tags"])
        groups = []
        for name in ["effective_tags", "controlled_tags", "conditional_tags"]:
            value = row[name]
            if (
                not isinstance(value, list)
                or any(not isinstance(t, str) for t in value)
                or len(set(value)) != len(value)
                or not set(value).issubset(tags)
            ):
                raise ValueError("Invalid research trace tag qualification")
            groups.append(set(value))
        active, controlled, conditional = groups
        if controlled & conditional or active & controlled:
            raise ValueError("Controlled and qualified signs cannot be conflated")
        if raw != "matched" and any(groups):
            raise ValueError("Unmatched trace must not supply effective signs")
        if raw == "matched" and active != tags - controlled:
            raise ValueError("Research labels cannot silently drop active tags")
        if raw == "not_met":
            continue
        if raw == "pending_context":
            uncertain = tags
            usable: set[str] = set()
        else:
            usable = active - conditional
            uncertain = conditional
        confirmed.update(usable & _SIGNS)
        possible.update(uncertain & _SIGNS)
        confirmed_unmapped.update(usable & _UNMAPPED)
        possible_unmapped.update(uncertain & _UNMAPPED)
        for sign in usable & _SIGNS:
            supports[sign].append(rid)
        if uncertain & (_SIGNS | _UNMAPPED):
            uncertain_rules.append(rid)
        if (usable | uncertain) & _UNMAPPED:
            unmapped_rules.append(rid)
    reasons = []
    if not confirmed:
        reasons.append("no_qualified_categorical_sign")
    elif len(confirmed) > 1:
        reasons.append("conflicting_qualified_categorical_signs")
    else:
        opposite = _SIGNS - confirmed
        if possible & opposite:
            reasons.append("possible_opposing_categorical_sign")
    if confirmed_unmapped:
        reasons.append("matched_unmapped_window_or_precipitation_type")
    if possible_unmapped:
        reasons.append("possible_unmapped_window_or_precipitation_type")
    label = "abstain" if reasons else "rain" if "rain" in confirmed else "dry"
    return {
        "policy_id": POLICY_ID,
        "label": label,
        "reason_codes": reasons,
        "qualified_signs": sorted(confirmed),
        "possible_signs": sorted(possible),
        "qualified_unmapped_tags": sorted(confirmed_unmapped),
        "possible_unmapped_tags": sorted(possible_unmapped),
        "supporting_rule_ids": {k: sorted(v) for k, v in supports.items()},
        "uncertain_rule_ids": sorted(uncertain_rules),
        "unmapped_window_rule_ids": sorted(unmapped_rules),
        "engine_single_forecast": weather["single_forecast"],
        "research_operationalization_only": True,
        "prediction_efficacy_established": False,
    }


def full_cohort_assessment(
    report: dict[str, Any], *, expected_cohort_days: int
) -> dict[str, Any]:
    """Abstaining cannot turn a small perfect subset into a primary pass."""
    n = report["cohort_days"]
    if type(n) is not int or n != expected_cohort_days or n <= 0:
        raise ValueError("The primary endpoint requires the entire locked cohort")
    baseline = report["fixed_baselines"]["all_observed_dates"]
    if baseline["count"] != report["known_observation_days"]:
        raise ValueError("Full-cohort baseline denominator disagrees")
    complete = (
        report["known_observation_days"] == n
        and report["issued_forecasts"] == n
        and report["missing_forecasts"] == 0
    )
    best_constant = max(baseline["always_rain_correct"], baseline["always_dry_correct"])
    return {
        "primary_endpoint": "correct_credit_over_all_locked_days",
        "cohort_days": n,
        "all_observations_and_forecasts_present": complete,
        "correct_credit": report["correct"],
        "correct_credit_fraction": report["correct"] / n,
        "better_constant_baseline_credit": best_constant,
        "better_constant_baseline_credit_fraction": best_constant / n,
        "credit_difference_from_better_constant": report["correct"] - best_constant,
        "passes_full_cohort_baselines": (
            report["correct"] > best_constant if complete else None
        ),
        "conditional_accuracy_is_not_primary_endpoint": True,
        "abstentions_or_unknowns_get_correct_credit": False,
        "real_world_predictive_efficacy_established": False,
        "authority_certified": False,
    }
