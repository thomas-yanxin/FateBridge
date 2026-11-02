"""Capacity bounds accompany the unchanged negative study on every local surface."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_public_capacity_bound_keeps_its_full_cohort_and_negative_result(
    tool, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = {"interpretation_topic": "weather"}
    if tool == "meihua_cast":
        payload["casting"] = {
            "method": "existing",
            "hexagram_code": "011010",
            "moving_line": 5,
        }
    else:
        payload.update(
            analysis_year=2026,
            analysis_month=10,
            analysis_day=23,
            analysis_hour=12,
            analysis_timezone="Asia/Hong_Kong",
            weather_context={"season": "autumn"},
        )
    fields = [
        "interpretation.weather.research_validation.version",
        "interpretation.weather.research_validation.current_profile_study",
        "interpretation.weather.single_forecast",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in fields),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
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
    protocol = asyncio.run(
        native(spec, payload, fields=fields, strict_fields=True, response_char_limit=0)
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    weather = outputs[0]["interpretation"]["weather"]
    assert weather["single_forecast"] is None
    evidence = weather["research_validation"]
    assert evidence["version"] == "1.6.0"
    current = evidence["current_profile_study"]
    assert current["evaluated_ruleset"] == "meihua_weather_v1@1.7.0"
    assert current["primary"]["full_cohort_correct_credit"] == 29
    assert current["primary"]["all_dates_always_dry_correct"] == 158
    assert current["primary"]["primary_full_cohort_gate_met"] is False
    audit = current["primary_attainable_skill_bound"]
    assert audit["file_commitment_verified"]
    assert not audit["study_plan_or_timestamp_authenticated"]
    bound = audit["attainable_skill_bound"]
    assert bound["cohort_days"] == 273
    assert bound["forecast_counts"] == {"rain": 0, "dry": 49, "abstain": 224}
    assert bound["maximum_possible_correct_credit"] == 49
    assert bound["better_constant_credit_lower_bound"] == 137
    assert bound["exact_maximum_margin_over_better_constant"] == -88
    assert not bound["passing_is_possible_for_some_complete_binary_outcomes"]
    assert bound["observed_accuracy"] is None
    assert not bound["observed_outcomes_used"]
    assert not bound["authority_certified"]
