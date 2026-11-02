"""Bind relative native paths to the original directory, without model calls."""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

import scripts.evaluate_agent as evaluator
from fatebridge.validation.evaluation_environment import (
    CONTEXT_METHOD,
    capture_selection,
    context_bytes,
    execution_directory,
    frozen_working_directory,
    load_selection,
    verify_stage_selection,
)
from scripts import preserve_human_design_deliveries as wrapper

ROOT = Path(__file__).resolve().parents[1]


def settings(command):
    return {
        command[i + 1].split("=", 1)[0]: json.loads(command[i + 1].split("=", 1)[1])
        for i, token in enumerate(command[:-1])
        if token == "-c"
    }


def save(tmp_path, raw):
    path = tmp_path / "native.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def test_context_keeps_path_list_basename_and_unset_values_exact(tmp_path):
    values = {
        "SE_EPHE_PATH": "missing" + os.pathsep + "./ephe with spaces",
        "FATEBRIDGE_JPL_FILE": "de441.eph",
        "FATEBRIDGE_SOLAR_SPK_FILE": "data/kernel.bsp",
        "XDG_CACHE_HOME": "./cache",
        "OPENAI_API_KEY": "must-never-be-frozen",
    }
    chosen = capture_selection(values)
    raw = context_bytes(chosen, tmp_path)
    path, sha = save(tmp_path, raw)
    loaded, original = load_selection(path, sha)
    assert loaded == chosen and original == raw
    assert json.loads(raw)["method_id"] == CONTEXT_METHOD
    assert execution_directory(raw) == tmp_path.resolve()
    assert frozen_working_directory(raw)["path"] == str(tmp_path.resolve())
    assert b"must-never-be-frozen" not in raw
    assert loaded["FATEBRIDGE_JPL_FILE"] == "de441.eph"
    assert loaded["SE_EPHE_PATH"] == values["SE_EPHE_PATH"]
    assert loaded["FATEBRIDGE_SOLAR_TERM_MODEL"] is None


@pytest.mark.parametrize(
    "fault", ["missing", "extra", "relative", "number", "nul", "flavor", "list"]
)
def test_rehashed_invalid_directory_context_is_rejected(tmp_path, fault):
    record = json.loads(context_bytes(capture_selection({}), tmp_path))
    if fault == "missing":
        record.pop("working_directory")
    elif fault == "extra":
        record["working_directory"]["native_execution_authenticated"] = True
    elif fault == "relative":
        record["working_directory"]["path"] = "some/relative/path"
    elif fault == "number":
        record["working_directory"]["path"] = 123
    elif fault == "nul":
        record["working_directory"]["path"] += "\x00"
    elif fault == "flavor":
        record["working_directory"]["flavor"] = "future_unknown"
    else:
        record["working_directory"]["flavor"] = []
    path, sha = save(tmp_path, json.dumps(record).encode())
    with pytest.raises(ValueError):
        load_selection(path, sha)


@pytest.mark.parametrize("network_share", [False, True])
def test_foreign_context_remains_offline_auditable_but_cannot_execute(
    tmp_path, network_share
):
    record = json.loads(context_bytes(capture_selection({}), tmp_path))
    foreign = (
        {"flavor": "posix", "path": "/original/source"}
        if os.name == "nt"
        else {
            "flavor": "nt",
            "path": (
                r"\\server\share\original" if network_share else r"C:\original source"
            ),
        }
    )
    record["working_directory"] = foreign
    path, sha = save(tmp_path, json.dumps(record).encode())
    _, raw = load_selection(path, sha)
    assert frozen_working_directory(raw) == foreign
    with pytest.raises(ValueError, match="another path platform"):
        execution_directory(raw)


