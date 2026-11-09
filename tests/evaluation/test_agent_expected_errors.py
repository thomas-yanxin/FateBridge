"""Expected refusal is exact, captured and separate from a successful chart."""

import asyncio
import json
from pathlib import Path

import pytest

from scripts.evaluate_agent import (
    ROOT,
    error_response,
    grade_case,
    matches_expected_error,
    model_prompt,
    prepare_references,
    prepare_workspace,
)
from tests.evaluation.test_agent_evaluation import event

ERROR = {
    "error_code": "validation_error",
    "status_code": 400,
    "retryable": False,
    "operation": "太乙",
    "error": "所选太乙历史历表仅覆盖推算公历0381-02-11至0386-02-16之前；不向未覆盖年代套用现代农历或回退算法",
}
CASE = {
    "required_any": [["taiyi"]],
    "allowed_tools": ["taiyi"],
    "expected_tool_errors": {"taiyi": ERROR},
    "max_total_calls": {"taiyi": 1},
    "max_successful_calls": {"taiyi": 0},
    "manual_review": ["Still pending; a structured refusal is not a semantic grade."],
}


def rejected(payload=ERROR):
    record = event("taiyi")
    record["item"]["result"] = {"isError": True, "structuredContent": payload}
    return record


def test_registered_refusal_is_not_a_successful_chart_or_an_unexpected_error():
    result = grade_case(CASE, [rejected()], "explain actual refusal", 0)
    assert result["mechanical_checks_passed"]
    assert result["tool_calls"][0]["protocol_error"]
    assert result["tool_calls"][0]["error_response"] == ERROR
    assert not grade_case({"manual_review": []}, [rejected()], "x", 0)[
        "mechanical_checks_passed"
    ]
    assert not grade_case(CASE, [], "x", 0)["mechanical_checks_passed"]
    assert not grade_case(CASE, [event("taiyi")], "x", 0)["mechanical_checks_passed"]


@pytest.mark.parametrize(
    "changes",
    [
        {"error_code": "server_error"},
        {"status_code": 422},
        {"status_code": 400.0},
        {"retryable": 0},
        {"retryable": True},
        {"operation": "different tool"},
        {"error": "other validation cause"},
    ],
)
def test_different_error_or_coerced_type_never_matches(changes):
    actual = {**ERROR, **changes}
    assert not matches_expected_error(actual, ERROR)
    assert not grade_case(CASE, [rejected(actual)], "x", 0)["mechanical_checks_passed"]


@pytest.mark.parametrize(
    "expected",
    [None, {}, {"error_code": "validation_error"}, {**ERROR, "status_code": True}],
)
def test_incomplete_error_declaration_cannot_ignore_failures(expected):
    assert not matches_expected_error(ERROR, expected)


def test_expected_null_still_requires_an_actual_present_field():
    expected = {**ERROR, "extra_context": None}
    assert not matches_expected_error(ERROR, expected)
    assert matches_expected_error({**ERROR, "extra_context": None}, expected)


def test_cli_failed_business_reply_needs_matching_actual_server_capture():
    item = rejected()
    item["item"]["status"] = "failed"
    item["item"]["result"] = {"structured_content": ERROR}
    captured = {
        "event": "tool_call",
        "tool": "taiyi",
        "arguments": item["item"]["arguments"],
        "outcome": "returned",
        "result": {"is_error": True, "structured_content": ERROR},
        "sha256": "actual-verified-journal-record",
    }
    assert not grade_case(CASE, [item], "actual refusal", 0)["mechanical_checks_passed"]
    result = grade_case(CASE, [item], "actual refusal", 0, [captured])
    assert result["mechanical_checks_passed"]
    assert result["tool_calls"][0]["status"] == "failed"
    assert result["tool_calls"][0]["protocol_error"] is False
    assert result["tool_calls"][0]["captured_returned_error"]["is_error"] is True
    for changes in (
        {"arguments": {"different": True}},
        {"outcome": "transport_failed"},
        {"result": {"is_error": False, "structured_content": ERROR}},
        {
            "result": {
                "is_error": True,
                "structured_content": {**ERROR, "status_code": 400.0},
            }
        },
        {"result": {"is_error": True, "structured_content": {**ERROR, "retryable": 0}}},
        {
            "result": {
                "is_error": True,
                "structured_content": {**ERROR, "status_code": 422},
            }
        },
    ):
        assert not grade_case(CASE, [item], "x", 0, [{**captured, **changes}])[
            "mechanical_checks_passed"
        ]
    assert not grade_case({"manual_review": []}, [item], "x", 0, [captured])[
        "mechanical_checks_passed"
    ]


