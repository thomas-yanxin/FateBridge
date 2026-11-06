"""Run isolated Codex conversations and grade observable tool behavior.

Requires an authenticated Codex CLI. No API key, user config edits, or pytest-time
model calls. Each case uses a new temporary workspace and the current interpreter's
real stdio MCP. The CLI default model is used unless --model is explicitly passed.
"""

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
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.validation.evaluation_assets import (
    copy_case_evidence,
    evidence_source_files,
    prepare_evidence_workspace,
    resolve_source,
)
from fatebridge.validation.evaluation_environment import (
    capture_selection,
    context_bytes,
    execution_directory,
    load_selection,
    process_environment,
    selected_environment,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests/fixtures/agent_behavior/cases.json"


def source_files(root=ROOT, profile="full", extra_files=()):
    if profile not in {"full", "runtime"}:
        raise ValueError("Unknown evaluation source snapshot profile")
    selected = [root / name for name in ("AGENTS.md", "pyproject.toml", "uv.lock")]
    for name in (
        "scripts/evaluate_agent.py",
        "scripts/evaluate_agent.pyi",
        "tests/evaluation/test_agent_evaluation.py",
        "tests/evaluation/test_contract_regressions.py",
        "tests/evaluation/test_agent_expected_errors.py",
        "tests/evaluation/test_agent_capture.py",
        "tests/evaluation/test_agent_tool_contract.py",
        "tests/bazi/test_bazi_focus_precision.py",
        "tests/fixtures/agent_behavior/cases.json",
        "tests/fixtures/agent_behavior/other_chart_cases.json",
        "tests/fixtures/agent_behavior/meihua_semantic_cases.json",
        "tests/fixtures/agent_behavior/ren_semantic_cases.json",
        "tests/fixtures/agent_behavior/taiyi_semantic_cases_v1.json",
        "tests/fixtures/agent_behavior/ren_semantic_refresh_cases_v1.json",
        "tests/ren/test_ren_semantic_refresh_preparation.py",
        "scripts/ren/audit_ren_semantic_refresh.py",
        "tests/fixtures/agent_behavior/jyotish_semantic_cases.json",
        "tests/fixtures/agent_behavior/human_design_semantic_cases_v1.json",
        "tests/fixtures/agent_behavior/human_design_complete_case_v3.json",
        "tests/human_design/test_human_design_semantic_preparation.py",
        "tests/human_design/test_human_design_semantic_binding.py",
        "tests/human_design/test_human_design_evaluation_runtime.py",
        "tests/evaluation/test_agent_native_environment.py",
        "tests/evaluation/test_agent_native_context.py",
        "tests/evaluation/test_agent_solar_environment.py",
        "tests/human_design/test_human_design_native_launch.py",
        "scripts/human_design/preserve_human_design_deliveries.py",
        "scripts/human_design/audit_human_design_semantics.py",
        "tests/fixtures/agent_behavior/bazi_semantic_cases_v1.json",
        "tests/fixtures/agent_behavior/western_semantic_cases_v1.json",
        "tests/western/test_western_semantic_preparation.py",
        "tests/evaluation/test_external_evaluation.py",
        "tests/evaluation/test_mingli_corpus.py",
        "tests/evaluation/test_mingli_semantic_audit.py",
        "scripts/evaluation/build_mingli_evaluation.py",
        "scripts/evaluation/audit_mingli_evaluation.py",
    ):
        path = root / name
        if path.is_file():
            selected.append(path)
    for folder in ("skills", "configs", "docs", "src"):
        selected.extend(
            p
            for p in (root / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix != ".pyc"
            and p.name != ".DS_Store"
            and not (
                profile == "runtime" and p.is_relative_to(root / "docs/validation")
            )
        )
    for relative in extra_files:
        path = resolve_source(root, relative)
        if path not in selected:
            selected.append(path)
    return sorted(selected)


def source_manifest(root=ROOT, profile="full", extra_files=()):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_files(root, profile, extra_files)
    }


def freeze_source(target, root=ROOT, profile="full", extra_files=()):
    """Freeze one batch's instructions and executable backend, including dirty work."""
    manifest = (
        source_manifest(root, profile, extra_files)
        if extra_files
        else (
            source_manifest(root)
            if profile == "full"
            else source_manifest(root, profile)
        )
    )
    # Keep one file in memory, not all historical validation/source archives.
    # Before/copy/after hashes retain the same fail-closed consistency rule.
    for name, expected in manifest.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(
                "Source changed while snapshotting; retry the evaluation"
            )
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    after = (
        source_manifest(root, profile, extra_files)
        if extra_files
        else (
            source_manifest(root)
            if profile == "full"
            else source_manifest(root, profile)
        )
    )
    frozen = (
        source_manifest(target, profile, extra_files)
        if extra_files
        else (
            source_manifest(target)
            if profile == "full"
            else source_manifest(target, profile)
        )
    )
    if after != manifest or frozen != manifest:
        raise RuntimeError("Source changed while snapshotting; retry the evaluation")
    return manifest


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def observations(events):
    calls, commands = [], []
    for event in events:
        # Only completed items: started/completed events refer to the same call.
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if item.get("type") == "mcp_tool_call":
            calls.append(
                {
                    "server": item.get("server"),
                    "tool": item.get("tool"),
                    "arguments": item.get("arguments", {}),
                    "status": item.get("status"),
                    "error": item.get("error"),
                    "protocol_error": bool(
                        (item.get("result") or {}).get("isError")
                        or (item.get("result") or {}).get("is_error")
                    ),
                    "error_response": error_response(item.get("result") or {}),
                }
            )
        for node in walk(item):
            if isinstance(node.get("command"), str):
                commands.append(node["command"])
    return calls, commands


def error_response(result):
    """Extract an actual structured error; never infer a code from prose."""
    for key in ("structuredContent", "structured_content"):
        value = result.get(key)
        if isinstance(value, dict) and isinstance(value.get("error_code"), str):
            return value
    for block in result.get("content") or []:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            continue
        try:
            value = json.loads(block["text"])
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("error_code"), str):
            return value
    return None


