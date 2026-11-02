"""Specified-edition topic clauses keep each actual cast and version distinct."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from fatebridge.core.meihua_topics import TOPICS, topic_ruleset
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_topics import audit_topic_clauses
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

REFERENCES = Path(__file__).parent / "fixtures/meihua_topics_v1"
CASES = json.loads((REFERENCES / "cases.json").read_text())["cases"]
VARIANTS = json.loads((REFERENCES / "variant-cases.json").read_text())["cases"]


@pytest.fixture(scope="module")
def audited():
    return audit_topic_clauses(REFERENCES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["topic"] + "-" + c["id"])
def test_frozen_hand_diagrams_select_their_actual_topic_clause(case, audited):
    row = next(
        r
        for r in audited["mathematical_cases"]
        if (r["topic"], r["id"]) == (case["topic"], case["id"])
    )
    assert row["passed"], row


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("case", VARIANTS, ids=lambda c: c["id"])
def test_each_count_candidate_keeps_own_clause_and_stage_context(
    case, basis, topic, audited
):
    row = next(
        r
        for r in audited["retained_cast_checks"]
        if (r["id"], r["topic"], r["selected_basis"]) == (case["id"], topic, basis)
    )
    assert row["passed"], row


def test_selected_nlc_transaction_delay_is_not_replaced_by_transcription_gain():
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="transaction"
    )
    clause = out["interpretation"]["topic_reading"]
    assert clause["relation"] == "体克用"
    assert clause["quote"] == "體尅用交易成遲"
    assert clause["use_role"] == "交易之應"
    assert clause["semantic_tags"] == ["relative_delay"]
    assert clause["comparison_reading"]["quote"] == "體克用，有財"
    assert (
        clause["comparison_reading"]["semantic_status"]
        == "explicit_difference_in_selected_reading"
    )
    assert not clause["comparison_reading"]["used_to_override_selected_edition"]
    assert (
        clause["event_time"]
        is clause["success_probability"]
        is clause["real_outcome_verdict"]
        is None
    )
    assert clause["delay_scope"] == "relative_delay_without_numeric_window"
    assert "交易成遲" in out["summary"]
    assert (
        out["interpretation"]["action_hint"]
        is out["interpretation"]["risk_hint"]
        is None
    )


@pytest.mark.parametrize("topic", TOPICS)
def test_explicit_topic_and_supplied_question_do_not_redraw_or_select_edition(topic):
    cast = {"method": "existing", "hexagram_code": "100111", "moving_line": 1}
    a = calculate_meihua_cast(
        casting=cast, interpretation_topic=topic, question="能否交易赚钱，明天会下雨吗"
    )
    b = calculate_meihua_cast(
        casting=cast, interpretation_topic=topic, question="希望给出相反结果"
    )
    assert a["meihua"] == b["meihua"]
    assert a["interpretation"] == b["interpretation"]
    general = calculate_meihua_cast(casting=cast, question="交易求财")
    assert general["interpretation"]["interpretation_topic"] == "general"
    assert general["interpretation"]["topic_reading"] is None


@pytest.mark.parametrize("topic", TOPICS)
def test_time_entry_retains_lunar_precision_and_selected_chapter(topic):
    result = calculate_meihua_analysis(
        analysis_year=2057,
        analysis_month=9,
        analysis_day=28,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
        interpretation_topic=topic,
    )
    assert "error" not in result
    assert result["interpretation"]["topic_reading"]["topic"] == topic
    assert result["meihua"]["base_hexagram"]["binary_code"] == "101100"
    assert (
        result["meihua"]["calendar_policy"]["label_precision"]["status"]
        == "named_month_start_review_required"
    )
    assert "相差一日" in result["summary"]


def test_thematic_source_checks_do_not_promote_transcription_or_tests_to_authority(
    audited,
):
    assert audited["selected_checks_passed"], audited
    assert audited["runtime_clause_count"] == 20
    assert len(audited["source_checks"]) == 20
    assert len(audited["retained_cast_checks"]) == 16
    assert not audited["full_chapter_conformance_established"]
    assert not audited["independent_human_expert_source_review"]
    assert not audited["exact_event_timing_computed"]
    assert audited["actual_model_runs"] == 0
    assert audited["real_model_semantic_acceptance"] == "not_run"
    assert not audited["real_world_predictive_efficacy_established"]
    assert not audited["authority_certified"]


def test_mutating_a_returned_topic_profile_cannot_change_later_clauses():
    profile = topic_ruleset()
    profile["rules"][0]["quote"] = "伪造文本"
    assert topic_ruleset()["rules"][0]["quote"] != "伪造文本"


def test_changed_manual_relation_does_not_pass_even_after_rehashing_reference(tmp_path):
    target = tmp_path / "fixtures/meihua_topics_v1"
    shutil.copytree(REFERENCES, target)
    for name in ["meihua_scan_v1", "meihua_v1"]:
        shutil.copytree(REFERENCES.parent / name, target.parent / name)
    path = target / "cases.json"
    cases = json.loads(path.read_text())
    cases["cases"][0]["relation"] = "用生体"
    path.write_text(json.dumps(cases, ensure_ascii=False))
    with pytest.raises(ValueError, match="Frozen topic reference changed"):
        audit_topic_clauses(target)
    manifest = target / "manifest.json"
    m = json.loads(manifest.read_text())
    m["files"]["cases.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(m))
    assert not audit_topic_clauses(target)["selected_checks_passed"]


@pytest.mark.parametrize("topic", TOPICS)
def test_weather_context_cannot_silently_influence_a_topic_chapter(topic):
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"],
        interpretation_topic=topic,
        weather_context={"season": "summer"},
    )
    assert out["error_code"] == "validation_error"


@pytest.mark.parametrize("tool", ["meihua_analysis", "meihua_cast"])
@pytest.mark.parametrize("topic", TOPICS)
def test_topic_guidance_projects_source_clause_identically_on_three_surfaces(
    tool, topic, rest, tmp_path, capsys
):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    payload = (
        {
            "casting": {
                "method": "sound_groups",
                "first_count": 11,
                "second_count": 1,
                "hour_branch": "子",
            },
            "season_month_branch": "午",
        }
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 2,
            "analysis_day": 19,
            "analysis_hour": 6,
            "analysis_timezone": "Asia/Hong_Kong",
        }
    )
    payload["interpretation_topic"] = topic
    fields = suggested_fields(spec, view="topic")
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, cli = call_cli(
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
    assert (
        business(response.json())
        == business(cli)
        == business(protocol.structured_content)
    )
    for out in [response.json(), cli, protocol.structured_content]:
        assert out["interpretation"]["topic_reading"]["topic"] == topic
        assert (
            out["interpretation"]["topic_reading"]["selected_edition_id"] == "nlc_1925"
        )


def test_quote_from_another_chapter_cannot_be_laundered_as_planning(
    tmp_path, monkeypatch
):
    from fatebridge.core import meihua_topics

    target = tmp_path / "fixtures/meihua_topics_v1"
    shutil.copytree(REFERENCES, target)
    for name in ["meihua_scan_v1", "meihua_v1"]:
        shutil.copytree(REFERENCES.parent / name, target.parent / name)
    wrong_quote = "用生體，即成，成必有財"  # transaction, not planning
    path = target / "readings.json"
    reference = json.loads(path.read_text())
    next(
        r
        for r in reference["topics"]["planning"]["clauses"]
        if r["relation"] == "用生体"
    )["transcription_quote"] = wrong_quote
    path.write_text(json.dumps(reference, ensure_ascii=False))
    manifest = target / "manifest.json"
    m = json.loads(manifest.read_text())
    m["files"]["readings.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(m))
    profile = topic_ruleset()
    next(r for r in profile["rules"] if r["id"] == "planning_use_generates_body")[
        "comparison_reading"
    ]["quote"] = wrong_quote
    monkeypatch.setattr(meihua_topics, "topic_ruleset", lambda: profile)
    report = audit_topic_clauses(target)
    row = next(
        r
        for r in report["source_checks"]
        if r["clause_id"] == "planning_use_generates_body"
    )
    assert row["comparison_quote_matches"]
    assert not row["comparison_quote_found_in_own_transcription"]
    assert not report["selected_checks_passed"]


def test_unflagged_textual_variants_are_not_certified_semantically_equivalent():
    result = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "101111", "moving_line": 1},
        interpretation_topic="planning",
    )
    row = result["interpretation"]["topic_reading"]
    assert row["quote"] == "用尅體求謀不成成亦有害"
    assert row["comparison_reading"]["quote"] == "用克體，求謀不成，謀亦有害"
    assert row["comparison_reading"]["semantic_status"] == "not_adjudicated"