def test_transport_failure_repetition_or_wrong_tools_still_fail():
    bad = rejected()
    bad["item"]["status"] = "failed"
    assert not grade_case(CASE, [bad], "x", 0)["mechanical_checks_passed"]
    bad["item"]["status"] = "completed"
    bad["item"]["error"] = "transport disconnected"
    assert not grade_case(CASE, [bad], "x", 0)["mechanical_checks_passed"]
    assert (
        "repeated_tool_attempt:taiyi"
        in grade_case(CASE, [rejected(), rejected()], "x", 0)["failures"]
    )
    assert not grade_case(CASE, [rejected(), event("sixyao")], "x", 0)[
        "mechanical_checks_passed"
    ]
    assert not grade_case(CASE, [rejected()], "", 0)["mechanical_checks_passed"]


def test_only_structured_or_json_error_codes_are_read_not_guessed_from_prose():
    assert error_response({"content": [{"text": json.dumps(ERROR)}]}) == ERROR
    assert error_response({"content": [{"text": "validation_error occurred"}]}) is None
    assert (
        error_response({"content": [{"text": "not JSON"}, {"text": json.dumps(ERROR)}]})
        == ERROR
    )


def test_runtime_workspace_excludes_new_judge_document_but_keeps_live_guides(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "AGENTS.md").write_text("rules")
    for name in (
        "src/example.py",
        "docs/taiyi-shiji.md",
        "docs/agent-evaluation.md",
    ):
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(
            "runtime" if "agent-evaluation" not in name else "HIDDEN RUBRIC"
        )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepare_workspace(workspace, source)
    assert (workspace / "docs/taiyi-shiji.md").exists()
    assert not (workspace / "docs/agent-evaluation.md").exists()
    assert not (workspace / "tests").exists()


def test_expected_error_reference_is_saved_and_next_real_stdio_case_continues(tmp_path):
    args = {
        "analysis_year": 2026,
        "analysis_month": 7,
        "analysis_day": 1,
        "analysis_hour": 12,
        "analysis_timezone": "+08:00",
        "use_true_solar_time": False,
    }
    cases = [
        {
            **CASE,
            "id": "refused",
            "prompt": "fictional",
            "reference_request": {
                "tool": "taiyi",
                "arguments": {
                    **args,
                    "year_profile": "jinjing_year_historical_table_v1",
                },
            },
        },
        {
            "id": "valid",
            "prompt": "fictional",
            "manual_review": ["pending"],
            "reference_request": {"tool": "taiyi", "arguments": args},
        },
    ]
    references = asyncio.run(prepare_references(cases, tmp_path, ROOT))
    assert [r["reference_status"] for r in references] == [
        "captured_expected_mcp_error",
        "captured_real_mcp",
    ]
    assert references[0]["run_id"] is None and references[1]["run_id"]
    payload = json.loads((tmp_path / "reference-payloads/refused.json").read_text())
    assert payload["is_error"] and payload["structured_content"] == ERROR
    worksheet = json.loads((tmp_path / "review-worksheet.json").read_text())
    assert worksheet["model_invocations"] == 0
    assert all(
        c["model_status"] == "not_run" and c["semantic_status"] == "pending"
        for c in worksheet["cases"]
    )


def test_streamed_snapshot_rejects_source_changes_after_copy(tmp_path, monkeypatch):
    import scripts.evaluate_agent as evaluator

    source = tmp_path / "source"
    source.mkdir()
    for name in ("AGENTS.md", "pyproject.toml", "uv.lock"):
        (source / name).write_text("before")
    original = evaluator.source_manifest
    calls = 0

    def manifests(root, *args):
        nonlocal calls
        calls += 1
        if calls == 2:
            (source / "AGENTS.md").write_text("concurrent change")
        return original(root, *args)

    monkeypatch.setattr(evaluator, "source_manifest", manifests)
    frozen = tmp_path / "frozen"
    with pytest.raises(RuntimeError, match="Source changed"):
        evaluator.freeze_source(frozen, source)
    assert (frozen / "AGENTS.md").read_text() == "before"
    assert (source / "AGENTS.md").read_text() == "concurrent change"


def test_explicit_runtime_snapshot_keeps_execution_and_judge_inputs_not_past_archives(
    tmp_path,
):
    from scripts.evaluate_agent import freeze_source, source_manifest

    source = tmp_path / "source"
    source.mkdir()
    paths = [
        "AGENTS.md",
        "pyproject.toml",
        "uv.lock",
        "src/fatebridge/engine.py",
        "src/fatebridge/data/rules.json",
        "docs/contracts/taiyi.json",
        "docs/taiyi-shiji.md",
        "scripts/evaluate_agent.py",
        "docs/validation/past/model-raw/source/src/past.py",
    ]
    for name in paths:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    manifest = freeze_source(tmp_path / "runtime", source, "runtime")
    assert set(manifest) == set(paths[:-1])
    assert source_manifest(tmp_path / "runtime") == manifest
    assert set(freeze_source(tmp_path / "full", source)) == set(paths)
    assert (source / paths[-1]).exists()
