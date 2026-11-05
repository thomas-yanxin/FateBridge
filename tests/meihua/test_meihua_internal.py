"""Actual role control remains conditional, traceable and source scoped."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import TypeAdapter, ValidationError

from fatebridge.core.meihua_countercontrol import (
    build_internal_countercontrol,
    internal_control_ruleset,
)
from fatebridge.core.requests.meihua import MeihuaCasting
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.validation.meihua_internal import audit_internal_controls
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

REFERENCES = Path(__file__).parents[1] / "fixtures/meihua_internal_v1"
BUNDLE = json.loads((REFERENCES / "cases.json").read_text())
CASES = BUNDLE["cases"]
TOPICS = ["general", "planning", "reputation", "wealth", "transaction"]


def resolve(result, path):
    value = result
    for k in path.split("."):
        value = value[int(k)] if isinstance(value, list) else value[k]
    return value


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("topic", TOPICS)
def test_original_worked_diagram_and_direct_control_survive_every_human_affairs_topic(
    case, topic
):
    out = calculate_meihua_cast(casting=case["casting"], interpretation_topic=topic)
    assert "error" not in out
    cast, control = out["meihua"], out["interpretation"]["internal_countercontrol"]
    expected = case["expected"]
    for key in ["raw_upper_number", "raw_lower_number", "line_sum", "moving_line"]:
        assert cast["seed"][key] == expected[key]
    for k, v in [
        ("base_hexagram", "base_code"),
        ("changed_hexagram", "changed_code"),
        ("mutual_hexagram", "mutual_code"),
    ]:
        assert cast[k]["binary_code"] == expected[v]
    assert [r["relation"] for r in cast["stage_relations"]] == expected["relations"]
    assert len(control["nodes"]) == 5 and control["directed_role_pairs_evaluated"] == 20
    assert sum(n["role"] == "body" for n in control["nodes"]) == 1
    for node in control["nodes"]:
        fact = resolve(out, node["fact_path"])
        assert (fact["name"], fact["element"]) == (node["trigram"], node["element"])
    edge = case["expected_partial_relief_edge"]
    relief = [
        q for q in control["qualifications"] if q["qualification"] == "partial_relief"
    ]
    if edge:
        assert any(
            q["role"] == edge[1] and edge[0] in q["incoming_controller_roles"]
            for q in relief
        )
        assert "仍保留原有克体" in out["summary"]
    else:
        assert not relief
    assert (
        control["net_verdict"]
        is control["event_time"]
        is control["success_probability"]
        is None
    )
    assert cast["calendar_policy"]["is_leap_month"] is None
    assert not cast["calendar_policy"]["actual_month_length_validated"]
    assert cast["seasonal_strength"] is None
    assert cast["counting_variants"] == []


def test_wang_relief_does_not_delete_fire_draining_body_or_recursively_cancel():
    out = calculate_meihua_cast(casting=CASES[1]["casting"])
    c = out["interpretation"]["internal_countercontrol"]
    assert "耗泄关系仍须同看" in out["summary"]
    assert not c["recursive_cancellation_applied"]
    assert (
        next(r for r in out["meihua"]["stage_relations"] if r["role"] == "use")[
            "relation"
        ]
        == "体生用"
    )
    edge = next(
        e
        for e in c["control_edges"]
        if (e["controller_role"], e["target_role"]) == ("use", "body_mutual")
    )
    assert edge["controller_relation_to_body"] == "体生用"


def test_support_can_be_constrained_without_turning_into_attack_or_counting_three_votes():
    out = calculate_meihua_cast(casting=BUNDLE["synthetic_probes"][0]["casting"])
    c = out["interpretation"]["internal_countercontrol"]
    q = c["qualifications"][0]
    assert q["original_relation_to_body"] == "用生体"
    assert q["qualification"] == "support_constrained"
    assert q["incoming_controller_roles"] == [
        "body_mutual",
        "use_mutual",
        "changed_use",
    ]
    # The body controls the three controllers, but no recursion cancels them.
    assert all(
        e["controller_itself_controlled_by_roles"] == ["body"]
        for e in c["control_edges"]
        if e["target_role"] == "use"
    )
    assert c["net_verdict"] is None


@pytest.mark.parametrize("branch", [None, "子", "午"])
def test_weak_or_unknown_fire_is_not_silently_disabled(branch):
    out = calculate_meihua_cast(casting=CASES[0]["casting"], season_month_branch=branch)
    c = out["interpretation"]["internal_countercontrol"]
    assert any(
        e["controller_role"] == "use_mutual" and e["target_role"] == "body_mutual"
        for e in c["control_edges"]
    )
    assert not c["seasonal_strength_used_to_disable_control"]
    if branch == "子":
        assert (
            next(
                r
                for r in out["meihua"]["seasonal_strength"]["trigrams"]
                if r["role"] == "use_mutual"
            )["strength"]
            == "衰"
        )


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("topic", ["general", "transaction"])
def test_each_count_candidate_uses_own_geometry_and_fact_paths(basis, topic):
    out = calculate_meihua_cast(
        casting={
            "method": "sound_groups",
            "first_count": 11,
            "second_count": 1,
            "hour_branch": "子",
            "line_sum_basis": basis,
        },
        interpretation_topic=topic,
    )
    rows = out["interpretation"]["casting_readings"]
    assert len(rows) == 2
    for i, row in enumerate(rows):
        c = row["internal_countercontrol"]
        expected = build_internal_countercontrol(
            row["stage_relations"], fact_prefix=f"meihua.counting_variants.{i}"
        )
        assert c == expected
        for node in c["nodes"]:
            assert node["fact_path"].startswith(f"meihua.counting_variants.{i}.")
            assert resolve(out, node["fact_path"])["name"] == node["trigram"]
        assert c["summary"] in out["summary"]
    assert (
        rows[0]["internal_countercontrol"]["nodes"][0]["trigram"]
        != rows[1]["internal_countercontrol"]["nodes"][0]["trigram"]
    )


def test_time_branch_receives_same_control_layer_without_changing_calendar():
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
    assert (
        out["interpretation"]["internal_countercontrol"]["nodes"][0]["trigram"]
        == out["meihua"]["body_trigram"]["name"]
    )
    assert "相差一日" in out["summary"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_weather_branch_does_not_import_internal_body_use_controls(case):
    out = calculate_meihua_cast(casting=case["casting"], interpretation_topic="weather")
    assert out["interpretation"]["internal_countercontrol"] is None
    assert out["interpretation"]["weather"] is not None


@pytest.mark.parametrize(
    "change",
    [
        {"added_count": True},
        {"added_count": 0},
        {"added_count": 1.5},
        {"lunar_month": 13},
        {"lunar_day": 31},
        {"year_branch": "2026"},
        {"line_sum_basis": "raw_counts"},
    ],
)
def test_added_count_rejects_invalid_or_mixed_method_parameters(change):
    with pytest.raises(ValidationError):
        TypeAdapter(MeihuaCasting).validate_python({**CASES[0]["casting"], **change})


def test_added_count_never_fills_missing_year_day_hour_or_count():
    for key in [
        "year_branch",
        "lunar_month",
        "lunar_day",
        "hour_branch",
        "added_count",
    ]:
        value = deepcopy(CASES[0]["casting"])
        value.pop(key)
        with pytest.raises(ValidationError):
            TypeAdapter(MeihuaCasting).validate_python(value)


def test_frozen_reference_and_unresolved_acceptance_boundaries():
    report = audit_internal_controls(REFERENCES)
    assert report["selected_checks_passed"], report
    assert report["source_worked_calculation_count"] == 3
    assert report["synthetic_probe_count"] == 1
    assert report["original_oracle_all_checks_passed"] is False
    assert report["cases"][3]["original_oracle_disagreements"] == ["mutual_code"]
    assert report["cases"][3]["declared_erratum"]["corrected"] == "111110"
    assert report["actual_model_runs"] == report["prospective_observation_count"] == 0
    assert not report["source_stories_are_outcome_observations"]
    assert not report["whole_book_conformance_established"]
    assert not report["predictive_efficacy_established"]


def test_declared_synthetic_mutual_erratum_follows_literal_line_positions():
    code = "011101"
    # Explicit one-based 2,3,4 and 3,4,5, independent of the production helper.
    lower = code[1] + code[2] + code[3]
    upper = code[2] + code[3] + code[4]
    assert lower == "111" and upper == "110"
    assert lower + upper == "111110"


def test_source_profile_copy_is_isolated():
    one = internal_control_ruleset()
    one["rules"][0]["quote"] = "changed"
    assert internal_control_ruleset()["rules"][0]["quote"] != "changed"


def test_tampering_with_oracle_fails_even_after_rehash(tmp_path):
    d = tmp_path / "fixtures/meihua_internal_v1"
    shutil.copytree(REFERENCES, d)
    for name in [
        "meihua_scan_v1/sources/nlc-1925.pdf",
        "meihua_v1/sources/volume-2.txt",
    ]:
        target = d.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REFERENCES.parent / name, target)
    path = d / "cases.json"
    value = json.loads(path.read_text())
    value["cases"][1]["expected"]["moving_line"] = 1
    path.write_text(json.dumps(value, ensure_ascii=False))
    with pytest.raises(ValueError, match="reference changed"):
        audit_internal_controls(d)
    manifest = json.loads((d / "manifest.json").read_text())
    manifest["files"]["cases.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (d / "manifest.json").write_text(json.dumps(manifest))
    report = audit_internal_controls(d)
    assert not report["selected_checks_passed"]
    assert "moving_line" in report["cases"][1]["disagreements"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("topic", ["general", "transaction"])
def test_added_count_control_and_projection_agree_on_rest_mcp_cli(
    case, topic, rest, tmp_path, capsys
):
    spec = SPECS["meihua_cast"]
    fields = [
        "meihua.seed",
        "meihua.calendar_policy",
        "interpretation.internal_countercontrol",
        "summary",
    ]
    payload = {"casting": case["casting"], "interpretation_topic": topic}
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
        assert out["meihua"]["seed"]["moving_line"] == case["expected"]["moving_line"]
        assert out["interpretation"]["internal_countercontrol"]["net_verdict"] is None
