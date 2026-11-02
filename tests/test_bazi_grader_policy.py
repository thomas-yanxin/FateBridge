"""The old judge must execute unchanged, not merely keep an unchanged facade."""

import ast
from copy import deepcopy
from functools import wraps

import pytest

from scripts import evaluate_agent as evaluator
from scripts.audit_bazi_grader_policy import (
    FIXTURE,
    ROOT,
    audit,
    check_source_identity,
    historical_grades,
    load_inputs,
)


@pytest.fixture(scope="module")
def replay():
    return audit()


def test_first_failed_guard_and_original_guard_file_are_retained(replay):
    first = (FIXTURE / "pytest-before-first-failure.log").read_text()
    assert "1 failed, 42 passed" in first
    assert "test_existing_scorer_and_argument_comparison_logic_are_unchanged" in first
    assert all(replay["source_identity"].values())


def test_all33_full_grades_match_frozen_function_and_original_reports(replay):
    assert replay["historical_case_count"] == 33
    assert replay["historical_pass_counts"] == [10, 10, 11]
    assert all(
        r["full_original_grade_fields_identical"] for r in replay["historical_cases"]
    )
    failures = [
        r
        for r in replay["historical_cases"]
        if not r["original_grade"]["mechanical_checks_passed"]
    ]
    assert len(failures) == 2
    assert "missing_tool:bazi_birth" in failures[0]["original_grade"]["failures"]
    assert replay["actual_model_executions"] == 0
    assert replay["new_interpretation_fidelity_credit"] == 0
    assert replay["real_world_predictive_validity"] == "not_tested"
    assert not replay["full_goal_complete"]


def test_actual_driver_keeps_full_denominator_and_selects_the_declared_policy(replay):
    controls = {r["case"]: r for r in replay["driver_controls"]}
    assert len(controls) == replay["driver_control_count"] == 10
    assert sum(r["expected_mechanical_pass"] for r in controls.values()) == 3
    for row in controls.values():
        assert (
            row["actual_record"]["mechanical_checks_passed"]
            is row["expected_mechanical_pass"]
        )
        assert set(row["actual_driver_grading_routes"]) == {
            row["actual_record"]["grading_policy"]
        }
    for key in [
        "legacy_success",
        "legacy_original_wrong_tool",
        "legacy_recovered_failure",
        "legacy_cannot_use_refusal_exception",
    ]:
        record = controls[key]["actual_record"]
        assert record["grading_policy"] == evaluator.LEGACY_GRADING_POLICY
        assert all("error_response" not in c for c in record["tool_calls"])
    assert (
        "capture_event_mismatch"
        in controls["legacy_capture_mismatch"]["actual_record"]["failures"]
    )
    assert (
        "unrecovered_tool_failure"
        in controls["legacy_cannot_use_refusal_exception"]["actual_record"]["failures"]
    )
    assert (
        "repeated_tool_attempt:taiyi"
        in controls["repeated_attempt"]["actual_record"]["failures"]
    )
    refused = controls["declared_refusal"]["actual_record"]["tool_calls"][0]
    assert refused["status"] == "failed" and refused["protocol_error"] is False
    assert refused["captured_returned_error"]["is_error"] is True


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"capture_payloads": True},
        {"grading_policy": "expected_errors_v1"},
        {"mechanical_checks_passed": True},
    ],
)
def test_response_or_output_policy_labels_cannot_opt_in_an_old_case(extra):
    assert evaluator.scoring_policy(extra) == evaluator.LEGACY_GRADING_POLICY


def test_runtime_wrapper_with_the_original_name_is_rejected(monkeypatch):
    _, before, legacy = load_inputs()
    original = evaluator.grade

    @wraps(original)
    def wrapped(*args, **kwargs):
        return original(*args, **kwargs)

    monkeypatch.setattr(evaluator, "grade", wrapped)
    with pytest.raises(ValueError, match="alias or wrapper"):
        check_source_identity(before, legacy)


def test_equal_pass_counts_cannot_hide_changed_call_facts(monkeypatch):
    _, _, legacy = load_inputs()
    original = evaluator.grade_case

    def altered(*args, **kwargs):
        result = deepcopy(original(*args, **kwargs))
        result["tool_calls"][0]["error_response"] = None
        return result

    monkeypatch.setattr(evaluator, "grade_case", altered)
    with pytest.raises(ValueError, match="Full historical grading result changed"):
        historical_grades(legacy)


def test_another_function_named_grade_cannot_replace_the_frozen_runtime(monkeypatch):
    _, before, legacy = load_inputs()
    namespace = {}
    exec("def grade(case, events, final, returncode): return {}", namespace)
    monkeypatch.setattr(evaluator, "grade", namespace["grade"])
    with pytest.raises(ValueError, match="source location"):
        check_source_identity(before, legacy)


def test_refusal_assertion_edits_cannot_be_disguised_as_an_api_rename():
    _, before, legacy = load_inputs()
    tree = ast.parse(before["tests/test_agent_expected_errors.py"])
    target = next(n for n in ast.walk(tree) if isinstance(n, ast.Assert))
    target.test = ast.Constant(value=True)
    before["tests/test_agent_expected_errors.py"] = ast.unparse(tree)
    with pytest.raises(ValueError, match="assertions or case values changed"):
        check_source_identity(before, legacy)


def test_typed_interface_freezes_the_actual_parameter_names_without_changing_bodies():
    runtime = ast.parse((ROOT / "scripts/evaluate_agent.py").read_text())
    interface = ast.parse((ROOT / "scripts/evaluate_agent.pyi").read_text())
    functions = {
        n.name: n
        for n in runtime.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    declarations = {
        n.name: n
        for n in interface.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert functions.keys() == declarations.keys()
    for name, function in functions.items():
        declared = declarations[name]
        assert type(function) is type(declared)
        assert [a.arg for a in function.args.args] == [
            a.arg for a in declared.args.args
        ]
        assert len(function.args.defaults) == len(declared.args.defaults)
        assert not function.args.posonlyargs and not declared.args.posonlyargs
        assert not function.args.kwonlyargs and not declared.args.kwonlyargs
    assert len(declarations["grade"].args.args) == 4
    assert len(declarations["grade_expected_errors"].args.args) == 5


def test_new_judge_document_is_kept_for_review_but_not_given_to_the_examinee(tmp_path):
    source, workspace = tmp_path / "source", tmp_path / "workspace"
    source.mkdir()
    workspace.mkdir()
    for name, text in {
        "AGENTS.md": "runtime rules",
        "src/example.py": "runtime",
        "skills/onda-zige/SKILL.md": "runtime guide",
        "docs/bazi-assessment.md": "runtime calculation explanation",
        "docs/bazi-grader-policy-audit.md": "HIDDEN GRADING HISTORY",
    }.items():
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    evaluator.prepare_workspace(workspace, source)
    assert (
        source / "docs/bazi-grader-policy-audit.md"
    ).read_text() == "HIDDEN GRADING HISTORY"
    assert not (workspace / "docs/bazi-grader-policy-audit.md").exists()
    assert (workspace / "docs/bazi-assessment.md").exists()
