"""Diagnostics and starter-projection schema checks for Codex integration."""

import shlex
import sys
from pathlib import Path

import pytest

from fatebridge import cli
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.core.schema_cache import model_schema
from fatebridge.diagnostics import (
    _probe_stdio,
    _StdioProbeError,
    diagnose,
    resolve_codex_cli,
)
from fatebridge.services.tool_catalog import CATALOG


def test_doctor_real_stdio_and_invalid_family() -> None:
    result = diagnose(mcp=True, family="bazi")
    assert result["ok"], result
    assert result["mcp"]["tool_count"] == result["mcp_tool_count"]
    assert result["mcp"]["scope"] == "initialize, tools/list, discover_tools"
    assert Path(result["codex"]["config"]["command"]).is_absolute()
    empty = diagnose(family="missing-family")
    assert not empty["ok"] and empty["issues"][0]["code"] == "unknown_family"


@pytest.mark.asyncio
async def test_doctor_keeps_the_child_startup_failure_and_stage() -> None:
    with pytest.raises(_StdioProbeError) as caught:
        await _probe_stdio({"FATEBRIDGE_MCP_FAMILIES": "missing-family"})
    details = caught.value.details
    assert details["stage"] == "initialize"
    assert details["error_type"]
    assert "Traceback" in details["server_stderr"]
    assert len(details["server_stderr"]) <= 8192


def test_doctor_returns_structured_stdio_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(env):
        raise _StdioProbeError("tools/list", OSError("probe failed"), "child stderr")

    monkeypatch.setattr("fatebridge.diagnostics._probe_stdio", fail)
    result = diagnose(mcp=True, family="bazi")
    assert not result["ok"]
    assert result["mcp"]["stage"] == "tools/list"
    assert result["mcp"]["error_type"] == "OSError"
    assert result["mcp"]["error"] == "probe failed"
    assert result["mcp"]["server_stderr"] == "child stderr"


def test_doctor_checks_active_dependency_markers_and_skips_unselected_extras(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fatebridge.diagnostics.importlib.metadata.requires",
        lambda _: [
            "fastmcp>=3.4.2; python_version >= '3.10'",
            "absent-platform-package; sys_platform == 'imaginary'",
            "absent-dev-package; extra == 'dev'",
        ],
    )
    result = diagnose()
    assert result["ok"]
    assert set(result["dependencies"]) == {"fastmcp"}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable bit")
def test_doctor_prefers_running_desktop_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desktop = tmp_path / "Desktop CLI" / "codex"
    desktop.parent.mkdir()
    desktop.write_text("#!/bin/sh\nexit 0\n")
    desktop.chmod(0o755)
    monkeypatch.setenv("CODEX_CLI_PATH", str(desktop))
    monkeypatch.setattr("fatebridge.diagnostics.shutil.which", lambda _: "/older/codex")
    result = diagnose()
    assert result["codex"]["cli"]["source"] == "desktop"
    assert shlex.split(result["codex"]["add_command"])[0] == str(desktop)
    assert result["codex"]["cli"]["path_cli"] == "/older/codex"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable bit")
def test_nonexecutable_desktop_cli_falls_back_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    desktop = tmp_path / "codex"
    desktop.touch(mode=0o644)
    monkeypatch.setenv("CODEX_CLI_PATH", str(desktop))
    monkeypatch.setattr(
        "fatebridge.diagnostics.shutil.which", lambda _: "/terminal/codex"
    )
    assert resolve_codex_cli()["path"] == "/terminal/codex"


def _schema_has_field_path(schema: dict, path: str) -> bool:
    defs = schema.get("$defs", {})

    def resolve(node):
        seen = set()
        while isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if not ref.startswith("#/$defs/") or ref in seen:
                    break
                seen.add(ref)
                node = defs.get(ref.removeprefix("#/$defs/"), {})
                continue
            for branch in ("anyOf", "oneOf", "allOf"):
                if branch in node:
                    opts = [
                        o
                        for o in node[branch]
                        if isinstance(o, dict) and o.get("type") != "null"
                    ]
                    obj_opts = [
                        o
                        for o in opts
                        if o.get("type") == "object" or "properties" in o or "$ref" in o
                    ]
                    chosen = obj_opts[0] if obj_opts else (opts[0] if opts else None)
                    if chosen is not None and chosen is not node:
                        node = chosen
                        break
            else:
                break
        return node if isinstance(node, dict) else {}

    node = resolve(schema)
    for part in path.split("."):
        node = resolve(node)
        props = node.get("properties")
        if isinstance(props, dict) and part in props:
            node = resolve(props[part])
            continue
        addl = node.get("additionalProperties")
        if addl is True:
            return True
        if isinstance(addl, dict):
            if addl.get("$ref") == "#/$defs/JsonValue":
                return True
            node = resolve(addl)
            continue
        if node.get("type") == "object" and "properties" not in node:
            return True
        return False
    return True


def test_published_starter_projection_is_valid_against_output_schemas() -> None:
    parser = cli.build_parser()
    starter_specs = [spec for spec in CATALOG if suggested_fields(spec) is not None]
    for spec in starter_specs:
        example = example_input(spec)
        spec.request_model.model_validate(example)
        command = shlex.split(cli._cli_example(spec, example))[1:]
        parsed = parser.parse_args(command)
        assert parsed._spec.name == spec.name
        schema = model_schema(spec.output_model)
        for field in suggested_fields(spec):
            assert _schema_has_field_path(schema, field), (spec.name, field)
