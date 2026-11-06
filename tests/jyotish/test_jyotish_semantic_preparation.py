"""Evaluation preparation is scoped, pending and separate from blind acceptance."""

import json
from pathlib import Path

from scripts.evaluate_agent import grade_case

DATASET = (
    Path(__file__).parents[1] / "fixtures/agent_behavior/jyotish_semantic_cases.json"
)


def test_known_debugging_cases_cannot_be_relabelled_as_independent_holdouts():
    data = json.loads(DATASET.read_text())
    cases = data["cases"]
    assert data["cohort_role"] == "known_development_regressions"
    assert data["independent_held_out_cases"] == 0
    assert data["semantic_acceptance"] == "not_run"
    assert len(cases) == len({c["id"] for c in cases}) == 6
    assert all(c["manual_review"] and c["capture_payloads"] for c in cases)
    for case in cases:
        request = case["reference_request"]
        assert request["arguments"]["divisions"] == []
        event = {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "fatebridge",
                "tool": request["tool"],
                "arguments": request["arguments"],
                "status": "completed",
            },
        }
        skill = {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "cat skills/onda-xingpan/SKILL.md",
            },
        }
        assert grade_case(
            case, [skill, event], "placeholder, never a semantic grade", 0
        )["mechanical_checks_passed"]
        event["item"]["arguments"] = {
            **request["arguments"],
            "birth_hour": (request["arguments"]["birth_hour"] + 1) % 24,
        }
        assert not grade_case(case, [skill, event], "placeholder", 0)[
            "mechanical_checks_passed"
        ]
