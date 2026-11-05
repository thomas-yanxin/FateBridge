"""Declared absence, uncollected facts and source scope are different states."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core.meihua_observation import quiet_context_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_observation_v1"
CASES = json.loads((FIXTURE / "contexts28.json").read_text())
TOPICS = [
    "general",
    "planning",
    "reputation",
    "wealth",
    "transaction",
    "travel",
    "meeting",
]
CAST = {"method": "existing", "hexagram_code": "100111", "moving_line": 1}
MET = {
    "label": "虚构静室工程示例",
    "quiet_room": True,
    "nothing_heard": True,
    "nothing_seen": True,
}


def calculate(context=None, **extra):
    return calculate_meihua_cast(casting=CAST, observation_context=context, **extra)


def test_frozen_source_and_ternary_truth_values_precede_implementation():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert not manifest["implementation_present"]
    assert not manifest["expected_values_from_production"]
    assert manifest["new_context_truth_cases"] == 28
    for name, digest in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert json.loads((FIXTURE / "live-source-recheck.json").read_text())[
        "same_bytes_as_pinned_original"
    ]


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_complete_ternary_context_on_all_human_branches(case, topic):
    result = calculate(case["input"], interpretation_topic=topic)
    assert "error" not in result
    layer = result["interpretation"]["observation_context"]
    assert layer["status"] == case["status"]
    assert layer["matches_declared_source_conditions"] is case["matches"]
    assert not layer["absence_of_all_actual_omens_independently_verified"]
    assert (
        layer["casting_eligibility"]
        is layer["event_time"]
        is layer["real_outcome"]
        is None
    )
    assert not layer["changes_registered_forecast_eligibility_or_denominators"]
    assert (layer["external_policy_under_selected_declared_context"] is not None) is (
        case["matches"] is True
    )
    assert not layer["internal_basis"]["full_selected_quiet_judgement_established"]


@pytest.mark.parametrize("field", ["quiet_room", "nothing_heard", "nothing_seen"])
@pytest.mark.parametrize("value", [0, 1, 1.0, "true", "false", "unknown", [], {}])
def test_declaration_flags_do_not_coerce_non_boolean_values(field, value):
    assert "error" in calculate({"label": "虚构", field: value})


@pytest.mark.parametrize(
    "value",
    [{}, {"label": ""}, {"label": " "}, {"label": "虚构", "unknown_flag": True}],
)
def test_missing_blank_or_unrecognized_context_is_not_completed_by_defaults(value):
    assert "error" in calculate(value)


def test_label_question_and_inner_moving_line_do_not_fill_external_facts():
    assert (
        calculate(question="虚构：我在静室，什么也没听见看见")["interpretation"][
            "observation_context"
        ]["status"]
        == "not_collected"
    )
    assert (
        calculate({"label": "静室无所闻见"})["interpretation"]["observation_context"][
            "status"
        ]
        == "pending_declared_conditions"
    )
    assert (
        calculate(MET, observer_activity="walking")["interpretation"][
            "observation_context"
        ]["status"]
        == "declared_conditions_met"
    )


def test_declared_quiet_no_perception_cannot_also_request_external_omens():
    assert "error" in calculate(
        MET, external_observations=[{"manifestation": "soil", "label": "虚构外应"}]
    )
    assert "error" in calculate_meihua_cast(casting=CAST, external_observations=[])


@pytest.mark.parametrize(
    "casting,context",
    [
        (
            {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "子",
            },
            {"label": "虚构", "nothing_heard": True},
        ),
        (
            {
                "method": "observed_trigrams",
                "upper_trigram": "乾",
                "lower_trigram": "兑",
                "hour_branch": "子",
            },
            MET,
        ),
    ],
)
def test_explicit_perception_source_conflicts_are_rejected(casting, context):
    assert "error" in calculate_meihua_cast(
        casting=casting, observation_context=context
    )


def test_a_single_vision_flag_does_not_assign_a_modality_to_all_observed_sources():
    result = calculate_meihua_cast(
        casting={
            "method": "observed_trigrams",
            "upper_trigram": "乾",
            "lower_trigram": "兑",
            "hour_branch": "子",
        },
        observation_context={
            "label": "虚构，所闻已报而所见未有",
            "quiet_room": True,
            "nothing_heard": False,
            "nothing_seen": True,
        },
    )
    assert "error" not in result
    assert (
        result["interpretation"]["observation_context"]["status"]
        == "declared_conditions_not_met"
    )


def test_each_count_candidate_keeps_own_body_and_month_strength_paths():
    result = calculate_meihua_cast(
        casting={"method": "object_count", "count": 11, "hour_branch": "丑"},
        season_month_branch="申",
        observation_context=MET,
    )
    assert "error" not in result
    candidates = result["interpretation"]["casting_readings"]
    assert len(candidates) == 2 and len({row["body"] for row in candidates}) == 2
    for index, row in enumerate(candidates):
        layer = row["observation_context"]
        assert layer["internal_basis"]["original_body"]["trigram"] == row["body"]
        assert (
            layer["internal_basis"]["original_body"]["fact_path"]
            == f"meihua.counting_variants.{index}.body_trigram"
        )
        assert (
            layer["internal_basis"]["available_month_strength_fact_path"]
            == f"interpretation.casting_readings.{index}.seasonal_strength"
        )


def test_time_entry_preserves_known_seed_values_without_inventing_strength_synthesis():
    result = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=23,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
        observation_context=MET,
    )
    assert "error" not in result
    layer = result["interpretation"]["observation_context"]
    for row in layer["internal_basis"]["known_seed_calendar_values"]:
        assert row["value"] == result["meihua"]["seed"].get(row["field"])
    assert layer["internal_basis"]["complete_year_month_day_strength_synthesis"] is None
    assert result["analysis_context"]["observation_context"]["quiet_room"] is True


def test_weather_does_not_apply_quiet_body_use_rule_or_change_negative_study():
    assert "error" in calculate(MET, interpretation_topic="weather")
    result = calculate(interpretation_topic="weather")
    assert result["interpretation"]["observation_context"] is None
    primary = result["interpretation"]["weather"]["research_validation"][
        "current_profile_study"
    ]["primary"]
    assert (
        primary["cohort_days"],
        primary["correct"],
        primary["all_dates_always_dry_correct"],
        primary["primary_full_cohort_gate_met"],
    ) == (273, 29, 158, False)


def test_selected_facsimile_words_and_cache_are_not_normalized_to_other_witness():
    profile = quiet_context_ruleset()
    assert profile["quote"].startswith("凡應占在靜室占無所聞見")
    assert profile["comparison_source"]["quote"].startswith("凡占在靜室，無所聞見")
    profile["quote"] = "伪造"
    assert quiet_context_ruleset()["quote"] != "伪造"
