"""Run isolated Codex conversations and grade observable tool behavior.

Requires an authenticated Codex CLI. No API key, user config edits, or pytest-time
model calls. Each case uses a new temporary workspace and the current interpreter's
real stdio MCP. The CLI default model is used unless --model is explicitly passed.
"""

import sys as _sys
from pathlib import Path as _Path

_VAL_REPO_ROOT = _Path(__file__).resolve().parents[1]
if str(_VAL_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_VAL_REPO_ROOT))
else:
    pass


import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import fastmcp
import fastmcp.client.transports
from pydantic import JsonValue

from fatebridge.diagnostics import resolve_codex_cli
from validation.agent_capture import read_capture
from validation.agent_grading import GRADING_POLICY as GRADING_POLICY
from validation.agent_grading import _same_argument_path as _same_argument_path
from validation.agent_grading import error_response as error_response
from validation.agent_grading import expected_error_call as expected_error_call
from validation.agent_grading import grade_case as grade_case
from validation.agent_grading import matches_expected_error as matches_expected_error
from validation.agent_grading import observations as observations
from validation.agent_grading import walk as walk
from validation.evaluation_assets import (
    copy_case_evidence,
    evidence_source_files,
    prepare_evidence_workspace,
    resolve_source,
)
from validation.evaluation_environment import (
    NativeSelection,
    capture_selection,
    context_bytes,
    execution_directory,
    load_selection,
    process_environment,
    selected_environment,
)
from validation.external_evaluation import (
    LAYERS,
    evaluation_summary,
    freeze_external_selection,
    load_external_suite,
    load_frozen_selection,
)

ROOT = Path(__file__).resolve().parents[1]
_LOCAL_DOC_DIRS = {"validation", "reviews", "plans", "superpowers"}


def source_files(root: Path = ROOT, *, extra_files: tuple[str, ...] = ()) -> list[Path]:
    selected = [root / name for name in ("AGENTS.md", "pyproject.toml", "uv.lock")]
    for name in (
        "scripts/evaluate_agent.py",
        "scripts/evaluate_agent.pyi",
        "scripts/evaluation/build_mingli_evaluation.py",
        "scripts/evaluation/audit_mingli_evaluation.py",
    ):
        path = root / name
        if path.is_file():
            selected.append(path)
        else:
            pass
    docs = root / "docs"
    for folder in (docs, root / "src", root / "validation"):
        if not folder.exists():
            continue
        else:
            pass
        for current, directories, files in os.walk(folder):
            directory = Path(current)
            excluded = {"__pycache__"}
            if directory == docs:
                excluded.update(_LOCAL_DOC_DIRS)
            else:
                pass
            directories[:] = [name for name in directories if name not in excluded]
            selected.extend(
                directory / name
                for name in files
                if not name.endswith((".pyc", ".pyo", ".log"))
                and name != ".DS_Store"
                and (directory / name).is_file()
            )
    for relative in extra_files:
        path = resolve_source(root, relative)
        if path not in selected:
            selected.append(path)
        else:
            pass
    return sorted(selected)


def source_manifest(
    root: Path = ROOT, *, extra_files: tuple[str, ...] = ()
) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_files(root, extra_files=extra_files)
    }


def freeze_source(
    target: Path, root: Path = ROOT, *, extra_files: tuple[str, ...] = ()
) -> dict[str, str]:
    """Freeze one batch's instructions and executable backend, including dirty work."""
    manifest = source_manifest(root, extra_files=extra_files)
    # Before/copy/after hashes retain the same fail-closed consistency rule.
    for name, expected in manifest.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(
                "Source changed while snapshotting; retry the evaluation"
            )
        else:
            pass
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    after = source_manifest(root, extra_files=extra_files)
    frozen = source_manifest(target, extra_files=extra_files)
    if after != manifest or frozen != manifest:
        raise RuntimeError("Source changed while snapshotting; retry the evaluation")
    else:
        pass
    return manifest


# Keep evaluator descriptions in the source snapshot for the reviewer only.
EVALUATION_DOCS_EXCLUDED = _LOCAL_DOC_DIRS | {
    "agent-evaluation.md",
    "liuren-jinkou-audit.md",
    "mingli-bench-evaluation.md",
}


