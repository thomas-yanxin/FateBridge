"""Synthetic label logic remains distinct from current weather-study outcomes."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.validation.meihua_weather_policy_v2 import (
    canonical_sha256,
    full_cohort_assessment,
    qualified_weather_label,
)
from tests.evaluation.test_agentic_nested_outputs import rest  # noqa: F401

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_weather_policy_v2"
MANIFEST = json.loads((REFERENCES / "manifest.json").read_text())
PROFILE = json.loads((REFERENCES / "profile.json").read_text())
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]


def synthetic(case):
    overrides = {r["rule"]: r for r in case["overrides"]}
    traces = []
    for rule in PROFILE["rules"]:
        override = overrides.get(rule["id"], {})
        status = override.get("status", "not_met")
        controlled = override.get("controlled", [])
        conditional = override.get("conditional", [])
        effective = status
        if status == "matched":
            effective = (
                "conditional_on_unresolved_control"
                if conditional
                else "qualified_by_source_control" if controlled else "matched"
            )
        traces.append(
            {
                "rule_id": rule["id"],
                "status": status,
                "effective_status": effective,
                "tags": deepcopy(rule["tags"]),
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
        "version": "1.5.0",
        "ruleset": deepcopy(PROFILE),
        "rule_trace": traces,
        "single_forecast": None,
    }


def label(weather):
    return qualified_weather_label(
        weather, expected_profile_sha256=MANIFEST["profile_canonical_sha256"]
    )


def test_frozen_policy_examples_keep_their_original_bytes():
    assert (
        hashlib.sha256((REFERENCES / "cases.json").read_bytes()).hexdigest()
        == MANIFEST["cases_sha256"]
    )
    assert canonical_sha256(PROFILE) == MANIFEST["profile_canonical_sha256"]
    assert MANIFEST["real_weather_observations"] == 0


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_manually_declared_synthetic_policy_cases(case):
    result = label(synthetic(case))
    assert result["label"] == case["expected_label"]
    assert result["research_operationalization_only"]
    assert result["engine_single_forecast"] is None
    assert not result["prediction_efficacy_established"]


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "profile",
        "missing",
        "duplicate",
        "unknown_status",
        "wrong_tags",
        "dropped_active_tag",
        "injected_effective_tag",
        "conflated_tags",
        "fake_engine_forecast",
    ],
)
def test_incomplete_or_changed_traces_cannot_supply_successful_labels(mutation):
    weather = synthetic(CASES[0])
    row = next(r for r in weather["rule_trace"] if r["rule_id"] == "symbol_kan")
    if mutation == "version":
        weather["version"] = "1.6.0"
    elif mutation == "profile":
        weather["ruleset"]["title"] = "changed"
    elif mutation == "missing":
        weather["rule_trace"].pop()
    elif mutation == "duplicate":
        weather["rule_trace"][-1] = deepcopy(weather["rule_trace"][0])
    elif mutation == "unknown_status":
        row["effective_status"] = "certain_future_rain"
    elif mutation == "wrong_tags":
        row["tags"] = ["clear"]
    elif mutation == "dropped_active_tag":
        row["effective_tags"] = []
    elif mutation == "injected_effective_tag":
        row["effective_tags"] = ["rain", "clear"]
    elif mutation == "conflated_tags":
        row["controlled_tags"] = row["conditional_tags"] = ["rain"]
    else:
        weather["single_forecast"] = "rain"
    with pytest.raises(ValueError):
        label(weather)


def test_one_correct_forecast_and_365_abstentions_cannot_pass_as_100_percent():
    report = {
        "cohort_days": 366,
        "correct": 1,
        "known_observation_days": 366,
        "issued_forecasts": 366,
        "missing_forecasts": 0,
        "accuracy_on_evaluable_days": 1.0,
        "fixed_baselines": {
            "all_observed_dates": {
                "count": 366,
                "always_rain_correct": 100,
                "always_dry_correct": 266,
            }
        },
    }
    result = full_cohort_assessment(report, expected_cohort_days=366)
    assert result["correct_credit_fraction"] == 1 / 366
    assert result["credit_difference_from_better_constant"] == -265
    assert result["passes_full_cohort_baselines"] is False
    report["known_observation_days"] = report["fixed_baselines"]["all_observed_dates"][
        "count"
    ] = 365
    assert (
        full_cohort_assessment(report, expected_cohort_days=366)[
            "passes_full_cohort_baselines"
        ]
        is None
    )
    report["cohort_days"] = 365
    with pytest.raises(ValueError, match="entire locked cohort"):
        full_cohort_assessment(report, expected_cohort_days=366)


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_old_and_current_negative_studies_remain_separate_on_all_transports(
    tool, rest, tmp_path, capsys
):
    from fatebridge.application.examples import suggested_fields
    from tests.evaluation.test_agentic_nested_outputs import (
        SPECS,
        business,
        call_cli,
        native,
    )

    spec = SPECS[tool]
    payload = (
        {"casting": {"method": "existing", "hexagram_code": "010010", "moving_line": 1}}
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 5,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Hong_Kong",
        }
    )
    payload["interpretation_topic"] = "weather"
    fields = [
        *suggested_fields(spec, view="weather"),
        "interpretation.weather.single_forecast",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", 0),
        ],
    )
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        weather = output["interpretation"]["weather"]
        evidence = weather["research_validation"]
        assert evidence["correct"] == 128 and evidence["evaluable_days"] == 209
        current = next(
            r
            for r in evidence["additional_profile_audits"]
            if r["study_id"] == "meihua-current-1.5.0-HKO-2024-v2"
        )
        assert current["cohort_days"] == 366 and current["abstentions"] == 337
        assert current["correct"] == current["same_dates_always_dry_correct"] == 16
        assert current["primary_full_cohort_gate_met"] is False
        assert current["prospective_case_count"] == 0
        assert weather["single_forecast"] is None
