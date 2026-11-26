"""Typed interface for the current observable-call evaluator."""

import subprocess as subprocess
from pathlib import Path

from pydantic import JsonValue

from validation.agent_grading import GRADING_POLICY as GRADING_POLICY
from validation.agent_grading import _same_argument_path as _same_argument_path
from validation.agent_grading import error_response as error_response
from validation.agent_grading import expected_error_call as expected_error_call
from validation.agent_grading import grade_case as grade_case
from validation.agent_grading import matches_expected_error as matches_expected_error
from validation.agent_grading import observations as observations
from validation.agent_grading import walk as walk
from validation.evaluation_environment import NativeSelection

Case = dict[str, JsonValue]
RunRecord = dict[str, JsonValue]

ROOT: Path
EVALUATION_DOCS_EXCLUDED: set[str]

def source_files(
    root: Path = ..., *, extra_files: tuple[str, ...] = ...
) -> list[Path]: ...
def source_manifest(
    root: Path = ..., *, extra_files: tuple[str, ...] = ...
) -> dict[str, str]: ...
def freeze_source(
    target: Path,
    root: Path = ...,
    *,
    extra_files: tuple[str, ...] = ...,
) -> dict[str, str]: ...
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
) -> RunRecord: ...
def model_prompt(case: Case) -> str: ...
async def prepare_references(
    cases: list[Case],
    output: Path,
    source: Path,
    native_selection: NativeSelection | None = ...,
    native_working_directory: Path | None = ...,
) -> list[dict[str, JsonValue]]: ...
def main() -> int: ...
