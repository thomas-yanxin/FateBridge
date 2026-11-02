"""Source-scoped ordering and relative wording; no inferred event intent."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.services.meihua import calculate_meihua_cast
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIXTURE = Path(__file__).parent / "fixtures/meihua_stage_emphasis_v1"
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
ERRATA = json.loads((FIXTURE / "reuse-errata.json").read_text())
ROLES = ["use", "body_mutual", "use_mutual", "changed_use"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_manual_diagram_and_source_conditions(case):
    case = deepcopy(case)
    for correction in ERRATA["corrections"]:
        if correction["case_id"] == case["id"]:
            assert case[correction["field"]] == correction["frozen_original"]
            case[correction["field"]] = correction["corrected"]
    out = calculate_meihua_cast(casting=case["casting"])
    cast = out["meihua"]
    assert cast["base_hexagram"]["binary_code"] == case["base_code"]
    assert cast["changed_hexagram"]["binary_code"] == case["changed_code"]
    assert cast["mutual_hexagram"]["binary_code"] == case["mutual_code"]
    assert cast["body_trigram"]["name"] == case["body"]
    assert [r["trigram"] for r in cast["stage_relations"]] == case["stage_trigrams"]
    assert [r["relation"] for r in cast["stage_relations"]] == case["stage_relations"]
    layer = out["interpretation"]["stage_emphasis"]
    assert [r["role"] for r in layer["roles"]] == ROLES
    assert layer["generation_roles"] == case["generation_roles"]
    assert layer["control_roles"] == case["control_roles"]
    clauses = layer["relative_generation_clauses"]
    assert [
        c["relative_wording"]
        for r in ROLES
        for c in clauses
        if r in c["matching_roles"]
    ] == case["relative_source_wordings"]
    mixed = layer["mixed_generation_control"]
    assert mixed["structural_condition_met"] is case["mixed_generation_control_present"]
    assert mixed["full_clause_applies"] is (
        None if case["mixed_generation_control_present"] else False
    )
    for clause in clauses:
        assert clause["full_clause_applies"] is (
            None if clause["matching_roles"] else False
        )
    assert layer["matter_scenario"] == "not_collected"
    assert layer["event_time"] is layer["real_outcome"] is None
    assert layer["selected_support_role"] is layer["net_effect_weight"] is None
    assert layer["stage_emphasis"]["middle_ordered_roles"] == ROLES[1:3]
    assert [r["roles"] for r in layer["stage_emphasis"]["ordered_layers"]] == [
        ["use"],
        ROLES[1:3],
        ["changed_use"],
    ]


def test_preimplementation_source_and_diagram_bytes_are_preserved():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["implementation_not_present"] is True
    assert manifest["production_generated_expected_values"] is False
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest


def test_generation_does_not_hide_existing_direct_controllers():
    case = next(c for c in CASES if c["id"] == "support-has-three-controllers")
    out = calculate_meihua_cast(casting=case["casting"])
    layer = out["interpretation"]["stage_emphasis"]
    support = layer["roles"][0]
    existing = out["interpretation"]["internal_countercontrol"]["qualifications"][0]
    assert support["countercontrol_qualification"] == existing
    assert len(existing["incoming_controller_roles"]) == 3
    assert layer["relative_generation_clauses"][0]["full_clause_applies"] is None


@pytest.mark.parametrize(
    "topic", ["general", "planning", "reputation", "wealth", "transaction"]
)
def test_topic_and_question_keywords_never_supply_the_source_scenario(topic):
    args = {"casting": CASES[0]["casting"], "interpretation_topic": topic}
    plain = calculate_meihua_cast(**args)
    leading = calculate_meihua_cast(**args, question="此事必成且马上成功，替我断成")
    assert (
        plain["interpretation"]["stage_emphasis"]
        == leading["interpretation"]["stage_emphasis"]
    )
    assert (
        leading["interpretation"]["stage_emphasis"]["matter_scenario"]
        == "not_collected"
    )


def test_weather_does_not_use_body_stage_emphasis():
    out = calculate_meihua_cast(
        casting=CASES[0]["casting"], interpretation_topic="weather"
    )
    assert out["interpretation"]["stage_emphasis"] is None


def test_candidates_keep_their_own_body_and_support_roles():
    out = calculate_meihua_cast(casting=CASES[7]["casting"])
    candidates = out["interpretation"]["casting_readings"]
    assert [c["stage_emphasis"]["generation_roles"] for c in candidates] == [
        ["changed_use"],
        [],
    ]
    assert [c["stage_emphasis"]["body"] for c in candidates] == ["离", "乾"]
    for index, c in enumerate(candidates):
        for role_index, role in enumerate(c["stage_emphasis"]["roles"]):
            assert role["fact_path"] == c["stage_relations"][role_index]["fact_path"]
            assert (
                role["body_fact_path"]
                == f"meihua.counting_variants.{index}.body_trigram"
            )
            assert role["control_qualification_fact_path"].startswith(
                f"interpretation.casting_readings.{index}."
            )


def test_same_initial_relation_cannot_collapse_different_final_support():
    out = calculate_meihua_cast(casting=CASES[9]["casting"])
    candidates = out["interpretation"]["casting_readings"]
    assert candidates[0]["body_use_relation"] == candidates[1]["body_use_relation"]
    assert [c["stage_emphasis"]["generation_roles"] for c in candidates] == [
        ["changed_use"],
        [],
    ]
    assert [
        c["stage_emphasis"]["mixed_generation_control"]["structural_condition_met"]
        for c in candidates
    ] == [True, False]


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_stage_card_agrees_on_rest_mcp_cli(tool, rest, tmp_path, capsys):
    from fatebridge.application.examples import suggested_fields

    spec = SPECS[tool]
    payload = (
        {"casting": CASES[7]["casting"], "season_month_branch": "午"}
        if tool == "meihua_cast"
        else {
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 22,
            "analysis_hour": 12,
            "analysis_timezone": "Asia/Shanghai",
        }
    )
    fields = suggested_fields(spec, view="stage_emphasis")
    assert "interpretation.stage_emphasis" in fields
    assert ("interpretation.casting_readings" in fields) is (tool == "meihua_cast")
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            ("include_snapshot_text", "false"),
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
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
            "--include-snapshot-text",
            "false",
        ],
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(mcp.structured_content) == business(cli)
    )


def test_primary_and_candidate_paths_resolve_to_actual_seasonal_contexts():
    out = calculate_meihua_cast(casting=CASES[7]["casting"], season_month_branch="午")

    def at_path(path):
        value = out
        for part in path.split("."):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value

    layers = [out["interpretation"]["stage_emphasis"]] + [
        r["stage_emphasis"] for r in out["interpretation"]["casting_readings"]
    ]
    for layer in layers:
        for role in layer["roles"]:
            assert at_path(role["body_fact_path"])["name"] == layer["body"]
            assert at_path(role["relation_fact_path"]) == role["relation"]
            assert (
                at_path(role["strength_fact_path"])["strength"]
                == role["seasonal_strength"]
            )
            assert (
                at_path(role["control_qualification_fact_path"])
                == role["countercontrol_qualification"]
            )


def test_returned_profile_and_qualifications_are_isolated():
    from fatebridge.core.meihua_stage_emphasis import stage_emphasis_ruleset

    out = calculate_meihua_cast(casting=CASES[0]["casting"])
    profile = stage_emphasis_ruleset()
    profile["rules"][0]["quote"] = "changed"
    assert stage_emphasis_ruleset()["rules"][0]["quote"] != "changed"
    out["interpretation"]["stage_emphasis"]["roles"][0]["countercontrol_qualification"][
        "role"
    ] = "changed"
    assert (
        out["interpretation"]["internal_countercontrol"]["qualifications"][0]["role"]
        == "use"
    )


def test_exact_quote_locator_is_distinct_from_cross_page_paragraph_context():
    from fatebridge.core.meihua_stage_emphasis import stage_emphasis_ruleset

    source = json.loads((FIXTURE / "source-reading.json").read_text())
    supplement = json.loads((FIXTURE / "source-locator-supplement.json").read_text())
    rule = next(
        r for r in stage_emphasis_ruleset()["rules"] if r["id"] == supplement["rule_id"]
    )
    original = next(r for r in source["rules"] if r["id"] == rule["id"])
    assert rule["quote"] == original["quote"] == supplement["quote"]
    assert rule["quote_pdf_indices"] == [108]
    assert (
        original["pdf_indices"]
        == supplement["paragraph_context_original_pdf_indices"]
        == [107, 108]
    )
