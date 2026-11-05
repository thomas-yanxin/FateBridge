"""Exact native selector parity and stage freezing, without invoking a model."""

import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

import scripts.evaluate_agent as evaluator
from fatebridge.validation.evaluation_environment import (
    METHOD,
    NATIVE_ENVIRONMENT_KEYS,
    capture_selection,
    load_selection,
    process_environment,
    selected_environment,
    selection_bytes,
    validate_selection,
    verify_stage_selection,
)

ROOT = Path(__file__).resolve().parents[1]
CASE = {
    "id": "native_data_case",
    "scenario": "onda-xingpan",
    "tool_scope": "complete",
    "capture_payloads": True,
    "prompt": "虚构工程核对。",
    "manual_review": ["按实际回执。"],
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


def settings(command):
    return {
        command[i + 1].split("=", 1)[0]: json.loads(command[i + 1].split("=", 1)[1])
        for i, token in enumerate(command[:-1])
        if token == "-c"
    }


def test_capture_roundtrip_preserves_unset_empty_and_exact_values_without_secrets(
    tmp_path,
):
    source = {
        "SE_EPHE_PATH": "/verified/path with spaces",
        "FATEBRIDGE_JPL_FILE": "",
        "OPENAI_API_KEY": "do-not-forward",
        "UNRELATED_TEST_SECRET": "hidden",
    }
    chosen = capture_selection(source)
    assert chosen == {k: source.get(k) for k in NATIVE_ENVIRONMENT_KEYS}
    raw = selection_bytes(chosen)
    path = tmp_path / "selectors.json"
    path.write_bytes(raw)
    loaded, original = load_selection(path, hashlib.sha256(raw).hexdigest())
    assert loaded == chosen and original == raw
    assert b"do-not-forward" not in raw and b"UNRELATED_TEST_SECRET" not in raw
    assert selected_environment(loaded) == {
        "SE_EPHE_PATH": source["SE_EPHE_PATH"],
        "FATEBRIDGE_JPL_FILE": "",
    }
    ambient = {**source, "FATEBRIDGE_SOLAR_TERM_MODEL": "later-ambient-mode"}
    actual = process_environment(loaded, ambient)
    assert "FATEBRIDGE_SOLAR_TERM_MODEL" not in actual
    assert (
        actual["OPENAI_API_KEY"] == "do-not-forward"
    )  # CLI authentication remains private.
    assert ambient["FATEBRIDGE_SOLAR_TERM_MODEL"] == "later-ambient-mode"


@pytest.mark.parametrize(
    "fault", ["extra_key", "missing_key", "boolean", "integer", "nul"]
)
def test_no_undeclared_or_unrepresentable_selector_is_accepted(fault):
    value = capture_selection({})
    if fault == "extra_key":
        value["OPENAI_API_KEY"] = "secret"
    elif fault == "missing_key":
        del value["SE_EPHE_PATH"]
    else:
        value["SE_EPHE_PATH"] = {"boolean": False, "integer": 1, "nul": "x\0y"}[fault]
    with pytest.raises(ValueError):
        validate_selection(value)


@pytest.mark.parametrize(
    "fault", ["changed_bytes", "unknown_method", "extra_metadata", "unknown_selector"]
)
def test_a_new_hash_cannot_legitimize_an_unknown_config_schema(tmp_path, fault):
    record = {"method_id": METHOD, "values": capture_selection({})}
    original = selection_bytes(record["values"])
    if fault == "unknown_method":
        record["method_id"] = "future_unreviewed_method"
    elif fault == "extra_metadata":
        record["all_accuracy_certified"] = True
    elif fault == "unknown_selector":
        record["values"]["UNRELATED_TEST_SECRET"] = "hidden"
    raw = json.dumps(record).encode()
    p = tmp_path / "bad.json"
    p.write_bytes(raw)
    expected = hashlib.sha256(original if fault == "changed_bytes" else raw).hexdigest()
    with pytest.raises(ValueError):
        load_selection(p, expected)


def test_run_case_clears_later_inherited_choices_and_keeps_exact_mcp_settings(
    monkeypatch, tmp_path
):
    chosen = capture_selection({"SE_EPHE_PATH": "/frozen/empty-directory"})
    monkeypatch.setenv("SE_EPHE_PATH", "/later/ambient-files")
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "/later/kernel.eph")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "later-mode")

    def prepare(workspace, source, case):
        (workspace / "AGENTS.md").write_text("test")

    monkeypatch.setattr(evaluator, "prepare_case_workspace", prepare)
    seen = []

    def process(command, **kwargs):
        seen.append((command, kwargs["env"]))
        target = tmp_path / "one"
        (target / "answer.txt").write_text("无需计算。")
        kwargs["stdout"].write(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "无需计算。"},
                }
            )
            + "\n"
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(evaluator.subprocess, "run", process)
    case = {
        "id": "one",
        "prompt": "无需计算。",
        "no_calculation": True,
        "allowed_tools": [],
        "manual_review": [],
    }
    result = evaluator.run_case(
        "unused-cli", case, tmp_path, 10, native_selection=chosen
    )
    assert result["mechanical_checks_passed"]
    command, env = seen[0]
    assert env["SE_EPHE_PATH"] == chosen["SE_EPHE_PATH"]
    assert "FATEBRIDGE_JPL_FILE" not in env and "FATEBRIDGE_SOLAR_TERM_MODEL" not in env
    config = settings(command)
    assert config["mcp_servers.fatebridge.env.SE_EPHE_PATH"] == chosen["SE_EPHE_PATH"]
    assert "mcp_servers.fatebridge.env.FATEBRIDGE_JPL_FILE" not in config
    assert os.environ["SE_EPHE_PATH"] == "/later/ambient-files"


