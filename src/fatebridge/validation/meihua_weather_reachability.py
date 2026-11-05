"""Exhaust symbolic support without using observations or selecting clocks.

This is a structural check of one pinned research operationalization. A positive
symbolic state is not a real dated forecast or evidence of predictive efficacy.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from fatebridge.core.divination import derive_meihua_hexagram
from fatebridge.core.meihua_weather import build_weather_interpretation
from fatebridge.validation.meihua_source_guard import (
    capture_package_sources,
    verify_package_sources,
)
from fatebridge.validation.meihua_weather_policy_v2 import canonical_sha256
from fatebridge.validation.meihua_weather_policy_v3 import scope_aware_weather_label

PROFILE_SHA256 = "c86045852fe4898152a183ea51f1c60f570fb6205dfdb764c77fa095c4403bb7"
CONTROL_SHA256 = "e4936c492ab61da234951ce22efe1c018c664bc0e100dfdc1a9ebd06cdc8fd21"
POLICY_SHA256 = "1ae45f5a674728a69290171eedffa43022ba1a13499dcf567f3dfafdf43731fd"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
SEASONS = (None, "spring", "summer", "autumn", "winter")
TRACE_KEYS = (
    "ruleset_id",
    "version",
    "context",
    "trigram_slots",
    "trigram_counts",
    "frequency_views",
    "controls",
    "rule_trace",
    "time_scope_comparison",
    "single_forecast",
    "casting_variants",
    "casting_variant_traces",
)


def rain_exclusion_certificate(weather: dict[str, Any]) -> dict[str, Any] | None:
    """Give a sufficient non-rain-label reason, separate from its actual label.

    The caller first validates all forty pinned traces through the locked policy.
    This certificate concerns that research mapping, not absence of real rain.
    """
    qualified_rain = []
    qualified_clear = []
    possible_clear = []
    unmapped = []
    for row in weather["rule_trace"]:
        raw = row["status"]
        if raw == "not_met":
            continue
        certain = (
            set(row["effective_tags"]) - set(row["conditional_tags"])
            if raw == "matched"
            else set()
        )
        possible = (
            set(row["tags"])
            if raw == "pending_context"
            else set(row["conditional_tags"])
        )
        rid = row["rule_id"]
        if "rain" in certain:
            qualified_rain.append(rid)
        if row["time_scope"] == "unspecified":
            if "clear" in certain:
                qualified_clear.append(rid)
            if "clear" in possible:
                possible_clear.append(rid)
        if (certain | possible) & {"variable", "rain_stopping", "snow"}:
            unmapped.append(rid)
    reasons = []
    if not qualified_rain:
        reasons.append({"reason": "no_qualified_rain_hypothesis", "rule_ids": []})
    if qualified_clear:
        reasons.append(
            {
                "reason": "qualified_unspecified_clear_blocks_unambiguous_rain",
                "rule_ids": qualified_clear,
            }
        )
    if possible_clear:
        reasons.append(
            {
                "reason": "possible_unspecified_clear_blocks_unambiguous_rain",
                "rule_ids": possible_clear,
            }
        )
    if unmapped:
        reasons.append(
            {
                "reason": "unmapped_type_or_window_blocks_categorical_label",
                "rule_ids": unmapped,
            }
        )
    if not reasons:
        return None
    return {
        "conclusion": "not_a_rain_label_under_pinned_policy",
        "qualified_rain_rule_ids": qualified_rain,
        "sufficient_reasons": reasons,
        "real_rain_absence_inferred": False,
    }


def audit_time_weather_reachability() -> dict[str, Any]:
    """Exhaust twelve hours times24 seed residues times five season contexts."""
    package = Path(__file__).resolve().parents[1]
    source_receipt = capture_package_sources(package)
    rows: list[dict[str, Any]] = []
    arithmetic: list[dict[str, Any]] = []
    legacy_metadata_attached = False
    counts: dict[int, dict[str, Counter[str]]] = {
        h: {str(s): Counter() for s in SEASONS} for h in range(1, 13)
    }
    for hour, branch in enumerate(BRANCHES, 1):
        for day in range(1, 25):
            total = day + 2  # Nominal year子=1 and month1 cover every S residue.
            cast = derive_meihua_hexagram(
                year_branch="子", lunar_month=1, lunar_day=day, hour_branch=branch
            )
            geometry = {
                "hour_number": hour,
                "s_residue": total % 24,
                "representative_s": total,
                "representative_day": day,
                "upper_number": cast["seed"]["upper_number"],
                "lower_number": cast["seed"]["lower_number"],
                "moving_line": cast["seed"]["moving_line"],
                "base_code": cast["base_hexagram"]["binary_code"],
                "changed_code": cast["changed_hexagram"]["binary_code"],
                "mutual_code": cast["mutual_hexagram"]["binary_code"],
            }
            arithmetic.append(geometry)
            for season in SEASONS:
                weather = build_weather_interpretation(cast, {"season": season})[
                    "weather"
                ]
                legacy_metadata_attached |= "research_validation" in weather
                decision = scope_aware_weather_label(
                    weather,
                    expected_profile_sha256=PROFILE_SHA256,
                    expected_control_profile_sha256=CONTROL_SHA256,
                )
                certificate = rain_exclusion_certificate(weather)
                if (decision["label"] == "rain") != (certificate is None):
                    raise ValueError(
                        "Independent exclusion conditions disagree with policy"
                    )
                counts[hour][str(season)][decision["label"]] += 1
                rows.append(
                    {
                        "hour_number": hour,
                        "hour_branch": branch,
                        "s_residue": total % 24,
                        "season": season,
                        "geometry_index": len(arithmetic) - 1,
                        "weather_trace_sha256": canonical_sha256(
                            {k: weather[k] for k in TRACE_KEYS}
                        ),
                        "decision": decision,
                        "rain_exclusion_certificate": certificate,
                    }
                )
    assert len(arithmetic) == 288 and len(rows) == 1440
    assert len({(r["hour_number"], r["s_residue"], r["season"]) for r in rows}) == 1440
    hourly: list[dict[str, Any]] = []
    for hour, branch in enumerate(BRANCHES, 1):
        own = [r for r in rows if r["hour_number"] == hour]
        rain = [r for r in own if r["decision"]["label"] == "rain"]
        hourly.append(
            {
                "hour_number": hour,
                "hour_branch": branch,
                "contexts": {
                    str(s): {
                        k: counts[hour][str(s)][k] for k in ["rain", "dry", "abstain"]
                    }
                    for s in SEASONS
                },
                "rain_label_symbolically_reachable": bool(rain),
                "all_nonrain_rows_have_exclusion_certificate": all(
                    r["rain_exclusion_certificate"] is not None
                    for r in own
                    if r["decision"]["label"] != "rain"
                ),
                "positive_symbolic_witnesses_are_not_real_dated_forecasts": True,
            }
        )
    noon = hourly[6]
    obstruction = not noon["rain_label_symbolically_reachable"]
    verify_package_sources(package, source_receipt)
    return {
        "audit_id": "meihua_weather_time_reachability_v1",
        "version": "1.0.0",
        "weather_profile": "meihua_weather_v1@1.7.0",
        "research_policy": "qualified_scope_aware_daily_rain_clear_v3@1.0.0",
        "profile_canonical_sha256": PROFILE_SHA256,
        "control_profile_canonical_sha256": CONTROL_SHA256,
        "policy_sha256": POLICY_SHA256,
        "engine_source_sha256": source_receipt,
        "engine_source_manifest_canonical_sha256": canonical_sha256(source_receipt),
        "period": {
            "seed_sum": "year_branch_number+nominal_lunar_month+nominal_lunar_day",
            "modulus": 24,
            "proof": "24 is divisible by8 and6; S+24 preserves both trigram numbers and moving line, hence selected geometry",
            "arithmetic_cases": 288,
            "context_cases": 1440,
        },
        "context": {
            "season_domain": list(SEASONS),
            "many_min_count": None,
            "prior_condition": None,
        },
        "calendar_domain_relation": "overapproximation; negative reachability transfers to real dated subsets, positive symbolic witnesses do not establish real date reachability",
        "all_hours_in_natural_order_no_clock_selection": hourly,
        "locked_noon_preflight": {
            "hour_number": 7,
            "hour_branch": "午",
            "issue_policy": "previous_civil_day12:00",
            "rain_label_symbolically_reachable": noon[
                "rain_label_symbolically_reachable"
            ],
            "structural_obstruction": obstruction,
            "status": (
                "dominated_by_always_dry"
                if obstruction
                else "not_structurally_excluded_not_efficacy_acceptance"
            ),
            "strict_full_cohort_superiority_possible": False if obstruction else None,
            "endpoint_conditions": [
                "same complete binary target dates",
                "zero correct credit for abstention",
                "comparison against always_dry",
            ],
            "mathematical_inference": "With only dry/abstain labels, every correct credit also belongs to always_dry; strict superiority is impossible",
            "legacy_primary_gate_passed": False,
            "forecast_or_cohort_modified": False,
        },
        "raw_observation_files_read": False,
        "legacy_result_metadata_attached_by_weather_engine": legacy_metadata_attached,
        "legacy_result_metadata_used_for_labels_or_clock_selection": False,
        "outcome_blind_study": False,
        "earlier_negative_results_known": True,
        "new_real_outcomes": 0,
        "independent_model_semantic_evaluations": 0,
        "clock_recommendation": None,
        "original_future_v1_trial_modified": False,
        "real_world_predictive_efficacy_established": False,
        "arithmetic_cases": arithmetic,
        "state_cases": rows,
    }
