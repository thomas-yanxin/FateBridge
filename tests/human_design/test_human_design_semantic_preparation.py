"""Seal hard-case inputs and separate mechanical checks from semantic judgment."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.application.discovery import select_mcp_specs
from fatebridge.services.tool_catalog import CATALOG
from scripts.evaluate_agent import (
    command_for,
    grade_case,
    model_prompt,
    prepare_workspace,
    source_files,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json"
CASES = json.loads(DATASET.read_text())["cases"]


def test_original_development_cohort_is_sealed_and_cannot_be_relabelled_blind():
    assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == (
        "0e413de085cb892fffa222c05219ec438b0e62f9ee1d769b293c7e0f931dad9b"
    )
    data = json.loads(DATASET.read_text())
    assert data["cohort_role"] == "known_development_regressions"
    assert data["independent_held_out_cases"] == 0
    assert data["real_world_prediction_observations"] == 0
    assert data["semantic_acceptance"] == "not_run"
    assert len(CASES) == len({c["id"] for c in CASES}) == 8
    assert all(c["manual_review"] and c["capture_payloads"] for c in CASES)


def test_profile_really_publishes_human_design():
    specs = select_mcp_specs(CATALOG)
    assert "human_design" in {s.tool_name for s in specs}
    assert DATASET in source_files()


def test_complete_answer_challenge_is_frozen_separately_from_original_cases():
    from scripts.human_design.audit_human_design_semantics import COHORT_SHA256

    path = ROOT / "tests/fixtures/agent_behavior/human_design_complete_case_v3.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == ("c2f5454a5be108312a77c28ad239ddfd36849e2f01e97465e5813269759062e8")
        == COHORT_SHA256["complete-answer-v3"]
    )
    data = json.loads(path.read_text())
    assert data["independent_held_out_cases"] == 0
    assert data["real_world_prediction_observations"] == 0
    assert data["original8_cases_replaced"] is False
    assert data["source_contract_v2_cases_replaced"] is False
    assert "not_independent_holdout" in data["cohort_role"]
    case = data["cases"][0]
    assert case["full_export"] == "human_design"
    assert len(case["manual_review"]) == 10
    assert all(c not in model_prompt(case) for c in case["manual_review"])


def test_no_tool_contract_is_explicit_for_non_external_suites():
    case = CASES[0]
    assert "evaluation_layer" not in case
    assert case["allowed_tools"] == []
    assert "不调用任何 FateBridge 工具" in model_prompt(case)


def test_explicit_native_data_selection_is_forwarded_without_environment_secrets(
    monkeypatch,
):
    monkeypatch.setenv("SE_EPHE_PATH", "/verified/ephe")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "/verified/de441.eph")
    monkeypatch.setenv("XDG_CACHE_HOME", "/verified/cache")
    monkeypatch.setenv("UNRELATED_TEST_SECRET", "must-not-enter-command")
    command = command_for("codex", Path("/workspace"), Path("/output"), CASES[1])
    assert 'mcp_servers.fatebridge.env.SE_EPHE_PATH="/verified/ephe"' in command
    assert (
        'mcp_servers.fatebridge.env.FATEBRIDGE_JPL_FILE="/verified/de441.eph"'
        in command
    )
    assert 'mcp_servers.fatebridge.env.XDG_CACHE_HOME="/verified/cache"' in command
    assert not any(
        "UNRELATED_TEST_SECRET" in v or "must-not-enter-command" in v for v in command
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_hidden_criteria_never_enter_model_prompt(case):
    prompt = model_prompt(case)
    assert case["prompt"] in prompt
    assert all(text not in prompt for text in case["manual_review"])
    assert "manual_review" not in prompt


@pytest.mark.parametrize("case", CASES[1:], ids=lambda c: c["id"])
def test_mechanical_success_never_claims_semantic_success_and_input_errors_fail(case):
    arguments = case["reference_request"]["arguments"]
    skill = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": "cat skills/onda-xingpan/SKILL.md",
        },
    }
    call = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": "fatebridge",
            "tool": "human_design",
            "arguments": {**arguments, "fields": None},
            "status": "completed",
        },
    }
    result = grade_case(case, [skill, call], "placeholder; not a semantic judgment", 0)
    assert result["mechanical_checks_passed"]
    assert "semantic_acceptance" not in result
    assert "semantic_status" not in result
    call["item"]["arguments"]["birth_hour"] = (arguments["birth_hour"] + 1) % 24
    assert (
        "input_mismatch:human_design"
        in grade_case(case, [skill, call], "x", 0)["failures"]
    )


def test_workspace_keeps_runtime_sources_but_excludes_past_answers_and_reviews(
    tmp_path,
):
    source = tmp_path / "source"
    workspace = tmp_path / "model"
    workspace.mkdir()
    for name in ["skills/onda-xingpan", "src/fatebridge", "docs/validation"]:
        (source / name).mkdir(parents=True, exist_ok=True)
    (source / "AGENTS.md").write_text("Runtime instructions")
    (source / "skills/onda-xingpan/SKILL.md").write_text("Runtime consultation")
    (source / "src/fatebridge/runtime.py").write_text("RUNTIME = True")
    (source / "docs/human-design.md").write_text("Runtime mechanics")
    (source / "docs/human-design-semantics-evaluation.md").write_text("HIDDEN REVIEW")
    (source / "docs/validation/answer.txt").write_text("HIDDEN ANSWER")
    prepare_workspace(workspace, source)
    assert (workspace / "docs/human-design.md").read_text() == "Runtime mechanics"
    assert (workspace / "src/fatebridge/runtime.py").exists()
    assert not (workspace / "docs/human-design-semantics-evaluation.md").exists()
    assert not (workspace / "docs/validation").exists()
    assert (workspace / ".agents/skills/onda-xingpan/SKILL.md").is_file()