def matches_expected_error(actual, expected):
    """Only predeclared exact typed error fields can authorize a refusal case."""
    required = {"error_code", "status_code", "retryable"}
    return (
        isinstance(actual, dict)
        and isinstance(expected, dict)
        and required <= expected.keys()
        and type(expected["error_code"]) is str
        and bool(expected["error_code"])
        and type(expected["status_code"]) is int
        and type(expected["retryable"]) is bool
        and all(
            key in actual
            and type(value) in {str, int, bool, type(None)}
            and type(actual.get(key)) is type(value)
            and actual.get(key) == value
            for key, value in expected.items()
        )
    )


def expected_error_call(call, expected):
    return (
        (
            (call["status"] == "completed" and call["protocol_error"])
            or (
                call["status"] == "failed"
                and call.get("captured_returned_error") is not None
            )
        )
        and not call["error"]
        and matches_expected_error(call["error_response"], expected)
    )


def grade_case(case, events, final, returncode, captured_tool_records=None):
    calls, commands = observations(events)
    own = [c for c in calls if c["server"] == "fatebridge"]
    # Some CLI versions mark a returned MCP business error as status=failed and
    # omit isError. Only an identity-matched, independently captured server reply
    # can distinguish that representation from a transport failure. Raw CLI
    # status/protocol flags stay unchanged in the report.
    if captured_tool_records is not None and len(own) == len(captured_tool_records):
        identical = all(
            c["tool"] == r.get("tool") and c["arguments"] == r.get("arguments")
            for c, r in zip(own, captured_tool_records)
        )
        if identical:
            for call, record in zip(own, captured_tool_records):
                response = record.get("result") or {}
                if (
                    record.get("event") == "tool_call"
                    and record.get("outcome") == "returned"
                    and response.get("is_error") is True
                    and call["error_response"] is not None
                    and error_response(response) == call["error_response"]
                    and matches_expected_error(
                        error_response(response),
                        case.get("expected_tool_errors", {}).get(call["tool"]),
                    )
                ):
                    call["captured_returned_error"] = {
                        "journal_record_sha256": record.get("sha256"),
                        "is_error": True,
                        "scope": "Matched actual server reply; raw CLI status retained",
                    }
    names = {c["tool"] for c in own}
    failures = []
    if returncode or not final.strip():
        failures.append("execution_failed_or_empty_answer")
    if any(c["server"] != "fatebridge" for c in calls):
        failures.append("unexpected_external_service")
    last = {c["tool"]: c for c in own}
    expected_errors = case.get("expected_tool_errors", {})
    if any(
        (c["status"] == "failed" or c["error"] or c["protocol_error"])
        and not expected_error_call(c, expected_errors.get(c["tool"]))
        for c in last.values()
    ):
        failures.append("unrecovered_tool_failure")
    for name, expected in expected_errors.items():
        selected = [c for c in own if c["tool"] == name]
        if not selected or not all(expected_error_call(c, expected) for c in selected):
            failures.append("expected_tool_error_not_matched:" + name)
    for choices in case.get("required_any", []):
        if not names.intersection(choices):
            failures.append("missing_tool:" + "|".join(choices))
    if case.get("no_calculation") and any(
        name
        not in {
            "knowledge_read",
            "knowledge_registry",
            "read_mcp_resource",
            "list_mcp_resources",
            "list_mcp_resource_templates",
        }
        for name in names
    ):
        failures.append("unexpected_calculation")
    if names.intersection(case.get("forbidden_tools", [])):
        failures.append("out_of_scope_tool")
    if "allowed_tools" in case and names - set(case["allowed_tools"]):
        failures.append("out_of_scope_tool")
    skill_sets = case.get("expected_skill_sets") or (
        [[case["expected_skill"]]] if case.get("expected_skill") else []
    )
    if skill_sets and not any(
        all(
            any(skill in cmd and "SKILL.md" in cmd for cmd in commands)
            for skill in group
        )
        for group in skill_sets
    ):
        failures.append(
            "skill_not_observed:" + "|".join("+".join(group) for group in skill_sets)
        )
    for name, expected in case.get("arguments", {}).items():
        selected = [c for c in own if c["tool"] == name]
        if not selected or any(
            c["arguments"].get(key) != value
            for c in selected
            for key, value in expected.items()
        ):
            failures.append("input_mismatch:" + name)
    for name, expected in case.get("argument_paths", {}).items():
        selected = [c for c in own if c["tool"] == name]
        if not selected or any(
            not _same_argument_path(c["arguments"], path, value)
            for c in selected
            for path, value in expected.items()
        ):
            failures.append("input_mismatch:" + name)
    for name, expected in case.get("instant_arguments", {}).items():
        selected = [c for c in own if c["tool"] == name]

        def same_instant(actual, expected):
            try:
                actual_time = datetime.fromisoformat(actual)
                expected_time = datetime.fromisoformat(expected)
                return (
                    actual_time.utcoffset() is not None
                    and expected_time.utcoffset() is not None
                    and actual_time == expected_time
                )
            except (TypeError, ValueError):
                return False

        if not selected or any(
            not same_instant(c["arguments"].get(key), value)
            for c in selected
            for key, value in expected.items()
        ):
            failures.append("instant_mismatch:" + name)
    for name, maximum in case.get("max_successful_calls", {}).items():
        successful = [
            c
            for c in own
            if c["tool"] == name
            and c["status"] == "completed"
            and not c["error"]
            and not c["protocol_error"]
        ]
        if len(successful) > maximum:
            failures.append("repeated_calculation:" + name)
    for name, maximum in case.get("max_total_calls", {}).items():
        if sum(c["tool"] == name for c in own) > maximum:
            failures.append("repeated_tool_attempt:" + name)
    if case.get("full_export"):
        selected = [c for c in own if c["tool"] == case["full_export"]]
        if not selected or selected[0]["arguments"].get("fields") is not None:
            failures.append("projected_full_export")
    return {
        "mechanical_checks_passed": not failures,
        "failures": failures,
        "tool_calls": own,
        "commands": commands,
        "manual_review": case["manual_review"],
    }