@pytest.mark.asyncio
@pytest.mark.parametrize("empty", [False, True])
async def test_reference_and_constructed_model_mcp_use_one_frozen_selection(
    monkeypatch, tmp_path, empty
):
    selected_path = tmp_path / "empty" if empty else ROOT / "ephe"
    if empty:
        selected_path.mkdir()
    chosen = capture_selection({"SE_EPHE_PATH": str(selected_path)})
    # Every later ambient setting intentionally disagrees with the fixed input.
    monkeypatch.setenv("SE_EPHE_PATH", str(ROOT / "ephe" if empty else tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", "/not-an-actual-kernel.eph")
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "invalid")
    config = settings(
        evaluator.command_for(
            "not-executed", ROOT, tmp_path, CASE, native_selection=chosen
        )
    )
    await evaluator.prepare_references([CASE], tmp_path, ROOT, chosen)
    reference = json.loads(
        (tmp_path / "reference-payloads/native_data_case.json").read_text()
    )
    prefix = "mcp_servers.fatebridge.env."
    env = {k[len(prefix) :]: v for k, v in config.items() if k.startswith(prefix)}
    env["FATEBRIDGE_EVALUATION_LOG"] = str(tmp_path / "model-arm.jsonl")
    async with Client(
        StdioTransport(
            command=config["mcp_servers.fatebridge.command"],
            args=config["mcp_servers.fatebridge.args"],
            cwd=str(ROOT),
            env=env,
            log_file=tmp_path / "model-arm-stderr.log",
        )
    ) as client:
        response = await client.call_tool(
            "human_design",
            {
                **CASE["reference_request"]["arguments"],
                "fields": None,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            },
        )
    assert not response.is_error and not reference["is_error"]
    a, b = reference["structured_content"], response.structured_content
    for key in (
        "activations",
        "bodygraph",
        "design_solver",
        "cycle_summary",
        "ephemeris_source_summary",
    ):
        assert a[key] == b[key]
    assert a["calculation_policy"]["ephemeris_model"] == (
        "moshier" if empty else "swieph"
    )
    assert a["cycle_summary"]["status"] == (
        "partial" if empty else "computed_finite_search"
    )
    assert a["cycle_summary"]["bodies"][2]["contact_count"] == (0 if empty else 3)


@pytest.mark.parametrize("fault", ["missing_hash", "missing_path", "changed_bytes"])
def test_invalid_reused_selection_stops_before_cli_or_model(
    monkeypatch, tmp_path, fault
):
    raw = selection_bytes(capture_selection({}))
    path = tmp_path / "native.json"
    path.write_bytes(raw)
    args = ["evaluate_agent", "--output", str(tmp_path / "out")]
    if fault != "missing_path":
        args += ["--native-environment", str(path)]
    if fault != "missing_hash":
        args += ["--native-environment-sha256", "0" * 64]
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(
        "fatebridge.diagnostics.resolve_codex_cli",
        lambda: pytest.fail("Premature model lookup"),
    )
    with pytest.raises(SystemExit) as error:
        evaluator.main()
    assert error.value.code == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "fault", [None, "changed_stage", "changed_bytes", "missing_metadata", "legacy"]
)
def test_stage_binding_never_reconstructs_or_substitutes_a_selection(tmp_path, fault):
    prepared, run = tmp_path / "prepared", tmp_path / "model-run"
    prepared.mkdir()
    run.mkdir()
    raw = selection_bytes(capture_selection({"SE_EPHE_PATH": "/original/ephe"}))
    digest = hashlib.sha256(raw).hexdigest()
    for folder, name in [(prepared, "preparation.json"), (run, "report.json")]:
        (folder / "native-environment.json").write_bytes(raw)
        (folder / name).write_text(json.dumps({"native_environment_sha256": digest}))
    if fault == "changed_stage":
        changed = selection_bytes(
            capture_selection({"SE_EPHE_PATH": "/different/ephe"})
        )
        (run / "native-environment.json").write_bytes(changed)
        (run / "report.json").write_text(
            json.dumps(
                {"native_environment_sha256": hashlib.sha256(changed).hexdigest()}
            )
        )
    elif fault == "changed_bytes":
        (run / "native-environment.json").write_bytes(raw + b" ")
    elif fault == "missing_metadata":
        (run / "report.json").write_text("{}")
    elif fault == "legacy":
        (run / "report.json").write_text("{}")
        (prepared / "preparation.json").write_text("{}")
    if fault in {"changed_stage", "changed_bytes", "missing_metadata", "legacy"}:
        with pytest.raises(ValueError):
            verify_stage_selection(prepared, run)
    else:
        result = verify_stage_selection(prepared, run)
        assert result["stage_equivalence_verified"] is True
