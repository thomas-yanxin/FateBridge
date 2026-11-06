"""Typed interface for the current observable-call evaluator."""

import subprocess as subprocess
from pathlib import Path
from typing import Any, Iterator, Literal

from fatebridge.validation.evaluation_environment import NativeSelection

Case = dict[str, Any]
Event = dict[str, Any]
Grade = dict[str, Any]

ROOT: Path
CASES: Path
EVALUATION_DOCS_EXCLUDED: set[str]
GRADING_POLICY: Literal["observed_calls_and_declared_errors_v2"]

def source_files(
    root: Path = ..., profile: str = ..., extra_files: tuple[str, ...] = ...
) -> list[Path]: ...
def source_manifest(
    root: Path = ..., profile: str = ..., extra_files: tuple[str, ...] = ...
) -> dict[str, str]: ...
def freeze_source(
    target: Path,
    root: Path = ...,
    profile: str = ...,
    extra_files: tuple[str, ...] = ...,
) -> dict[str, str]: ...
def walk(value: Any) -> Iterator[dict[str, Any]]: ...
def observations(events: list[Event]) -> tuple[list[Event], list[str]]: ...
def error_response(result: dict[str, Any]) -> dict[str, Any] | None: ...
def matches_expected_error(actual: Any, expected: Any) -> bool: ...
def expected_error_call(call: Event, expected: Any) -> bool: ...
def grade_case(
    case: Case,
    events: list[Event],
    final: str,
    returncode: int,
    captured_tool_records: list[Event] | None = ...,
) -> Grade: ...
def _same_argument_path(
    arguments: dict[str, Any], path: str, expected: Any
) -> bool: ...
def _without_evaluation_private_sections(text: str) -> str: ...
def prepare_workspace(workspace: Path, source: Path = ...) -> None: ...
def prepare_case_workspace(workspace: Path, source: Path, case: Case) -> None: ...
def command_for(
    cli: str,
    workspace: Path,
    output: Path,
    case: Case,
    model: str | None = ...,
    backend_source: Path | None = ...,
    native_selection: NativeSelection | None = ...,
    native_working_directory: Path | None = ...,
) -> list[str]: ...
def run_case(
    cli: str,
    case: Case,
    output: Path,
    timeout: int,
    model: str | None = ...,
    source: Path = ...,
    native_selection: NativeSelection | None = ...,
    native_working_directory: Path | None = ...,
) -> Grade: ...
def model_prompt(case: Case) -> str: ...
async def prepare_references(
    cases: list[Case],
    output: Path,
    source: Path,
    native_selection: NativeSelection | None = ...,
    native_working_directory: Path | None = ...,
) -> list[dict[str, Any]]: ...
def main() -> int: ...