# These ids describe predeclared case contracts, never model outcomes.
GRADING_POLICY = "observed_calls_and_declared_errors_v2"


def _same_argument_path(arguments, path, expected):
    value = arguments
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return value == expected and isinstance(value, bool) == isinstance(expected, bool)


# Keep runtime documentation, but do not hand the examinee past grades, answer
# transcripts or evaluator descriptions. The full snapshot still retains these
# materials for the reviewer; only the model workspace excludes them.
EVALUATION_DOCS_EXCLUDED = {
    "validation",
    "reviews",
    "agent-evaluation.md",
    "numerology-semantics-preparation.md",
    "liuren-jinkou-audit.md",
    "meihua-semantics-evaluation.md",
    "bazi-semantics-evaluation.md",
    "bazi-grader-policy-audit.md",
    "taiyi-semantics-evaluation.md",
    "western-semantics-evaluation.md",
    "human-design-semantics-evaluation.md",
    "mingli-bench-evaluation.md",
}


def _without_evaluation_private_sections(text):
    """Remove explicit reviewer-only spans, preserving ordinary source prose."""
    start = "<!-- agent-evaluation-private:start -->"
    end = "<!-- agent-evaluation-private:end -->"
    parts = text.split(start)
    if end in parts[0]:
        raise ValueError("Unbalanced evaluation-private document markers")
    visible = [parts[0]]
    for part in parts[1:]:
        if part.count(end) != 1:
            raise ValueError("Unbalanced evaluation-private document markers")
        _, public = part.split(end, 1)
        visible.append(public)
    return "".join(visible)


