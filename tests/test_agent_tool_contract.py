"""Operational tool restrictions must be visible while grading remains frozen."""

import json
from pathlib import Path

from scripts.evaluate_agent import command_for, grade_case, model_prompt
from tests.test_agent_evaluation import event

ROOT = Path(__file__).resolve().parents[1]


def test_prompt_exposes_allowed_tools_without_answer_or_hidden_rubric():
    case = {
        "prompt": "解释这次结果",
        "allowed_tools": ["bazi_birth", "knowledge_read"],
        "manual_review": ["HIDDEN_CRITERION"],
        "argument_paths": {"bazi_birth": {"HIDDEN_EXPECTED_VALUE": 1}},
    }
    prompt = model_prompt(case)
    assert "bazi_birth、knowledge_read" in prompt
    assert prompt.endswith(case["prompt"])
    assert "HIDDEN_" not in prompt
    assert model_prompt({"prompt": "unchanged"}) == "unchanged"


def test_original_failed_comprehensive_call_still_fails_the_same_tool_gates():
    cases = json.loads(
        (ROOT / "tests/fixtures/agent_behavior/bazi_semantic_cases_v1.json").read_text()
    )["cases"]
    case = cases[0]
    assert "bazi_birth" in model_prompt(case)
    failed = grade_case(
        case,
        [event("analyze_destiny", case["reference_request"]["arguments"])],
        "actual answer",
        0,
    )
    assert {
        "missing_tool:bazi_birth",
        "out_of_scope_tool",
        "input_mismatch:bazi_birth",
    } <= set(failed["failures"])


def test_calculation_server_is_required_before_the_models_initial_catalog():
    command = command_for("codex", Path("/workspace"), Path("/output"), {})
    assert "--strict-config" in command
    assert "mcp_servers.fatebridge.required=true" in command
    assert not any("enabled_tools" in token for token in command)
