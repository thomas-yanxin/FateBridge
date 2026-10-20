"""Read-only installation and real stdio diagnostics for agent onboarding."""

import asyncio
import importlib.metadata
import json
import os
import platform
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fatebridge import __version__
from fatebridge.application.discovery import select_specs
from fatebridge.application.examples import example_input
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.runtime import load_runtime_env


def resolve_codex_cli() -> Dict[str, str]:
    """Prefer the running desktop's CLI to an unrelated PATH installation."""
    desktop = os.getenv("CODEX_CLI_PATH")
    terminal = shutil.which("codex")
    if desktop and Path(desktop).is_file() and os.access(desktop, os.X_OK):
        return {"path": desktop, "source": "desktop", "path_cli": terminal or ""}
    return {
        "path": terminal or "codex",
        "source": "PATH" if terminal else "not_installed",
        "path_cli": terminal or "",
    }


async def _probe_stdio(env: Dict[str, str]) -> Dict[str, Any]:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    # A GUI host need not launch in the checkout. Verify that installed imports
    # and package data work from an unrelated working directory as well.
    with tempfile.TemporaryDirectory(prefix="fatebridge-doctor-") as directory:
        with tempfile.TemporaryFile(mode="w+") as log:
            transport = StdioTransport(
                command=sys.executable,
                args=["-m", "fatebridge.mcp_server"],
                env=env,
                cwd=directory,
                log_file=log,
            )
            async with Client(transport, timeout=30) as client:
                tools = await client.list_tools()
                summary = await client.read_resource("fatebridge://catalog/summary")
                catalog = json.loads(summary[0].text)
                if {t.name for t in tools} != {t["tool"] for t in catalog["tools"]}:
                    raise RuntimeError("MCP catalog and tools/list disagree")
                output: Dict[str, Any] = {
                    "ok": True,
                    "scope": "initialize, tools/list, resources/read",
                    "tool_count": len(tools),
                    "tools_wire_bytes": len(
                        json.dumps(
                            [t.model_dump(mode="json", by_alias=True) for t in tools],
                            ensure_ascii=False,
                        ).encode()
                    ),
                    "summary_bytes": len(summary[0].text.encode()),
                }
                names = {tool.name for tool in tools}
                candidate = next(
                    (
                        (spec, example_input(spec))
                        for spec in CATALOG
                        if spec.mcp_name in names and example_input(spec) is not None
                    ),
                    None,
                )
                if candidate is not None:
                    spec, inputs = candidate
                    response = await client.call_tool(
                        spec.tool_name,
                        {
                            **(inputs or {}),
                            "fields": ["run_metadata"],
                            "strict_fields": True,
                        },
                        raise_on_error=False,
                    )
                    if response.is_error:
                        raise RuntimeError("MCP fictional smoke calculation failed")
                    receipt = response.structured_content["run_metadata"]
                    if receipt["tool_name"] != spec.run_metadata_name:
                        raise RuntimeError("MCP smoke receipt has wrong tool name")
                    output["smoke_tool"] = spec.tool_name
                    output["scope"] += ", one fictional calculation"
                return output


def diagnose(
    *,
    mcp: bool = False,
    family: Optional[str] = None,
    scenario: Optional[str] = None,
) -> Dict[str, Any]:
    if mcp:
        load_runtime_env()
    family = family if family is not None else os.getenv("FATEBRIDGE_MCP_FAMILIES", "")
    scenario = (
        scenario if scenario is not None else os.getenv("FATEBRIDGE_MCP_SCENARIOS", "")
    )
    try:
        selected = select_specs(
            CATALOG, family=family or None, scenario=scenario or None, surface="mcp"
        )
    except ParameterError as exc:
        return {"ok": False, **exc.as_result()}
    env = {"FATEBRIDGE_MCP_FAMILIES": family, "FATEBRIDGE_MCP_SCENARIOS": scenario}
    dependencies: Dict[str, Any] = {}
    for dependency in importlib.metadata.requires("fatebridge") or []:
        from packaging.requirements import Requirement

        requirement = Requirement(dependency)
        # Platform requirements are active on that platform; unselected extras
        # and other inactive markers must not enter the required dependency set.
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
    output: Dict[str, Any] = {
        "ok": all(item["ok"] for item in dependencies.values()),
        "version": __version__,
        "python": platform.python_version(),
        "executable": sys.executable,
        "package_path": str(Path(__file__).parent),
        "dependencies": dependencies,
        "mcp_tool_count": len(selected),
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
        output["error"] = "分类与场景交集为空，请调整 --family / --scenario"
    elif mcp and output["ok"]:
        try:
            output["mcp"] = asyncio.run(asyncio.wait_for(_probe_stdio(env), timeout=40))
        except Exception as exc:
            output["ok"] = False
            output["mcp"] = {
                "ok": False,
                "error_type": type(exc).__name__,
                "hint": "检查解释器、依赖和 MCP 分类/场景；用同一绝对路径启动进程复核日志。",
            }
    return output