def prepare_workspace(workspace, source=ROOT):
    shutil.copy2(source / "AGENTS.md", workspace / "AGENTS.md")
    shutil.copytree(source / "src", workspace / "src")
    for name in ("skills", "configs"):
        if (source / name).is_dir():
            shutil.copytree(source / name, workspace / name)
    shutil.copytree(
        source / "docs",
        workspace / "docs",
        ignore=lambda _directory, names: set(names) & EVALUATION_DOCS_EXCLUDED,
    )
    for path in (workspace / "docs").rglob("*.md"):
        original = path.read_text(encoding="utf-8")
        visible = _without_evaluation_private_sections(original)
        if visible != original:
            path.write_text(visible, encoding="utf-8")
    entries = workspace / ".agents/skills"
    entries.mkdir(parents=True)
    for skill in (workspace / "skills").glob("*"):
        if not (skill / "SKILL.md").is_file():
            continue
        (entries / skill.name).symlink_to(
            Path("../../skills") / skill.name, target_is_directory=True
        )
    with (workspace / "AGENTS.md").open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## 验收环境\n"
            "仅使用本目录资料、MCP 结果交付文件与 FateBridge 只读工具，直接完成用户请求。"
            "不安装、修改配置、写源文件、访问其他服务或向别人发送消息。\n"
        )


def prepare_case_workspace(workspace: Path, source: Path, case: dict[str, Any]) -> None:
    mode = case.get("evidence_only_workspace", False)
    if type(mode) is not bool:
        raise ValueError("evidence_only_workspace must be a boolean")
    if mode:
        if not case.get("evidence_files"):
            raise ValueError("Evidence-only workspaces require declared evidence")
        prepare_evidence_workspace(workspace, source)
    else:
        prepare_workspace(workspace, source)


def command_for(
    cli,
    workspace,
    output,
    case,
    model=None,
    backend_source=None,
    native_selection=None,
    native_working_directory=None,
):
    if case.get("evidence_only_workspace") and backend_source is None:
        raise ValueError("Evidence-only models require a separate frozen MCP backend")
    backend = backend_source if case.get("evidence_only_workspace") else workspace
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
        "--disable",
        "skill_mcp_dependency_install",
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
        "mcp_servers.fatebridge.env.FATEBRIDGE_MCP_SCENARIOS": case.get("scenario", ""),
        "mcp_servers.fatebridge.env.FATEBRIDGE_MCP_TOOL_SCOPE": case.get(
            "tool_scope", "complete"
        ),
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
            "fatebridge.validation.agent_capture",
        ]
        settings["mcp_servers.fatebridge.env.FATEBRIDGE_EVALUATION_LOG"] = str(
            output / "mcp-calls.jsonl"
        )
    if native_working_directory is not None:
        settings["mcp_servers.fatebridge.cwd"] = str(native_working_directory)
        # Script mode keeps Python's initial import path in the frozen source.
        # With -m, an unrelated fatebridge/sitecustomize in the native data cwd
        # could shadow the declared PYTHONPATH before our code starts. This
        # also works on Python3.10, which has no -P switch.
        entry = (
            "src/fatebridge/validation/agent_capture.py"
            if case.get("capture_payloads")
            else "src/fatebridge/mcp_server.py"
        )
        settings["mcp_servers.fatebridge.args"] = [
            "-X",
            "utf8",
            str((backend / entry).absolute()),
        ]
    for key, value in settings.items():
        command.extend(["-c", key + "=" + json.dumps(value, ensure_ascii=False)])
    if model:
        command.extend(["--model", model])
    command.append("-")
    return command


