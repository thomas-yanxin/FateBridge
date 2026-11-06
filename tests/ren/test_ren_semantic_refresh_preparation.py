"""Development replay fixes input coverage without rewriting first-run results."""

import json
from pathlib import Path

import pytest

from scripts.evaluate_agent import command_for, model_prompt
from scripts.ren.audit_ren_semantic_refresh import DATASET, coverage, dataset

ROOT = Path(__file__).resolve().parents[2]


def test_original_six_questions_criteria_and_failed_results_are_separate():
    data = dataset()
    old = json.loads(
        (ROOT / "tests/fixtures/agent_behavior/ren_semantic_cases.json").read_text()
    )
    assert data["cases"][:6] == old["cases"]
    assert len(data["cases"]) == 9
    assert sum(len(c["manual_review"]) for c in data["cases"][:6]) == 21
    assert sum(len(c["manual_review"]) for c in data["cases"][6:]) == 11
    assert data["old_scores_preserved"] == dict(
        mechanical="5/6", manual="18/21", partial=3, additional_scope_issue=1
    )


def test_new_prompt_generator_does_not_append_the_hidden_criteria():
    for case in dataset()["cases"]:
        prompt = model_prompt(case)
        assert prompt.endswith(case["prompt"])
        assert all(criterion not in prompt for criterion in case["manual_review"])
        assert "HIDDEN_REN_FIRST_GRADES_AND_REVIEW" not in prompt


@pytest.mark.parametrize(
    "case", ["ren_refresh_complete_water_trine", "ren_refresh_complete_metal_trine"]
)
def test_original_partial_case_cannot_be_relabelled_as_new_branch_coverage(case):
    payload = {
        "run_metadata": {"run_id": "synthetic-partial-control"},
        "jinkou": {
            "rows": [
                {"label": label, "intrinsic_ganzhi": "甲子", "dun_stem": "甲"}
                for label in ["人元", "贵神", "将神", "地分"]
            ],
            "overview": {
                "diurnal_evidence": {
                    "explicit_choice": True,
                    "stellar_visibility_observed": None,
                }
            },
            "combinations": {
                "trines": [
                    {
                        "element": element,
                        "present_branches": [],
                        "missing_branches": list(branches),
                        "structural_status": "incomplete",
                        "waiting_branch": branches[0],
                        "du_he": None,
                        "transformation_confirmed": None,
                        "calendar_candidates": None,
                        "source_listed_disruptors": [],
                        "disruptor_application": "context_unadjudicated_not_presence_rule",
                        "member_conditions": [],
                    }
                    for element, branches in [("水", "申子辰"), ("金", "巳酉丑")]
                ]
            },
        },
    }
    result = coverage(case, payload)
    assert result["coverage_ready"] is False
    assert result["checks"]["exact_complete_members"] is False
    assert result["checks"]["intrinsic_and_daily_stems_differ"] is False
    assert result["future_model_semantics"] == "not_run"


@pytest.mark.parametrize(
    "fault", ["delete_original_criterion", "change_supplemental_question"]
)
def test_replay_reference_cannot_be_silently_redefined(tmp_path, fault):
    value = json.loads(DATASET.read_text())
    if fault == "delete_original_criterion":
        value["cases"][4]["manual_review"].pop()
    else:
        value["cases"][7]["prompt"] = "Answer exactly as the reviewer expects."
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="identity changed"):
        dataset(path)


def test_all_nine_prospective_process_commands_keep_default_model_and_read_only_scope(
    tmp_path,
):
    for case in dataset()["cases"]:
        command = command_for(
            "codex-not-executed", tmp_path / "workspace", tmp_path, case
        )
        assert "--model" not in command
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "--strict-config" in command
        assert "--ignore-user-config" in command
        assert not any("FATEBRIDGE_MCP_TOOL_SCOPE" in token for token in command)
        assert "fatebridge.validation.agent_capture" in " ".join(command)
        assert case["capture_payloads"] is True