def test_removed_directory_is_not_required_for_offline_binding(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    raw = context_bytes(capture_selection({"SE_EPHE_PATH": "ephe"}), origin)
    origin.rmdir()
    path, sha = save(tmp_path, raw)
    load_selection(path, sha)
    with pytest.raises(ValueError, match="unavailable"):
        execution_directory(raw)
    run = tmp_path / "run"
    run.mkdir()
    for folder, name in [(tmp_path, "preparation.json"), (run, "report.json")]:
        (folder / name).write_text(json.dumps({"native_environment_sha256": sha}))
        (folder / "native-environment.json").write_bytes(raw)
    result = verify_stage_selection(tmp_path, run)
    assert result["native_working_directory"]["path"] == str(origin)
    assert result["actual_file_read_set_authenticated"] is False


def test_same_selectors_in_a_different_directory_are_not_one_stage_context(tmp_path):
    chosen = capture_selection({"SE_EPHE_PATH": "ephe"})
    run = tmp_path / "run"
    run.mkdir()
    for folder, name in [(tmp_path, "preparation.json"), (run, "report.json")]:
        raw = context_bytes(chosen, folder)
        (folder / "native-environment.json").write_bytes(raw)
        (folder / name).write_text(
            json.dumps({"native_environment_sha256": hashlib.sha256(raw).hexdigest()})
        )
    with pytest.raises(ValueError, match="differ"):
        verify_stage_selection(tmp_path, run)


def test_missing_native_directory_stops_cli_before_model_lookup(tmp_path, monkeypatch):
    raw = context_bytes(capture_selection({}), tmp_path / "not-present")
    path, sha = save(tmp_path, raw)

    def prohibited():
        raise AssertionError("Invalid native context reached model lookup")

    monkeypatch.setattr("fatebridge.diagnostics.resolve_codex_cli", prohibited)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluator",
            "--output",
            str(tmp_path / "out"),
            "--native-environment",
            str(path),
            "--native-environment-sha256",
            sha,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        evaluator.main()
    assert exc.value.code == 2
    assert not (tmp_path / "out").exists()


def test_unavailable_context_stops_preserver_before_any_model_process(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    raw = context_bytes(capture_selection({"SE_EPHE_PATH": "ephe"}), tmp_path / "lost")
    sha = hashlib.sha256(raw).hexdigest()
    (tmp_path / "native-environment.json").write_bytes(raw)
    (tmp_path / "preparation.json").write_text(
        json.dumps({"native_environment_sha256": sha})
    )
    (tmp_path / "proposed-execution.json").write_text(
        json.dumps(
            {
                "command": [
                    sys.executable,
                    str(source / "scripts/evaluate_agent.py"),
                    "--native-environment",
                    str(tmp_path / "native-environment.json"),
                    "--native-environment-sha256",
                    sha,
                ],
                "cwd": str(source),
                "environment": {},
            }
        )
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Lost native working directory reached Popen")

    monkeypatch.setattr(wrapper.subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="unavailable"):
        wrapper.launch(tmp_path)
    assert not (tmp_path / "model-process.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("path_mode", ["relative", "path_list", "empty"])
async def test_actual_reference_and_model_workspaces_keep_requested_file_resolution(
    tmp_path, path_mode, monkeypatch
):
    origin = tmp_path / "native-origin"
    origin.mkdir()
    (origin / "fatebridge").mkdir()
    (origin / "fatebridge/__init__.py").write_text(
        "raise RuntimeError('UNFROZEN_NATIVE_CWD_PACKAGE_IMPORTED')\n"
    )
    (origin / "sitecustomize.py").write_text(
        "raise RuntimeError('UNFROZEN_NATIVE_CWD_SITECUSTOMIZE_IMPORTED')\n"
    )
    if os.name == "nt":
        shutil.copytree(ROOT / "ephe", origin / "ephe")
    else:
        (origin / "ephe").symlink_to(ROOT / "ephe", target_is_directory=True)
    workspace = tmp_path / "model-workspace"
    workspace.mkdir()
    if os.name == "nt":
        shutil.copytree(
            ROOT / "src",
            workspace / "src",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    else:
        (workspace / "src").symlink_to(ROOT / "src", target_is_directory=True)
    if path_mode == "empty":
        empty = tmp_path / "empty"
        empty.mkdir()
        requested = os.path.relpath(empty, origin)
    else:
        requested = (
            "ephe"
            if path_mode == "relative"
            else "no-such-directory" + os.pathsep + "ephe"
        )
    chosen = capture_selection({"SE_EPHE_PATH": requested})
    monkeypatch.setenv("SE_EPHE_PATH", "/unrelated/later/path")
    case = {
        "id": "one",
        "scenario": "onda-xingpan",
        "tool_scope": "complete",
        "capture_payloads": True,
        "prompt": "虚构工程配置核对。",
        "manual_review": [],
        "reference_request": {
            "tool": "human_design",
            "arguments": {
                "birth_year": 1980,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 0,
                "birth_minute": 0,
                "birth_timezone": "UTC",
                "cycle_reference_datetime": "2025-01-01T00:00:00Z",
            },
        },
    }
    await evaluator.prepare_references([case], tmp_path, ROOT, chosen, origin)
    command = evaluator.command_for(
        "not-executed",
        workspace,
        tmp_path,
        case,
        native_selection=chosen,
        native_working_directory=origin,
    )
    config = settings(command)
    assert config["mcp_servers.fatebridge.cwd"] == str(origin)
    assert config["mcp_servers.fatebridge.args"][-1] == str(
        workspace / "src/fatebridge/validation/agent_capture.py"
    )
    assert config["mcp_servers.fatebridge.env.PYTHONPATH"] == str(workspace / "src")
    assert config["mcp_servers.fatebridge.env.SE_EPHE_PATH"] == requested
    prefix = "mcp_servers.fatebridge.env."
    env = {k[len(prefix) :]: v for k, v in config.items() if k.startswith(prefix)}
    env["FATEBRIDGE_EVALUATION_LOG"] = str(tmp_path / "model-arm.jsonl")
    async with Client(
        StdioTransport(
            command=config["mcp_servers.fatebridge.command"],
            args=config["mcp_servers.fatebridge.args"],
            cwd=config["mcp_servers.fatebridge.cwd"],
            env=env,
            log_file=tmp_path / "model-stderr.log",
        )
    ) as client:
        model = await client.call_tool(
            "human_design",
            {
                **case["reference_request"]["arguments"],
                "fields": None,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
        )
    assert not model.is_error
    reference = json.loads((tmp_path / "reference-payloads/one.json").read_text())[
        "structured_content"
    ]
    for key in [
        "activations",
        "bodygraph",
        "design_solver",
        "cycle_summary",
        "ephemeris_source_summary",
    ]:
        assert reference[key] == model.structured_content[key]
    assert reference["calculation_policy"]["ephemeris_model"] == (
        "moshier" if path_mode == "empty" else "swieph"
    )
    assert reference["cycle_summary"]["bodies"][2]["contact_count"] == (
        0 if path_mode == "empty" else 3
    )
    for name in ["model-stderr.log", "reference-mcp-stderr.log"]:
        assert "UNFROZEN_NATIVE_CWD" not in (tmp_path / name).read_text()


@pytest.mark.asyncio
async def test_anchored_non_capture_server_uses_frozen_absolute_entry(tmp_path):
    origin = tmp_path / "native-origin"
    origin.mkdir()
    (origin / "fatebridge").mkdir()
    (origin / "fatebridge/__init__.py").write_text(
        "raise RuntimeError('UNFROZEN_NATIVE_CWD_PACKAGE_IMPORTED')\n"
    )
    (origin / "sitecustomize.py").write_text(
        "raise RuntimeError('UNFROZEN_NATIVE_CWD_SITECUSTOMIZE_IMPORTED')\n"
    )
    config = settings(
        evaluator.command_for(
            "not-executed",
            ROOT,
            tmp_path,
            {"scenario": "onda-xingpan"},
            native_selection=capture_selection({}),
            native_working_directory=origin,
        )
    )
    assert config["mcp_servers.fatebridge.args"][-1] == str(
        ROOT / "src/fatebridge/mcp_server.py"
    )
    prefix = "mcp_servers.fatebridge.env."
    env = {k[len(prefix) :]: v for k, v in config.items() if k.startswith(prefix)}
    log = tmp_path / "server-stderr.log"
    async with Client(
        StdioTransport(
            command=config["mcp_servers.fatebridge.command"],
            args=config["mcp_servers.fatebridge.args"],
            cwd=config["mcp_servers.fatebridge.cwd"],
            env=env,
            log_file=log,
        )
    ) as client:
        assert "human_design" in {t.name for t in await client.list_tools()}
    assert "UNFROZEN_NATIVE_CWD" not in log.read_text()
