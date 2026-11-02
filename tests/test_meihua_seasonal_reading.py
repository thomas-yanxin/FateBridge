"""Selected month-strength clauses retain uncertainty and mixed source signals."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.meihua_seasonal_reading import (
    build_seasonal_qualification,
    seasonal_reading_ruleset,
)
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_seasonal_reading import audit_seasonal_reading
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

REFERENCES = Path(__file__).parent / "fixtures/meihua_seasonal_reading_v1"
DIAGRAMS = json.loads((REFERENCES / "cases.json").read_text())["diagrams"]
CASES = [(case, context) for case in DIAGRAMS for context in case["months"]]
TOPICS = ["general", "planning", "reputation", "wealth", "transaction"]


def resolve(out, path):
    value = out
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


@pytest.mark.parametrize(
    "case,context",
    CASES,
    ids=[f"{case['id']}-{context['month']}" for case, context in CASES],
)
@pytest.mark.parametrize("topic", TOPICS)
def test_hand_diagrams_strengths_and_three_joint_rules_match(case, context, topic):
    out = calculate_meihua_cast(
        casting=case["casting"],
        season_month_branch=context["month"],
        interpretation_topic=topic,
    )
    assert "error" not in out
    q = out["interpretation"]["seasonal_qualification"]
    assert [r["strength"] for r in q["roles"]] == context["strengths"]
    assert [r["trigram"] for r in q["roles"]] == case["role_trigrams"]
    assert [r["relation_to_body"] for r in q["roles"][1:]] == case["relations"]
    assert [r["status"] for r in q["condition_checks"]] == context["joint_statuses"]
    assert [r["status"] for r in q["preferences"]] == context["preference_statuses"]
    assert q["summary"] in out["summary"]
    for row in q["roles"]:
        assert resolve(out, row["fact_path"])["name"] == row["trigram"]
        if row["strength_fact_path"] is not None:
            assert resolve(out, row["strength_fact_path"]) == row["strength"]
        if row["relation_fact_path"] is not None:
            assert resolve(out, row["relation_fact_path"]) == row["relation_to_body"]
    assert q["net_verdict"] is q["success_probability"] is q["event_time"] is None


def test_jing_weak_body_attack_and_support_are_not_cancelled_or_ranked():
    out = calculate_meihua_cast(
        casting=DIAGRAMS[0]["casting"], season_month_branch="申"
    )
    q = out["interpretation"]["seasonal_qualification"]
    assert q["simultaneous_increased_constraint_and_partial_relief"]
    assert "受克之忧加重" in out["summary"] and "衰稍解" in out["summary"]
    assert q["net_verdict"] is None
    attacked = next(
        r
        for r in q["condition_checks"]
        if r["rule_id"] == "shuai_body_receives_control"
    )
    assert attacked["countercontrol_qualifications"]["body_mutual"] == "partial_relief"


def test_controlled_support_remains_a_relation_without_claiming_full_rescue():
    out = calculate_meihua_cast(
        casting=DIAGRAMS[2]["casting"], season_month_branch="子"
    )
    q = out["interpretation"]["seasonal_qualification"]
    support = next(
        r
        for r in q["condition_checks"]
        if r["rule_id"] == "shuai_body_receives_generation"
    )
    assert support["status"] == "matched"
    assert support["countercontrol_qualifications"] == {"use": "support_constrained"}
    assert support["full_effect_after_countercontrol"] == "not_adjudicated"
    assert "生助受到限制" in out["summary"] and "衰稍解" in out["summary"]


def test_body_and_supporter_wang_preferences_are_not_a_joint_requirement():
    out = calculate_meihua_cast(
        casting=DIAGRAMS[0]["casting"], season_month_branch="寅"
    )
    q = out["interpretation"]["seasonal_qualification"]
    assert q["condition_checks"][0]["status"] == "matched"
    assert q["preferences"][0]["status"] == "matches"
    assert q["preferences"][1]["status"] == "unknown_strength"
    assert not q["preference_matches_are_joint_necessary_conditions"]


def test_unclassified_strength_is_pending_and_never_neutral_or_weak():
    out = calculate_meihua_cast(
        casting=DIAGRAMS[0]["casting"], season_month_branch="子"
    )
    q = out["interpretation"]["seasonal_qualification"]
    assert q["roles"][0]["strength"] == "原文未定"
    assert all(r["status"] == "pending_strength" for r in q["condition_checks"])
    assert q["preferences"][1]["status"] == "matches"
    assert "未由当前所选月支旺衰表定级" in out["summary"]


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("topic", ["general", "transaction"])
def test_candidate_strength_paths_point_into_own_interpretation_rows(basis, topic):
    out = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        season_month_branch="午",
        interpretation_topic=topic,
    )
    rows = out["interpretation"]["casting_readings"]
    assert len(rows) == 2
    for i, row in enumerate(rows):
        q = row["seasonal_qualification"]
        assert q["roles"][0]["trigram"] == row["body"]
        for role in q["roles"]:
            assert role["fact_path"].startswith(f"meihua.counting_variants.{i}.")
            assert role["strength_fact_path"].startswith(
                f"interpretation.casting_readings.{i}.seasonal_strength."
            )
            assert resolve(out, role["strength_fact_path"]) == role["strength"]
        assert q["summary"] in out["summary"]


def test_time_entry_keeps_calendar_precision_and_body_strength_evidence():
    out = calculate_meihua_analysis(
        analysis_year=2057,
        analysis_month=9,
        analysis_day=28,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
    )
    assert (
        out["meihua"]["calendar_policy"]["label_precision"]["status"]
        == "named_month_start_review_required"
    )
    q = out["interpretation"]["seasonal_qualification"]
    assert q["roles"][0]["trigram"] == out["meihua"]["body_trigram"]["name"]
    assert "相差一日" in out["summary"]


def test_mismatched_cast_strength_or_control_context_is_rejected():
    a = calculate_meihua_cast(casting=DIAGRAMS[0]["casting"], season_month_branch="午")
    b = calculate_meihua_cast(casting=DIAGRAMS[2]["casting"], season_month_branch="午")
    with pytest.raises(ValueError, match="same actual cast"):
        build_seasonal_qualification(
            a["meihua"]["stage_relations"],
            a["meihua"]["seasonal_strength"],
            b["interpretation"]["internal_countercontrol"],
        )
    with pytest.raises(ValueError, match="another cast"):
        build_seasonal_qualification(
            a["meihua"]["stage_relations"],
            b["meihua"]["seasonal_strength"],
            a["interpretation"]["internal_countercontrol"],
        )


def test_repeated_control_threshold_is_not_invented_and_profile_is_isolated():
    p = seasonal_reading_ruleset()
    p["rules"][0]["quote"] = "changed"
    assert seasonal_reading_ruleset()["rules"][0]["quote"] != "changed"
    out = calculate_meihua_cast(
        casting=DIAGRAMS[0]["casting"], season_month_branch="申"
    )
    assert (
        out["interpretation"]["seasonal_qualification"]["repeated_control_clause"][
            "status"
        ]
        == "not_adjudicated"
    )


@pytest.mark.parametrize("month", [None, "申"])
def test_weather_remains_exempt_from_body_strength_reading(month):
    out = calculate_meihua_cast(
        casting=DIAGRAMS[0]["casting"],
        season_month_branch=month,
        interpretation_topic="weather",
    )
    assert out["interpretation"]["seasonal_qualification"] is None


def test_frozen_audit_does_not_claim_prediction_or_full_book_acceptance():
    report = audit_seasonal_reading(REFERENCES)
    assert report["selected_checks_passed"], report
    assert report["unique_hand_diagrams"] == 4 and report["month_context_checks"] == 13
    assert report["selected_source_clauses"] == 6
    assert (
        report["actual_model_runs"]
        == report["predictive_observation_count"]
        == report["original_worked_forecasts_added"]
        == 0
    )
    assert not report["independent_human_expert_review"]
    assert not report["full_chapter_or_book_conformance_established"]
    assert not report["predictive_efficacy_established"]


def test_wrong_frozen_status_is_detected_even_after_rehashing(tmp_path):
    d = tmp_path / "fixtures/meihua_seasonal_reading_v1"
    shutil.copytree(REFERENCES, d)
    for name in [
        "meihua_scan_v1/sources/nlc-1925.pdf",
        "meihua_v1/sources/volume-2.txt",
        "meihua_v1/sources/volume-3.txt",
    ]:
        target = d.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REFERENCES.parent / name, target)
    path = d / "cases.json"
    v = json.loads(path.read_text())
    v["diagrams"][0]["months"][0]["joint_statuses"][0] = "not_matched"
    path.write_text(json.dumps(v, ensure_ascii=False))
    with pytest.raises(ValueError, match="reference changed"):
        audit_seasonal_reading(d)
    manifest = json.loads((d / "manifest.json").read_text())
    manifest["files"]["cases.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (d / "manifest.json").write_text(json.dumps(manifest))
    report = audit_seasonal_reading(d)
    assert not report["selected_checks_passed"]
    assert report["cases"][0]["disagreements"] == ["joint_statuses"]


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
@pytest.mark.parametrize("topic", ["general", "transaction", "weather"])
def test_new_evidence_and_null_weather_agree_on_three_transports(
    tool, topic, rest, tmp_path, capsys
):
    spec = SPECS[tool]
    payload = (
        {"casting": DIAGRAMS[0]["casting"], "season_month_branch": "申"}
        if tool == "meihua_cast"
        else {
            "analysis_year": 2057,
            "analysis_month": 9,
            "analysis_day": 28,
            "analysis_hour": 12,
            "analysis_timezone": "UTC+08:00",
        }
    )
    payload["interpretation_topic"] = topic
    fields = [
        "meihua.seasonal_strength",
        "interpretation.seasonal_qualification",
        "summary",
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
    for out in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        if topic == "weather":
            assert out["interpretation"]["seasonal_qualification"] is None
        else:
            assert (
                out["interpretation"]["seasonal_qualification"]["net_verdict"] is None
            )
