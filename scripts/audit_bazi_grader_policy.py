"""Preserve historical grades and verify real driver routing without a model."""

from __future__ import annotations

import argparse
import ast
import asyncio
import gzip
import hashlib
import json
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Callable, cast
from unittest.mock import patch

from scripts import evaluate_agent as evaluator

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_grader_policy_v1"
LEGACY_FUNCTIONS = {"grade", "observations", "_same_argument_path"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[dict[str, Any], dict[str, str], str]:
    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    if (
        digest(FIXTURE / "protocol.json")
        != (FIXTURE / "protocol.sha256").read_text().strip()
    ):
        raise ValueError("Original policy protocol changed")
    archive = FIXTURE / "before-source.json.gz"
    if digest(archive) != protocol["before_source_archive_sha256"]:
        raise ValueError("Before source changed")
    before = json.loads(gzip.decompress(archive.read_bytes()))
    for name, expected in protocol["before_files_sha256"].items():
        if hashlib.sha256(before[name].encode()).hexdigest() != expected:
            raise ValueError("Before source entry changed: " + name)
    legacy = FIXTURE / "legacy-evaluate-agent.py.txt"
    if digest(legacy) != protocol["legacy_evaluator_sha256"]:
        raise ValueError("Original evaluator source changed")
    for name, expected in protocol["original_batch_references_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Historical batch archive changed: " + name)
    return protocol, before, legacy.read_text()


def function_asts(text: str) -> dict[str, str]:
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(text).body
        if isinstance(node, ast.FunctionDef)
    }


