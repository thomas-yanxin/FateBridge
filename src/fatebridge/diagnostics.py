"""Read-only installation and real stdio diagnostics for agent onboarding."""

import asyncio
import importlib.metadata
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from packaging.requirements import Requirement
from typing_extensions import NotRequired, TypedDict

from fatebridge import __version__
from fatebridge.application.discovery import select_mcp_specs
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.core.ephemeris_installation import (
    FENGSHUI_PROFILE,
    HUMAN_DESIGN_PROFILE,
    fengshui_file_status,
    human_design_file_status,
    user_ephemeris_dir,
)
from fatebridge.core.ephemeris_paths import ephemeris_search_directories
from fatebridge.core.ephemeris_runtime import effective_ephemeris_search_path
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.runtime import load_runtime_env

STDIO_CALL_TIMEOUT_SECONDS = 30
STDIO_PROBE_TIMEOUT_SECONDS = 40
STDIO_ERROR_MESSAGE_CHARS = 2048
STDIO_LOG_TAIL_BYTES = 8192


class CodexCliResolution(TypedDict):
    path: str
    source: Literal["desktop", "running_desktop", "PATH", "not_installed"]
    path_cli: str


class DependencyStatus(TypedDict):
    ok: bool
    version: NotRequired[str]


class StdioProbeResult(TypedDict):
    ok: bool
    scope: str
    tool_count: int
    tools_wire_bytes: int
    summary_bytes: int


StdioStage = Literal["initialize", "tools/list", "discover_tools", "shutdown"]


class StdioFailureDetails(TypedDict):
    stage: StdioStage
    error_type: str
    error: str
    server_stderr: str


def resolve_codex_cli() -> CodexCliResolution:
    """Prefer the running desktop's CLI to an unrelated PATH installation."""
    desktop = os.getenv("CODEX_CLI_PATH")
    terminal = shutil.which("codex")
    if desktop and Path(desktop).is_file() and os.access(desktop, os.X_OK):
        return {"path": desktop, "source": "desktop", "path_cli": terminal or ""}
    if (
        not desktop
        and os.getenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE") == "Codex Desktop"
    ):
        running = _running_desktop_cli()
        if running:
            return {
                "path": running,
                "source": "running_desktop",
                "path_cli": terminal or "",
            }
    return {
        "path": terminal or "codex",
        "source": "PATH" if terminal else "not_installed",
        "path_cli": terminal or "",
    }


def _running_desktop_cli() -> str | None:
    """Discover a unique actual macOS app CLI; process arguments are never read."""
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["ps", "-axo", "comm"], capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    candidates = {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith("/codex")
        and ".app/Contents/" in line
        and Path(line.strip()).is_file()
        and os.access(line.strip(), os.X_OK)
    }
    # note (desktop): Fall back to PATH if more than one app is active.
    return next(iter(candidates)) if len(candidates) == 1 else None


class _StdioProbeError(RuntimeError):
    def __init__(self, stage: StdioStage, cause: Exception, stderr: str) -> None:
        super().__init__(str(cause))
        self.details: StdioFailureDetails = {
            "stage": stage,
            "error_type": type(cause).__name__,
            "error": str(cause)[:STDIO_ERROR_MESSAGE_CHARS],
            "server_stderr": stderr,
        }


async def _probe_stdio(env: dict[str, str]) -> StdioProbeResult:
    # note (installed entry): Launch outside the checkout to exercise installed imports and data.
    with tempfile.TemporaryDirectory(prefix="fatebridge-doctor-") as directory:
        with tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace"
        ) as log:
            transport = StdioTransport(
                command=sys.executable,
                args=["-X", "utf8", "-m", "fatebridge.mcp_server"],
                env=env,
                cwd=directory,
                log_file=log,
                keep_alive=False,
            )
            stage: StdioStage = "initialize"
            try:
                async with Client(
                    transport, timeout=STDIO_CALL_TIMEOUT_SECONDS
                ) as client:
                    stage = "tools/list"
                    tools = await client.list_tools()
                    stage = "discover_tools"
                    summary = await client.call_tool("discover_tools", {})
                    catalog = summary.structured_content
                    assert isinstance(catalog, dict)
                    summary_text = json.dumps(catalog, ensure_ascii=False)
                    names = {tool.name for tool in tools}
                    if not catalog.get("tools"):
                        raise RuntimeError("MCP discover_tools returned no tools")
                    expected = {"discover_tools", "run_calculation"}
                    if names != expected:
                        raise RuntimeError("MCP catalog and tools/list disagree")
                    output: StdioProbeResult = {
                        "ok": True,
                        "scope": "initialize, tools/list, discover_tools",
                        "tool_count": len(tools),
                        "tools_wire_bytes": len(
                            json.dumps(
                                [
                                    t.model_dump(mode="json", by_alias=True)
                                    for t in tools
                                ],
                                ensure_ascii=False,
                            ).encode()
                        ),
                        "summary_bytes": len(summary_text.encode()),
                    }
                    stage = "shutdown"
                return output
            except Exception as exc:
                # note (diagnostics): Report the stage and a bounded tail of child stderr.
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - STDIO_LOG_TAIL_BYTES))
                raise _StdioProbeError(stage, exc, log.read()) from exc


