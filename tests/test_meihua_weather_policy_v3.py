"""Locked scope-aware logical probes are not actual rainfall observations."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.meihua_weather_time_scope import compare_weather_time_scopes
from fatebridge.validation.meihua_weather_policy_v2 import (
    canonical_sha256,
    full_cohort_assessment,
)
from fatebridge.validation.meihua_weather_policy_v3 import scope_aware_weather_label

REF = Path(__file__).parent / "fixtures/meihua_weather_policy_v3"
MANIFEST = json.loads((REF / "manifest.json").read_text())
PROFILE = json.loads((REF / "profile.json").read_text())
CONTROL = json.loads((REF / "control-profile.json").read_text())
PLAN = json.loads((REF / "plan.json").read_text())
CASES = json.loads((REF / "cases.json").read_text())["cases"]


def synthetic(case):
    overrides = {r["rule"]: r for r in case["overrides"]}
    traces = []
    for rule in PROFILE["rules"]:
        over = overrides.get(rule["id"], {})
        status = over.get("status", "not_met")
        controlled = over.get("controlled", [])
        conditional = over.get("conditional", [])
        effective = (
            status
            if status != "matched"
            else (
                "conditional_on_unresolved_control"
                if conditional
                else ("qualified_by_source_control" if controlled else "matched")
            )
        )
        traces.append(
            {
                "rule_id": rule["id"],
                "tags": deepcopy(rule["tags"]),
                "time_scope": rule.get("time_scope", "unspecified"),
                "status": status,
                "effective_status": effective,
                "effective_tags": (
                    [t for t in rule["tags"] if t not in controlled]
                    if status == "matched"
                    else []
                ),
                "controlled_tags": controlled,
                "conditional_tags": conditional,
            }
        )
    return {
        "ruleset_id": "meihua_weather_v1",
        "version": "1.7.0",
        "ruleset": deepcopy(PROFILE),
        "control_profile": deepcopy(CONTROL),
        "single_forecast": None,
        "casting_variants": [],
        "casting_variant_traces": [],
        "rule_trace": traces,
        "time_scope_comparison": compare_weather_time_scopes(traces),
    }


def label(weather):
    return scope_aware_weather_label(
        weather,
        expected_profile_sha256=PLAN["profile_canonical_sha256"],
        expected_control_profile_sha256=PLAN["control_profile_canonical_sha256"],
    )


def test_policy_plan_and_logical_oracles_remain_fixed():
    for name, digest in MANIFEST["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((REF / name).read_bytes()).hexdigest() == digest
    assert canonical_sha256(PROFILE) == PLAN["profile_canonical_sha256"]
    assert canonical_sha256(CONTROL) == PLAN["control_profile_canonical_sha256"]
    assert MANIFEST["real_weather_observations_in_synthetic_corpus"] == 0
    assert {k: len(v) for k, v in PLAN["cohorts"].items()} == {
        "primary_2026_ytd_through_last_complete_month": 273,
        "retrospective_2024": 366,
        "retrospective_2025": 365,
    }


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_frozen_scope_aware_research_labels(case):
    q = label(synthetic(case))
    assert q["label"] == case["expected_label"]
    assert q["engine_single_forecast"] is None
    assert q["target_date_and_rainfall_threshold_are_research_assumptions"]
    assert q["unspecified_clear_to_daily_dry_is_research_proxy"]
    assert not q["prediction_efficacy_established"]


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "profile",
        "control_profile",
        "missing",
        "duplicate",
        "fake_forecast",
        "count_candidates",
        "scope",
        "comparison",
        "dropped_tag",
        "injected_tag",
        "status",
        "matched_with_qualification",
    ],
)
def test_incomplete_or_forged_source_trace_is_not_a_successful_label(mutation):
    w = synthetic(CASES[0])
    row = next(r for r in w["rule_trace"] if r["rule_id"] == "symbol_kan")
    if mutation == "version":
        w["version"] = "1.5.0"
    elif mutation == "profile":
        w["ruleset"]["title"] = "changed"
    elif mutation == "control_profile":
        w["control_profile"]["title"] = "changed"
    elif mutation == "missing":
        w["rule_trace"].pop()
    elif mutation == "duplicate":
        w["rule_trace"][-1] = deepcopy(w["rule_trace"][0])
    elif mutation == "fake_forecast":
        w["single_forecast"] = "rain"
    elif mutation == "count_candidates":
        w["casting_variants"] = [{"selected": True}]
    elif mutation == "scope":
        row["time_scope"] = "morning"
    elif mutation == "comparison":
        w["time_scope_comparison"]["groups"] = []
    elif mutation == "dropped_tag":
        row["effective_tags"] = []
    elif mutation == "injected_tag":
        row["effective_tags"] = ["rain", "clear"]
    elif mutation == "status":
        row["effective_status"] = "certain_future"
    else:
        row["conditional_tags"] = ["rain"]
    with pytest.raises(ValueError):
        label(w)


def test_morning_clear_and_evening_rain_do_not_become_daily_conflict():
    case = next(r for r in CASES if r["id"] == "morning-clear-evening-rain-compatible")
    q = label(synthetic(case))
    assert q["label"] == "rain"
    assert q["qualified_daily_hypotheses"] == ["rain"]
    assert q["qualified_daypart_clear_not_full_day_dry"] == [
        "li_above_gen_morning_clear"
    ]


def test_displayed_prior_study_results_cannot_change_the_new_policy_label():
    w = synthetic(CASES[0])
    expected = label(w)
    w["research_validation"] = {
        "score": 100,
        "label": "dry",
        "authority_certified": True,
    }
    assert label(w) == expected


def test_primary_endpoint_keeps_unknown_observations_and_abstentions():
    r = {
        "cohort_days": 273,
        "correct": 1,
        "known_observation_days": 272,
        "issued_forecasts": 273,
        "missing_forecasts": 0,
        "fixed_baselines": {
            "all_observed_dates": {
                "count": 272,
                "always_rain_correct": 100,
                "always_dry_correct": 172,
            }
        },
    }
    q = full_cohort_assessment(r, expected_cohort_days=273)
    assert q["correct_credit_fraction"] == 1 / 273
    assert q["passes_full_cohort_baselines"] is None
