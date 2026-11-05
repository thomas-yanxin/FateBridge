"""Protocol-integrity failures must not become favorable weather-study scores."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

import fatebridge
from fatebridge.validation.meihua_weather_scope_study import audit_scope_weather_study
from tests.support.transports import SPECS, business, rest, surface_calls

REFERENCE = Path(__file__).parents[1] / "fixtures/meihua_weather_policy_v3/plan.json"


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_shell(tmp_path, *, plan_change=None):
    """Small format shell only: no generated forecasts or real observations."""
    base = tmp_path / "study"
    package = Path(fatebridge.__file__).parent
    names = [
        "validation/meihua_weather_policy_v3.py",
        "validation/meihua_weather_scope_study.py",
        "validation/meihua_weather_study.py",
        "validation/meihua_weather_policy_v2.py",
        "core/meihua_weather_time_scope.py",
    ]
    manifest = {}
    for name in names:
        target = base / "engine/src/fatebridge" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package / name, target)
        manifest["src/fatebridge/" + name] = digest(target)
    plan = json.loads(REFERENCE.read_text())
    if plan_change:
        plan_change(plan)
    put(base / "plan.json", plan)
    put(base / "engine-source-sha256.json", manifest)
    put(
        base / "generation-lock.json",
        {"files": {"plan.json": digest(base / "plan.json")}},
    )
    return base


def test_source_change_stops_before_any_observation_or_scoring(tmp_path):
    base = protocol_shell(tmp_path)
    (base / "engine/src/fatebridge/validation/meihua_weather_policy_v3.py").write_text(
        "changed"
    )
    with pytest.raises(ValueError, match="Locked study source"):
        audit_scope_weather_study(base)


def test_source_manifest_path_escape_stops_before_file_read(tmp_path):
    base = protocol_shell(tmp_path)
    put(base / "engine-source-sha256.json", {"../outside": "irrelevant"})
    with pytest.raises(ValueError, match="Locked study source"):
        audit_scope_weather_study(base)


def test_missing_target_day_cannot_create_a_perfect_smaller_cohort(tmp_path):
    base = protocol_shell(
        tmp_path, plan_change=lambda p: p["cohorts"][p["primary_cohort"]].pop()
    )
    with pytest.raises(ValueError, match="Every locked cohort date"):
        audit_scope_weather_study(base)


def test_switching_to_better_looking_context_after_results_is_rejected(tmp_path):
    base = protocol_shell(
        tmp_path, plan_change=lambda p: p.update(primary_scenario="season_not_supplied")
    )
    with pytest.raises(ValueError, match="primary scenario"):
        audit_scope_weather_study(base)


def test_changed_forecast_file_fails_its_pre_outcome_seal(tmp_path):
    base = protocol_shell(tmp_path)
    put(base / "generated/forecasts.json", [])
    put(base / "generated/forecast-seal.json", {"files": {"forecasts.json": "wrong"}})
    with pytest.raises(ValueError, match="Sealed forecasts"):
        audit_scope_weather_study(base)


def test_duplicate_date_scenarios_cannot_be_counted_as_new_samples(tmp_path):
    base = protocol_shell(tmp_path)
    row = {
        "cohort": "retrospective_2024",
        "scenario": "calendar_season_supplied",
        "date": "2024-01-01",
        "label": "rain",
    }
    put(base / "generated/forecasts.json", [row] * 2008)
    put(
        base / "generated/forecast-seal.json",
        {"files": {"forecasts.json": digest(base / "generated/forecasts.json")}},
    )
    with pytest.raises(ValueError, match="required exactly once"):
        audit_scope_weather_study(base)


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
def test_current_negative_study_is_exposed_without_replacing_old_records(
    tool, surface_calls
):
    spec = SPECS[tool]
    payload = {"interpretation_topic": "weather"}
    if tool == "meihua_cast":
        payload["casting"] = {
            "method": "existing",
            "hexagram_code": "001101",
            "moving_line": 1,
        }
    else:
        payload.update(
            analysis_year=2026,
            analysis_month=2,
            analysis_day=19,
            analysis_hour=6,
            analysis_timezone="Asia/Hong_Kong",
        )
    fields = [
        "interpretation.weather.research_validation",
        "interpretation.weather.single_forecast",
    ]
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        projection={"fields": fields, "strict_fields": True, "response_char_limit": 0},
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        weather = result["interpretation"]["weather"]
        evidence = weather["research_validation"]
        assert weather["single_forecast"] is None
        assert evidence["correct"] == 128
        assert evidence["additional_profile_audits"][0]["correct"] == 16
        current = evidence["current_profile_study"]
        assert current["evaluated_ruleset"] == "meihua_weather_v1@1.7.0"
        assert current["primary"]["full_cohort_correct_credit"] == 29
        assert current["primary"]["all_dates_always_dry_correct"] == 158
        assert current["primary"]["primary_full_cohort_gate_met"] is False
        assert current["known_observation_target_dates"] == 1004
        assert current["prospective_case_count"] == current["actual_model_runs"] == 0
        assert not current["daypart_readings_observationally_validated_in_this_cohort"]


def test_source_rule_profile_is_not_mutated_to_link_its_own_evaluation():
    from fatebridge.core.meihua_weather import weather_ruleset
    from fatebridge.validation.meihua_weather_policy_v2 import canonical_sha256

    plan = json.loads(REFERENCE.read_text())
    assert canonical_sha256(weather_ruleset()) == plan["profile_canonical_sha256"]