def check_source_identity(before: dict[str, str], legacy: str) -> dict[str, Any]:
    current = (ROOT / "scripts/evaluate_agent.py").read_text()
    original = function_asts(legacy)
    functions = function_asts(current)
    for name in LEGACY_FUNCTIONS:
        if original[name] != functions[name]:
            raise ValueError("Historical grader AST changed: " + name)
    guard = "tests/test_bazi_first_model_grades.py"
    if (ROOT / guard).read_text() != before[guard]:
        raise ValueError("Original grader guard test changed")
    if (
        evaluator.grade.__name__ != "grade"
        or evaluator.grade.__code__.co_name != "grade"
    ):
        raise ValueError("Original function was replaced by an alias or wrapper")
    if evaluator.observations.__code__.co_name != "observations":
        raise ValueError("Original observations was replaced")
    runtime_nodes = {
        n.name: n for n in ast.parse(current).body if isinstance(n, ast.FunctionDef)
    }
    for name in LEGACY_FUNCTIONS:
        code = getattr(evaluator, name).__code__
        if (
            Path(code.co_filename).resolve()
            != (ROOT / "scripts/evaluate_agent.py").resolve()
            or code.co_firstlineno != runtime_nodes[name].lineno
        ):
            raise ValueError(
                "Historical runtime function does not match source location: " + name
            )

    class NormalizeExtendedName(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            if node.name == "grade_expected_errors":
                node.name = "grade"
            if node.name == "observations_expected_errors":
                node.name = "observations"
            return self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == "observations_expected_errors":
                node.id = "observations"
            return node

    normalized = NormalizeExtendedName().visit(ast.parse(current))
    extended = {
        n.name: ast.dump(n, include_attributes=False)
        for n in cast(ast.Module, normalized).body
        if isinstance(n, ast.FunctionDef)
    }
    prior = function_asts(before["scripts/evaluate_agent.py"])
    for name in ("grade", "observations"):
        # Last duplicate in this normalized AST is the separately named extension.
        if extended[name] != prior[name]:
            raise ValueError("Pre-existing refusal policy changed: " + name)

    class NormalizeTestCalls(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == "grade":
                node.id = "grade_expected_errors"
            return node

        def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
            if node.module == "scripts.evaluate_agent":
                for item in node.names:
                    if item.name == "grade":
                        item.name = "grade_expected_errors"
            return node

    test = "tests/test_agent_expected_errors.py"
    normalized_test = NormalizeTestCalls().visit(ast.parse(before[test]))
    if ast.dump(normalized_test, include_attributes=False) != ast.dump(
        ast.parse((ROOT / test).read_text()), include_attributes=False
    ):
        raise ValueError("Pre-existing refusal test assertions or case values changed")
    return dict(
        original_function_asts_identical=True,
        original_guard_file_unchanged=True,
        legacy_runtime_is_unwrapped_function=True,
        preexisting_refusal_policy_ast_identical_except_names=True,
        preexisting_refusal_tests_identical_except_explicit_api_names=True,
    )


def historical_grades(legacy: str) -> list[dict[str, Any]]:
    nodes: list[ast.stmt] = [
        n
        for n in ast.parse(legacy).body
        if isinstance(n, ast.FunctionDef) and n.name in LEGACY_FUNCTIONS | {"walk"}
    ]
    namespace: dict[str, Any] = {"datetime": datetime}
    exec(
        compile(
            ast.Module(body=nodes, type_ignores=[]), "frozen-first-grader.py", "exec"
        ),
        namespace,
    )
    original_grade = cast(Callable[..., dict[str, Any]], namespace["grade"])
    rows = []
    for version in (1, 2, 3):
        folder = ROOT / f"tests/fixtures/bazi_semantic_run_v{version}"
        cases = json.loads((folder / "case-dataset.json").read_text())["cases"]
        report = json.loads((folder / "report.json").read_text())["cases"]
        for case, receipt in zip(cases, report, strict=True):
            if evaluator.scoring_policy(case) != evaluator.LEGACY_GRADING_POLICY:
                raise ValueError("Historical case opted into a new policy")
            target = folder / case["id"]
            events = [
                json.loads(line)
                for line in (target / "events.jsonl").read_text().splitlines()
            ]
            answer = (target / "answer.txt").read_text()
            original = original_grade(case, events, answer, receipt["exit_code"])
            current = evaluator.grade_case(case, events, answer, receipt["exit_code"])
            if current != original or any(
                receipt[key] != value for key, value in original.items()
            ):
                raise ValueError(
                    "Full historical grading result changed: " + case["id"]
                )
            rows.append(
                dict(
                    version=version,
                    case=case["id"],
                    case_dataset_sha256=digest(folder / "case-dataset.json"),
                    original_report_sha256=digest(folder / "report.json"),
                    events_sha256=digest(target / "events.jsonl"),
                    answer_sha256=digest(target / "answer.txt"),
                    grading_policy=evaluator.scoring_policy(case),
                    original_grade=original,
                    current_grade=current,
                    full_original_grade_fields_identical=True,
                )
            )
    if len(rows) != 33:
        raise ValueError("The complete three batches must remain in the denominator")
    return rows


def event(
    tool: str, *, status: str = "completed", failure: dict[str, Any] | None = None
) -> dict[str, Any]:
    item: dict[str, Any] = dict(
        type="mcp_tool_call",
        server="fatebridge",
        tool=tool,
        arguments={"birth_hour": 10},
        status=status,
    )
    if failure is not None:
        item["result"] = {"structured_content": failure}
    return {"type": "item.completed", "item": item}


def driver_controls() -> list[dict[str, Any]]:
    """Exercise actual run_case with declared synthetic CLI/journal fixtures.

    These are control-flow tests, neither independent server observations nor
    model outputs. Actual server/capture integration has separate existing tests.
    """
    from fatebridge.validation.agent_capture import CaptureJournal

    refusal = dict(
        error_code="validation_error",
        status_code=400,
        retryable=False,
        operation="太乙",
        error="synthetic_frozen_refusal",
    )
    base = dict(
        prompt="Fictional offline control-flow fixture; no model.",
        manual_review=["pending"],
        capture_payloads=True,
        required_any=[["bazi_birth"]],
        allowed_tools=["bazi_birth"],
        arguments={"bazi_birth": {"birth_hour": 10}},
    )
    expected = dict(
        base,
        required_any=[["taiyi"]],
        allowed_tools=["taiyi"],
        arguments={"taiyi": {"birth_hour": 10}},
        expected_tool_errors={"taiyi": refusal},
        max_total_calls={"taiyi": 1},
        max_successful_calls={"taiyi": 0},
    )
    success = event("bazi_birth")
    error = event("bazi_birth", status="failed", failure=refusal)
    refused = event("taiyi", status="failed", failure=refusal)
    wrong = event("taiyi", status="failed", failure={**refusal, "status_code": 422})
    controls = [
        ("legacy_success", base, [success], True, None),
        ("legacy_original_wrong_tool", base, [event("analyze_destiny")], False, None),
        ("legacy_uncaptured_failure", base, [error], False, None),
        ("legacy_recovered_failure", base, [error, success], True, None),
        ("legacy_capture_mismatch", base, [success], False, "mismatch"),
        ("declared_refusal", expected, [refused], True, None),
        ("wrong_error", expected, [wrong], False, None),
        ("missing_capture", expected, [refused], False, "missing"),
        ("repeated_attempt", expected, [refused, refused], False, None),
        (
            "legacy_cannot_use_refusal_exception",
            {
                k: v
                for k, v in expected.items()
                if k not in {"expected_tool_errors", "max_total_calls"}
            },
            [refused],
            False,
            None,
        ),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix="bazi-grader-controls-") as directory:
        output = Path(directory)
        for name, definition, events, wanted, mode in controls:
            case = {**deepcopy(definition), "id": name}
            captured: list[dict[str, Any]] = []
            route: list[str] = []
            legacy_grade, extended_grade = (
                evaluator.grade,
                evaluator.grade_expected_errors,
            )

            def legacy_call(*args: Any, **kwargs: Any) -> Any:
                route.append(evaluator.LEGACY_GRADING_POLICY)
                return legacy_grade(*args, **kwargs)

            def extended_call(*args: Any, **kwargs: Any) -> Any:
                route.append(evaluator.EXPECTED_ERRORS_GRADING_POLICY)
                return extended_grade(*args, **kwargs)

            def synthetic_cli(*args: Any, **kwargs: Any) -> CompletedProcess[str]:
                target = output / name
                (target / "answer.txt").write_text(
                    "Synthetic control-flow fixture, not a model answer."
                )
                for entry in events:
                    kwargs["stdout"].write(json.dumps(entry) + "\n")
                if mode != "missing":
                    journal = CaptureJournal(target / "mcp-calls.jsonl")
                    try:
                        for entry in events:
                            item = entry["item"]
                            result = item.get("result") or {}
                            captured.append(
                                dict(
                                    event="tool_call",
                                    tool=item["tool"],
                                    arguments=(
                                        {"birth_hour": 11}
                                        if mode == "mismatch"
                                        else item["arguments"]
                                    ),
                                    outcome="returned",
                                    result=dict(
                                        is_error=bool(result),
                                        structured_content=result.get(
                                            "structured_content",
                                            {"synthetic_success": True},
                                        ),
                                    ),
                                )
                            )
                            asyncio.run(journal.append(captured[-1]))
                    finally:
                        journal.close()
                return CompletedProcess(args[0], 0)

            with (
                patch.object(evaluator, "prepare_workspace"),
                patch.object(
                    evaluator, "command_for", return_value=["synthetic_cli_no_model"]
                ),
                patch.object(evaluator.subprocess, "run", side_effect=synthetic_cli),
                patch.object(evaluator, "grade", side_effect=legacy_call),
                patch.object(
                    evaluator, "grade_expected_errors", side_effect=extended_call
                ),
            ):
                result = evaluator.run_case("synthetic_cli_no_model", case, output, 1)
            if result["mechanical_checks_passed"] is not wanted or set(route) != {
                evaluator.scoring_policy(case)
            }:
                raise ValueError("Actual driver routed or graded incorrectly: " + name)
            rows.append(
                dict(
                    case=name,
                    scope="Synthetic CLI and journal fixtures in actual run_case; no model or independent server observation",
                    case_definition=case,
                    events=events,
                    synthetic_capture_records=captured,
                    actual_driver_grading_routes=route,
                    expected_mechanical_pass=wanted,
                    actual_record=result,
                )
            )
    return rows


def audit() -> dict[str, Any]:
    protocol, before, legacy = load_inputs()
    identity = check_source_identity(before, legacy)
    rows = historical_grades(legacy)
    controls = driver_controls()
    return dict(
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=digest(FIXTURE / "protocol.json"),
        current_evaluator_sha256=digest(ROOT / "scripts/evaluate_agent.py"),
        source_identity=identity,
        historical_case_count=len(rows),
        historical_cases=rows,
        historical_pass_counts=[
            sum(
                row["original_grade"]["mechanical_checks_passed"]
                for row in rows
                if row["version"] == v
            )
            for v in (1, 2, 3)
        ],
        driver_control_count=len(controls),
        driver_controls=controls,
        scoring_thresholds_changed=False,
        original_guard_changed=False,
        actual_model_executions=0,
        new_interpretation_fidelity_credit=0,
        independent_semantic_acceptance="not_completed",
        real_world_predictive_validity="not_tested",
        full_goal_complete=False,
        overall_score=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or Path(str(output) + ".sha256").exists():
        raise SystemExit("Preserve existing first results")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    Path(str(output) + ".sha256").write_text(digest(output) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "historical_case_count",
                    "historical_pass_counts",
                    "driver_control_count",
                    "actual_model_executions",
                    "full_goal_complete",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