def diagnose(
    *,
    mcp: bool = False,
    family: str | None = None,
) -> ServiceResult:
    if mcp:
        load_runtime_env()
    family = family if family is not None else os.getenv("FATEBRIDGE_MCP_FAMILIES", "")
    try:
        selected = select_mcp_specs(
            CATALOG,
            family=family or None,
        )
    except ParameterError as exc:
        return {"ok": False, **exc.as_result()}
    env = {"FATEBRIDGE_MCP_FAMILIES": family}
    if archive_dir := os.getenv("FATEBRIDGE_DE441_DIR"):
        env["FATEBRIDGE_DE441_DIR"] = archive_dir
    dependencies: dict[str, DependencyStatus] = {}
    for dependency in importlib.metadata.requires("fatebridge") or []:
        requirement = Requirement(dependency)
        # note (markers): Include active platform dependencies and exclude unselected extras.
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        try:
            version = importlib.metadata.version(requirement.name)
            dependencies[requirement.name] = {
                "version": version,
                "ok": version in requirement.specifier,
            }
        except importlib.metadata.PackageNotFoundError:
            dependencies[requirement.name] = {"ok": False}
    codex_cli = resolve_codex_cli()
    args = [codex_cli["path"], "mcp", "add", "fatebridge"]
    for key, value in env.items():
        args.extend(["--env", f"{key}={value}"])
    args.extend(["--", sys.executable, "-m", "fatebridge.mcp_server"])
    output: ServiceResult = {
        "ok": all(status["ok"] for status in dependencies.values()),
        "version": __version__,
        "python": platform.python_version(),
        "executable": sys.executable,
        "package_path": str(Path(__file__).parent),
        "dependencies": dependencies,
        "mcp_tool_count": 2 if selected else 0,
        "mcp_capability_count": len(selected),
        "codex": {
            "cli": codex_cli,
            "add_command": shlex.join(args),
            "config": {
                "command": sys.executable,
                "args": ["-m", "fatebridge.mcp_server"],
                "env": env,
            },
            "note": "诊断不会修改 Codex 配置；注册后在新聊天中检查工具是否可见。",
        },
        "checks_scope": "installed package and dependency versions",
    }
    if not selected:
        output["ok"] = False
        output["error"] = "未找到所选分类的公开工具，请调整 --family"
    elif mcp and output["ok"]:
        try:
            output["mcp"] = asyncio.run(
                asyncio.wait_for(_probe_stdio(env), timeout=STDIO_PROBE_TIMEOUT_SECONDS)
            )
        except Exception as exc:
            output["ok"] = False
            output["mcp"] = {
                "ok": False,
                "error_type": type(exc).__name__,
                "hint": "检查解释器、依赖和 MCP 分类；用同一绝对路径启动进程复核日志。",
            }
            if isinstance(exc, _StdioProbeError):
                output["mcp"].update(exc.details)
    has_fengshui = any(spec.family == "fengshui" for spec in selected)
    has_human_design = any(spec.name == "human_design" for spec in selected)
    if has_fengshui or has_human_design:
        active = effective_ephemeris_search_path()
    else:
        active = None
    if has_fengshui:
        output["fengshui_calendar"] = {
            "active_search_path": active,
            "active_directories": [
                fengshui_file_status(item)
                for item in ephemeris_search_directories(active)
            ],
            "user_cache": fengshui_file_status(user_ephemeris_dir()),
            "setup_argv": [
                sys.executable,
                "-m",
                "fatebridge.fetch_ephe",
                "--profile",
                FENGSHUI_PROFILE,
            ],
            "setup_command": f"{shlex.quote(sys.executable)} -m fatebridge.fetch_ephe --profile fengshui_calendar",
            "astronomical_acceptance": "not_run_by_doctor; file identity does not certify one-second TT accuracy",
            "scope": "read_only_data_readiness; doctor ok describes package/dependencies/protocol, not full Feng Shui precision",
        }
    if has_human_design:
        setup = [
            sys.executable,
            "-m",
            "fatebridge.fetch_ephe",
            "--profile",
            HUMAN_DESIGN_PROFILE,
        ]
        output["human_design"] = {
            "active_search_path": active,
            "active_directories": [
                human_design_file_status(item)
                for item in ephemeris_search_directories(active)
            ],
            "user_cache": human_design_file_status(user_ephemeris_dir()),
            "setup_argv": setup,
            "setup_command": shlex.join(setup),
            "astronomical_acceptance": "not_run_by_doctor; file identity does not certify positions, Design roots or cycle contacts",
            "scope": "read_only_data_readiness; doctor ok describes package/dependencies/protocol, not full Human Design acceptance",
        }
    return output