def prepare_workspace(workspace: Path, source: Path = ROOT) -> None:
    shutil.copy2(source / "AGENTS.md", workspace / "AGENTS.md")
    shutil.copytree(source / "src", workspace / "src")
    shutil.copytree(
        source / "docs",
        workspace / "docs",
        ignore=lambda _directory, names: set(names) & EVALUATION_DOCS_EXCLUDED,
    )
    with (workspace / "AGENTS.md").open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## 验收环境\n"
            "仅使用本目录资料、MCP 结果交付文件与 FateBridge 只读工具，直接完成用户请求。"
            "不安装、修改配置、写源文件、访问其他服务或向别人发送消息。\n"
        )


def prepare_case_workspace(
    workspace: Path, source: Path, case: dict[str, JsonValue]
) -> None:
    mode = case.get("evidence_only_workspace", False)
    if type(mode) is not bool:
        raise ValueError("evidence_only_workspace must be a boolean")
    else:
        pass
    if mode:
        if not case.get("evidence_files"):
            raise ValueError("Evidence-only workspaces require declared evidence")
        else:
            pass
        prepare_evidence_workspace(workspace, source)
    else:
        prepare_workspace(workspace, source)


def command_for(
    cli: str,
    workspace: Path,
    output: Path,
    case: dict[str, JsonValue],
    model: str | None = None,
    backend_source: Path | None = None,
    native_selection: NativeSelection | None = None,
    native_working_directory: Path | None = None,
) -> list[str]:
    if case.get("evidence_only_workspace") and backend_source is None:
        raise ValueError("Evidence-only models require a separate frozen MCP backend")
    else:
        pass
    backend = backend_source or workspace
    command = [
        cli,
        "exec",
        "--ephemeral",
        "--strict-config",
        "--ignore-user-config",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--json",
        "--color",
        "never",
        "-C",
        str(workspace),
        "-o",
        str(output / "answer.txt"),
        "-c",
        'approval_policy="never"',
        "--disable",
        "apps",
        "--disable",
        "plugins",
    ]
    # Ignore unrelated configured connectors; authentication stays in CODEX_HOME.
    settings = {
        # A required calculation server must finish initializing before the
        # initial tool catalog; optional servers may miss the 1s grace window.
        "mcp_servers.fatebridge.required": True,
        "mcp_servers.fatebridge.command": sys.executable,
        "mcp_servers.fatebridge.args": ["-X", "utf8", "-m", "fatebridge.mcp_server"],
        "mcp_servers.fatebridge.env.FATEBRIDGE_MCP_FAMILIES": "",
        "mcp_servers.fatebridge.env.PYTHONPATH": str(backend / "src"),
    }
    # Codex MCP servers need explicit non-default data selection. Preserve the
    # operator's backend/cache choice without forwarding credentials or the
    # rest of the evaluator environment. Actual return flags remain evidence.
    for name, value in selected_environment(native_selection).items():
        settings["mcp_servers.fatebridge.env." + name] = value
    if case.get("capture_payloads"):
        settings["mcp_servers.fatebridge.args"] = [
            "-X",
            "utf8",
            "-m",
            "validation.agent_capture",
        ]
        settings["mcp_servers.fatebridge.env.PYTHONPATH"] = os.pathsep.join(
            [str(backend), str(backend / "src")]
        )
        settings["mcp_servers.fatebridge.env.FATEBRIDGE_EVALUATION_LOG"] = str(
            output / "mcp-calls.jsonl"
        )
    else:
        pass
    if native_working_directory is not None:
        settings["mcp_servers.fatebridge.cwd"] = str(native_working_directory)
        # Script mode keeps Python's initial import path in the frozen source.
        # With -m, an unrelated fatebridge/sitecustomize in the native data cwd
        # could shadow the declared PYTHONPATH before our code starts. This
        # also works on Python3.10, which has no -P switch.
        entry = (
            "validation/agent_capture.py"
            if case.get("capture_payloads")
            else "src/fatebridge/mcp_server.py"
        )
        settings["mcp_servers.fatebridge.args"] = [
            "-X",
            "utf8",
            str((backend / entry).absolute()),
        ]
    else:
        pass
    for key, value in settings.items():
        command.extend(["-c", key + "=" + json.dumps(value, ensure_ascii=False)])
    if model:
        command.extend(["--model", model])
    else:
        pass
    command.append("-")
    return command