def run_case(
    cli,
    case,
    output,
    timeout,
    model=None,
    source=ROOT,
    native_selection=None,
    native_working_directory=None,
):
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
        command = (
            command_for(
                cli,
                workspace,
                target,
                case,
                model,
                source,
                native_selection,
                native_working_directory,
            )
            if case.get("evidence_only_workspace")
            else command_for(
                cli,
                workspace,
                target,
                case,
                model,
                native_selection=native_selection,
                native_working_directory=native_working_directory,
            )
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
    if evidence:
        record["evidence_files"] = evidence
    if case.get("capture_payloads"):
        from fatebridge.validation.agent_capture import read_capture

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
    (target / "grade.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def reference_scenarios(cases):
    """Reference servers cover the selected cases, not a hard-coded discipline."""
    scenarios = {case.get("scenario", "") for case in cases}
    return ",".join(sorted(scenarios)) if "" not in scenarios else ""


def reference_tool_scope(cases):
    """Keep a homogeneous topic batch restricted during reference capture too.

    Mixed batches retain the complete reference union. Actual model execution
    still creates a separate server with each case's declared scope.
    """
    scopes = {case.get("tool_scope", "complete") for case in cases}
    if scopes - {"complete", "topic"}:
        raise ValueError("Unknown reference tool scope")
    if any(
        case.get("tool_scope", "complete") == "topic" and not case.get("scenario")
        for case in cases
    ):
        raise ValueError("Topic reference capture requires a scenario")
    return "topic" if scopes == {"topic"} else "complete"


def model_prompt(case):
    """Expose the operational tool contract, never hidden answer criteria.

    Earlier runs graded allowed_tools without telling the model about that
    restriction. Keep those failures; enforce the same contract prospectively.
    """
    allowed = case.get("allowed_tools")
    if allowed is None:
        return case["prompt"]
    if allowed == []:
        return (
            "本次运行的工具合同：不调用任何 FateBridge 工具。"
            "请按适用技能核对已确认资料并直接回应当前请求。\n\n" + case["prompt"]
        )
    return (
        "本次运行的工具合同：只允许调用以下FateBridge工具："
        + "、".join(allowed)
        + "。即使技能给出其他通用入口，也须遵守本次限定；不以别的计算工具替代。"
        + "仍按适用技能核对输入、读取实际回执和同run分页。\n\n"
        + case["prompt"]
    )


async def prepare_references(
    cases, output, source, native_selection=None, native_working_directory=None
):
    """Call real MCP tools only; do not start a model or grade any answer."""
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    from fatebridge.validation.external_evaluation import LAYERS

    target = output / "reference-payloads"
    target.mkdir()
    prompts = output / "model-prompts"
    prompts.mkdir()
    transport = StdioTransport(
        command=sys.executable,
        args=(
            ["-X", "utf8", "-m", "fatebridge.validation.agent_capture"]
            if native_working_directory is None
            else [
                "-X",
                "utf8",
                str((source / "src/fatebridge/validation/agent_capture.py").absolute()),
            ]
        ),
        cwd=str(
            source if native_working_directory is None else native_working_directory
        ),
        env={
            **selected_environment(native_selection),
            "PYTHONPATH": str(source / "src"),
            "FATEBRIDGE_EVALUATION_LOG": str(output / "reference-mcp.jsonl"),
            "FATEBRIDGE_MCP_FAMILIES": "",
            "FATEBRIDGE_MCP_SCENARIOS": reference_scenarios(cases),
            "FATEBRIDGE_MCP_TOOL_SCOPE": reference_tool_scope(cases),
        },
        log_file=output / "reference-mcp-stderr.log",
    )
    references = []
    worksheet = []
    async with Client(transport) as client:
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
            worksheet.append(row)
            if case.get("evidence_files"):
                with tempfile.TemporaryDirectory(
                    prefix="fatebridge-evidence-precheck-"
                ) as directory:
                    workspace = Path(directory)
                    prepare_case_workspace(workspace, source, case)
                    evidence = copy_case_evidence(workspace, case, source)
                row["evidence_files"] = evidence
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
            response = await client.call_tool(
                request["tool"], arguments, raise_on_error=False
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
            elif response.is_error or payload is None:
                raise ValueError(f"Reference MCP call failed: {case['id']}")
            references.append(
                {
                    "case": case["id"],
                    "reference_profile": {
                        "scenarios": reference_scenarios(cases),
                        "tool_scope": reference_tool_scope(cases),
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


def main():
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
        "--snapshot-profile",
        choices=("full", "runtime"),
        default="full",
        help="runtime retains backend/data, scenario configs, optional skills, public docs and judge code; excludes past docs/validation archives",
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
    if bool(args.native_environment) != bool(args.native_environment_sha256):
        parser.error(
            "--native-environment and --native-environment-sha256 must be provided together"
        )
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
        from fatebridge.validation.external_evaluation import (
            evaluation_summary,
            freeze_external_selection,
            load_external_suite,
            load_frozen_selection,
        )

        split = args.split or "development"
        try:
            external = (
                load_frozen_selection(args.cases_file, split, args.cases)
                if args.cases_file
                else load_external_suite(
                    ROOT / "tests/fixtures/mingli_bench_v1", split, args.cases
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
        dataset_bytes = (args.cases_file or CASES).read_bytes()
        document = json.loads(dataset_bytes)
        if document.get("suite_id") == "mingli-bench-v1":
            parser.error("MingLi data requires --external-suite mingli-bench")
        cases = document["cases"]
        known = {case["id"] for case in cases}
        if len(known) != len(cases):
            parser.error("Case IDs must be unique")
        if args.cases and not set(args.cases) <= known:
            parser.error("Unknown case; available: " + ", ".join(sorted(known)))
        cases = [c for c in cases if not args.cases or c["id"] in args.cases]
    from fatebridge.diagnostics import resolve_codex_cli

    cli = None if args.prepare_only else args.codex or resolve_codex_cli()["path"]
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(output, 0o700)
    if external is not None:
        dataset_bytes = freeze_external_selection(external, output)
    (output / "case-dataset.json").write_bytes(dataset_bytes)
    (output / "native-environment.json").write_bytes(native_raw)
    if external is not None:
        # Execute the exact sealed bytes reviewed in the output, not mutable inputs.
        external = load_frozen_selection(
            output / "case-dataset.json", external["split"]
        )
        cases = external["cases"]
    source = output / "source"
    extra_files = evidence_source_files(cases, ROOT)
    manifest = (
        freeze_source(source, profile=args.snapshot_profile, extra_files=extra_files)
        if extra_files
        else (
            freeze_source(source)
            if args.snapshot_profile == "full"
            else freeze_source(source, profile=args.snapshot_profile)
        )
    )
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
        frozen_manifest = (
            source_manifest(source, args.snapshot_profile, extra_files)
            if extra_files
            else (
                source_manifest(source)
                if args.snapshot_profile == "full"
                else source_manifest(source, profile=args.snapshot_profile)
            )
        )
        if frozen_manifest != manifest:
            raise RuntimeError("Frozen source changed during reference preparation")
        command = [
            sys.executable,
            str(source / "scripts/evaluate_agent.py"),
            "--cases-file",
            str(output / "case-dataset.json"),
            "--output",
            str(output / "model-run"),
            "--timeout",
            str(args.timeout),
            "--stop-on-execution-failure",
            "--native-environment",
            str(output / "native-environment.json"),
            "--native-environment-sha256",
            native_sha256,
        ]
        for name in args.cases or []:
            command.extend(["--case", name])
        if external is not None:
            command.extend(
                ["--external-suite", args.external_suite, "--split", external["split"]]
            )
        if args.codex:
            command.extend(["--codex", args.codex])
        if args.model:
            command.extend(["--model", args.model])
        if args.snapshot_profile != "full":
            command.extend(["--snapshot-profile", args.snapshot_profile])
        proposal = {
            "command": command,
            "cwd": str(source),
            "environment": {"PYTHONPATH": str(source / "src")},
            "requires_session_authorization_for_independent_model": True,
        }
        (output / "proposed-execution.json").write_text(
            json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        report = {
            "scope": "Frozen preparation and real MCP reference capture only; not model evaluation",
            "selected_case_count": len(cases),
            "model_invocations": 0,
            "semantic_acceptance": "not_run",
            "real_world_observations": 0,
            "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "source_snapshot_profile": args.snapshot_profile,
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
    report = {
        "scope": "real Codex model + current stdio MCP; fictional isolated cases",
        "cli": cli,
        "cli_version": subprocess.check_output([cli, "--version"], text=True).strip(),
        "model": args.model or "CLI default (unrelated user config ignored)",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "source_snapshot_profile": args.snapshot_profile,
        "native_environment_sha256": native_sha256,
        "source_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "runtime_dependencies": {
            name: importlib.metadata.version(name)
            for name in ("fastmcp", "pydantic", "kerykeion", "pyswisseph")
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
    return 0 if report["mechanical_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