def run_case(
    cli: str,
    case: dict[str, JsonValue],
    output: Path,
    timeout: int,
    model: str | None = None,
    source: Path = ROOT,
    native_selection: NativeSelection | None = None,
    native_working_directory: Path | None = None,
) -> dict[str, JsonValue]:
    native_selection = (
        capture_selection() if native_selection is None else native_selection
    )
    target = output / case["id"]
    target.mkdir()
    prompt = model_prompt(case)
    (target / "model-prompt.txt").write_text(prompt, encoding="utf-8")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="fatebridge-agent-eval-") as directory:
        workspace = Path(directory)
        prepare_case_workspace(workspace, source, case)
        evidence = copy_case_evidence(workspace, case, source)
        if evidence:
            (target / "evidence-files.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            pass
        backend_source = (
            source
            if case.get("evidence_only_workspace") or case.get("capture_payloads")
            else None
        )
        command = command_for(
            cli,
            workspace,
            target,
            case,
            model,
            backend_source,
            native_selection,
            native_working_directory,
        )
        with (
            (target / "events.jsonl").open("w", encoding="utf-8") as stdout,
            (target / "stderr.log").open("w", encoding="utf-8") as stderr,
        ):
            try:
                result = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=timeout,
                    env=process_environment(native_selection),
                )
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
    events = []
    for line in (target / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    answer = target / "answer.txt"
    final = answer.read_text(encoding="utf-8") if answer.exists() else ""
    record = {
        "case": case["id"],
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "exit_code": code,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "grading_policy": GRADING_POLICY,
        **grade_case(case, events, final, code),
    }
    if "evaluation_layer" in case:
        record.update(
            evaluation_layer=case["evaluation_layer"],
            split=case["split"],
            source_case_id=case["source_case_id"],
            semantic_status="pending",
        )
    else:
        pass
    if evidence:
        record["evidence_files"] = evidence
    else:
        pass
    if case.get("capture_payloads"):
        try:
            captured = read_capture(target / "mcp-calls.jsonl")
            tool_records = [r for r in captured if r["event"] == "tool_call"]
            calls, _ = observations(events)
            own = [c for c in calls if c["server"] == "fatebridge"]
            record["capture"] = {
                "journal_sha256": hashlib.sha256(
                    (target / "mcp-calls.jsonl").read_bytes()
                ).hexdigest(),
                "tool_calls": len(tool_records),
                "resource_reads": sum(r["event"] == "resource_read" for r in captured),
                "tool_lists": sum(r["event"] == "tool_list" for r in captured),
                "advertised_tools": sorted(
                    {
                        name
                        for r in captured
                        if r["event"] == "tool_list"
                        for name in r["tool_names"]
                    }
                ),
                "scope": "Actual server replies, not a separately recalculated reference",
            }
            observed = sorted(
                json.dumps([c["tool"], c["arguments"]], sort_keys=True) for c in own
            )
            recorded = sorted(
                json.dumps([r["tool"], r["arguments"]], sort_keys=True)
                for r in tool_records
            )
            if observed != recorded:
                record["failures"].append("capture_event_mismatch")
            else:
                record.update(
                    grade_case(
                        case, events, final, code, captured_tool_records=tool_records
                    )
                )
        except (OSError, ValueError, KeyError, TypeError):
            record["failures"].append("missing_or_invalid_mcp_capture")
        record["mechanical_checks_passed"] = not record["failures"]
    else:
        pass
    (target / "grade.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def model_prompt(case: dict[str, JsonValue]) -> str:
    """Expose the operational tool contract, never hidden answer criteria.

    Earlier runs graded allowed_tools without telling the model about that
    restriction. Keep those failures; enforce the same contract prospectively.
    """
    allowed = case.get("allowed_tools")
    if allowed is None:
        return case["prompt"]
    else:
        pass
    if allowed == []:
        return (
            "本次运行的工具合同：不调用任何 FateBridge 工具。"
            "请按适用技能核对已确认资料并直接回应当前请求。\n\n" + case["prompt"]
        )
    else:
        pass
    return (
        "本次运行通过 run_calculation 调用能力，tool 只能选 "
        + "、".join(allowed)
        + "。按需用 discover_capabilities 或 describe_capability 核对合同，"
        + "用 read_result 读取同次计算的结果。仍按适用技能核对输入和实际回执。\n\n"
        + case["prompt"]
    )


async def prepare_references(
    cases: list[dict[str, JsonValue]],
    output: Path,
    source: Path,
    native_selection: NativeSelection | None = None,
    native_working_directory: Path | None = None,
) -> list[dict[str, JsonValue]]:
    """Call real MCP tools only; do not start a model or grade any answer."""
    target = output / "reference-payloads"
    target.mkdir()
    prompts = output / "model-prompts"
    prompts.mkdir()
    transport = fastmcp.client.transports.StdioTransport(
        command=sys.executable,
        args=(
            ["-X", "utf8", "-m", "validation.agent_capture"]
            if native_working_directory is None
            else [
                "-X",
                "utf8",
                str((source / "validation/agent_capture.py").absolute()),
            ]
        ),
        cwd=str(
            source if native_working_directory is None else native_working_directory
        ),
        env={
            **selected_environment(native_selection),
            "PYTHONPATH": os.pathsep.join([str(source), str(source / "src")]),
            "FATEBRIDGE_EVALUATION_LOG": str(output / "reference-mcp.jsonl"),
            "FATEBRIDGE_MCP_FAMILIES": "",
        },
        log_file=output / "reference-mcp-stderr.log",
    )
    references = []
    worksheet = []
    async with fastmcp.Client(transport) as client:
        for case in cases:
            (prompts / (case["id"] + ".txt")).write_text(
                model_prompt(case), encoding="utf-8"
            )
            row = {
                "case": case["id"],
                "model_status": "not_run",
                "semantic_status": "pending",
                "checks": [
                    {
                        "id": f"criterion_{i + 1}",
                        "criterion": text,
                        "status": "pending",
                        "answer_quote": None,
                        "actual_model_run_id": None,
                        "evidence_paths": [],
                        "reviewer": None,
                    }
                    for i, text in enumerate(case["manual_review"])
                ],
            }
            if "evaluation_layer" in case:
                row.update(
                    evaluation_layer=case["evaluation_layer"],
                    split=case["split"],
                    source_case_id=case["source_case_id"],
                )
            else:
                pass
            worksheet.append(row)
            if case.get("evidence_files"):
                with tempfile.TemporaryDirectory(
                    prefix="fatebridge-evidence-precheck-"
                ) as directory:
                    workspace = Path(directory)
                    prepare_case_workspace(workspace, source, case)
                    evidence = copy_case_evidence(workspace, case, source)
                row["evidence_files"] = evidence
            else:
                pass
            request = case.get("reference_request")
            if request is None:
                references.append(
                    {
                        "case": case["id"],
                        "reference_status": (
                            "frozen_evidence_files_verified"
                            if case.get("evidence_files")
                            else "no_calculation_required"
                        ),
                    }
                )
                continue
            else:
                pass
            arguments = {
                **request["arguments"],
                "fields": None,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            }
            if case.get("source_case_id") and case.get("evaluation_layer") in LAYERS:
                # External suites freeze their reviewed evidence projection.
                # Keep historical cohorts' full-reference capture unchanged.
                arguments["fields"] = request["arguments"].get("fields")
            else:
                pass
            controls = {
                "as_of",
                "trace_id",
                "parent_run_id",
                "detail",
                "fields",
                "strict_fields",
                "include_snapshot_text",
                "response_char_limit",
                "compact",
            }
            response = await client.call_tool(
                "run_calculation",
                {
                    "tool": request["tool"],
                    "detail": "standard",
                    "arguments": {
                        name: value
                        for name, value in arguments.items()
                        if name not in controls
                    },
                    **{
                        name: value
                        for name, value in arguments.items()
                        if name in controls
                    },
                },
                raise_on_error=False,
            )
            payload = response.structured_content
            path = target / (case["id"] + ".json")
            path.write_text(
                json.dumps(
                    {
                        "tool": request["tool"],
                        "arguments": arguments,
                        "is_error": response.is_error,
                        "structured_content": payload,
                        "content": [
                            block.model_dump(mode="json") for block in response.content
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            expected = case.get("expected_tool_errors", {}).get(request["tool"])
            if expected is not None:
                actual_error = error_response(
                    {
                        "structured_content": payload,
                        "content": [
                            block.model_dump(mode="json") for block in response.content
                        ],
                    }
                )
                if not response.is_error or not matches_expected_error(
                    actual_error, expected
                ):
                    raise ValueError(
                        f"Expected reference MCP error not matched: {case['id']}"
                    )
                else:
                    pass
            elif response.is_error or payload is None:
                raise ValueError(f"Reference MCP call failed: {case['id']}")
            else:
                pass
            references.append(
                {
                    "case": case["id"],
                    "reference_profile": {
                        "tool_selection": "full_catalog",
                    },
                    "reference_status": (
                        "captured_expected_mcp_error"
                        if expected is not None
                        else "captured_real_mcp"
                    ),
                    "run_id": (payload or {}).get("run_metadata", {}).get("run_id"),
                    "payload_file": str(path.relative_to(output)),
                    "payload_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    (output / "review-worksheet.json").write_text(
        json.dumps(
            {
                "scope": "Reference-only preparation. Future semantic review must use the model's ACTUAL captured replies, not treat these separate reference runs as the model's evidence.",
                "model_invocations": 0,
                "cases": worksheet,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return references


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New private output directory; contains evaluation conversations",
    )
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--cases-file", type=Path)
    parser.add_argument(
        "--external-suite",
        choices=("mingli-bench",),
        help="Opt in to a validated public competition suite; isolated from historical cohorts",
    )
    parser.add_argument(
        "--split",
        choices=("development", "holdout"),
        help="External suite split (default: development); one split per invocation",
    )
    parser.add_argument(
        "--codex", help="Codex CLI executable; desktop CLI is preferred"
    )
    parser.add_argument(
        "--model", help="Explicit model override; otherwise the CLI default"
    )
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument(
        "--native-environment",
        type=Path,
        help="Reuse frozen native selector bytes from preparation",
    )
    parser.add_argument(
        "--native-environment-sha256",
        help="Required exact SHA-256 of --native-environment",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Freeze inputs, hidden criteria and real MCP references; never start a model",
    )
    parser.add_argument(
        "--stop-on-execution-failure",
        action="store_true",
        help="Retain the first failed model execution and leave remaining cases unrun",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    else:
        pass
    if bool(args.native_environment) != bool(args.native_environment_sha256):
        parser.error(
            "--native-environment and --native-environment-sha256 must be provided together"
        )
    else:
        pass
    try:
        if args.native_environment is None:
            native_selection = capture_selection()
            native_raw = context_bytes(native_selection, Path.cwd())
        else:
            native_selection, native_raw = load_selection(
                args.native_environment, args.native_environment_sha256
            )
        native_working_directory = execution_directory(native_raw)
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    native_sha256 = hashlib.sha256(native_raw).hexdigest()
    external = None
    if args.external_suite:
        split = args.split or "development"
        try:
            external = (
                load_frozen_selection(args.cases_file, split, args.cases)
                if args.cases_file
                else load_external_suite(
                    ROOT / "tests/fixtures/mingli_bench_v2", split, args.cases
                )
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(str(error))
        cases = external["cases"]
        dataset_bytes = (
            b""  # Serialized with its receipt after the private output exists.
        )
    else:
        if args.split:
            parser.error("--split requires --external-suite")
        else:
            pass
        if args.cases_file is None:
            parser.error("--cases-file is required unless --external-suite is used")
        else:
            pass
        try:
            dataset_bytes = args.cases_file.read_bytes()
            document: object = json.loads(dataset_bytes)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        if not isinstance(document, dict):
            parser.error("Case dataset must be a JSON object")
        else:
            pass
        if document.get("suite_id") in ("mingli-bench-v1", "mingli-bench-v2"):
            parser.error("MingLi data requires --external-suite mingli-bench")
        else:
            pass
        raw_cases = document.get("cases")
        if not isinstance(raw_cases, list):
            parser.error("Case dataset must contain a case list")
        else:
            pass
        known: set[str] = set()
        cases = []
        for case in raw_cases:
            if not isinstance(case, dict):
                parser.error("Evaluation cases must be JSON objects")
            else:
                pass
            case_id = case.get("id")
            if (
                not isinstance(case_id, str)
                or not case_id
                or case_id in {".", ".."}
                or any(character in case_id for character in ("/", "\\", "\x00"))
            ):
                parser.error("Case IDs must be nonempty safe file names")
            else:
                pass
            if case_id in known:
                parser.error("Case IDs must be unique")
            else:
                pass
            known.add(case_id)
            if not args.cases or case_id in args.cases:
                cases.append(case)
            else:
                pass
        if args.cases and not set(args.cases) <= known:
            parser.error("Unknown case; available: " + ", ".join(sorted(known)))
        else:
            pass
    if not cases:
        parser.error("No evaluation cases selected")
    if any({"expected_skill", "expected_skill_sets"} & case.keys() for case in cases):
        parser.error("Cases with retired skill requirements are unsupported")
    cli = None if args.prepare_only else args.codex or resolve_codex_cli()["path"]
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(output, 0o700)
    if external is not None:
        dataset_bytes = freeze_external_selection(external, output)
    else:
        pass
    (output / "case-dataset.json").write_bytes(dataset_bytes)
    (output / "native-environment.json").write_bytes(native_raw)
    if external is not None:
        # Execute the exact sealed bytes reviewed in the output, not mutable inputs.
        external = load_frozen_selection(
            output / "case-dataset.json", external["split"]
        )
        cases = external["cases"]
    else:
        pass
    source = output / "source"
    extra_files = evidence_source_files(cases, ROOT)
    manifest = freeze_source(source, extra_files=extra_files)
    (output / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.prepare_only:
        references = asyncio.run(
            prepare_references(
                cases, output, source, native_selection, native_working_directory
            )
        )
        frozen_manifest = source_manifest(source, extra_files=extra_files)
        if frozen_manifest != manifest:
            raise RuntimeError("Frozen source changed during reference preparation")
        report = {
            "scope": "Frozen preparation and real MCP reference capture only; not model evaluation",
            "selected_case_count": len(cases),
            "model_invocations": 0,
            "semantic_acceptance": "not_run",
            "real_world_observations": 0,
            "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "native_environment_sha256": native_sha256,
            "source_manifest_sha256": hashlib.sha256(
                (output / "source-manifest.json").read_bytes()
            ).hexdigest(),
            "references": references,
            "runtime_dependencies": {
                n: importlib.metadata.version(n) for n in ("fastmcp", "pydantic")
            },
        }
        if external is not None:
            report.update(evaluation_summary(external))
            report["scope"] = (
                "Frozen public competition adaptation and MCP references; no model or semantic evaluation"
            )
        else:
            pass
        (output / "preparation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {"status": "prepared", "cases": len(cases), "model_invocations": 0},
                ensure_ascii=False,
            )
        )
        return 0
    else:
        pass
    report = {
        "scope": "real Codex model + current stdio MCP; fictional isolated cases",
        "cli": cli,
        "cli_version": subprocess.check_output([cli, "--version"], text=True).strip(),
        "model": args.model or "CLI default (unrelated user config ignored)",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "native_environment_sha256": native_sha256,
        "source_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "runtime_dependencies": {
            name: importlib.metadata.version(name)
            for name in ("fastmcp", "pydantic", "pyswisseph")
        },
        "cases": [],
        "selected_case_count": len(cases),
        "unrun_case_ids": [c["id"] for c in cases],
        "manual_review_required": True,
    }
    if external is not None:
        report.update(evaluation_summary(external))
        report["scope"] = (
            "Real Codex model + frozen stdio MCP; public competition adaptations; semantic review pending"
        )
    else:
        pass
    for case in cases:
        record = run_case(
            cli,
            case,
            output,
            args.timeout,
            args.model,
            source,
            native_selection,
            native_working_directory,
        )
        report["cases"].append(record)
        report["unrun_case_ids"] = [c["id"] for c in cases[len(report["cases"]) :]]
        report["mechanical_checks_passed"] = all(
            c["mechanical_checks_passed"] for c in report["cases"]
        )
        if external is not None:
            report.update(evaluation_summary(external, report["cases"]))
        else:
            pass
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "case": case["id"],
                    "passed": record["mechanical_checks_passed"],
                    "failures": record["failures"],
                }
            ),
            flush=True,
        )
        if args.stop_on_execution_failure and record["exit_code"]:
            break
        else:
            pass
    return 0 if report["mechanical_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
