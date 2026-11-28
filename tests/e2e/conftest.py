"""Shared pytest fixtures and opaque-box surface callers for FateBridge E2E tests.

Strictly interacts with FateBridge through public entrypoints (`fatebridge`,
`fatebridge.api:app`, `fatebridge.mcp_server`, `fatebridge.cli`) and shared
test helpers (`tests/support/transports.py`, `tests/fixtures/surface_payloads.py`)
without importing internal core, application, or service modules.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.support.transports import AS_OF, business, cached_mcp_app

BLOAT_KEYS: frozenset[str] = frozenset(
    {"rule_trace", "source_citations", "source_catalog", "conventions"}
)

REPO_ROOT = Path(__file__).resolve().parents[2]

AUGMENTED_TOOL_INPUTS: dict[str, dict[str, Any]] = {
    "ipip_big_five": REST_POST_CASES["/api/psychometrics/ipip-big-five"](),
    "knowledge_read": {"domain": "human_design", "category": "lines", "key": "1.1"},
    "knowledge_catalog": {},
}

EXTRA_DOMAIN_INPUTS: dict[str, dict[str, Any]] = {
    "ipip_big_five_list": {"action": "list_items"},
    "knowledge_read_numerology": {
        "domain": "heluo",
        "category": "line_texts",
        "key": "乾為天:1",
    },
    "fengshui_monthly_stars_instant": {
        "query_at": "2026-10-12T12:00:00+08:00",
        "include_daily_hourly": True,
    },
}


@dataclass(frozen=True, slots=True)
class SurfaceOutcome:
    """Normalized response envelope across Python, MCP, REST, and CLI surfaces."""

    ok: bool
    status_code: int | None
    payload: dict[str, Any]
    exit_code: int | None = None
    raw_stdout: str | None = None
    raw_stderr: str | None = None


def strip_run_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of payload without top-level `run_metadata`."""
    return copy.deepcopy(business(payload))


def find_bloat_keys(obj: Any, prefix: str = "") -> list[str]:
    """Recursively collect dotted paths of any legacy audit bloat keys."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_str = str(key)
            path = f"{prefix}.{key_str}" if prefix else key_str
            if key_str in BLOAT_KEYS:
                hits.append(path)
            hits.extend(find_bloat_keys(value, path))
    elif isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            hits.extend(find_bloat_keys(item, f"{prefix}[{index}]"))
    return hits


def has_dotted_path(obj: Any, dotted_path: str) -> bool:
    """Return True if a dotted path (with optional `*` wildcards) resolves in obj."""
    segments = [part for part in dotted_path.split(".") if part]
    return bool(segments) and _has_segments(obj, segments)


def _has_segments(current: Any, segments: Sequence[str]) -> bool:
    if not segments:
        return True
    head, tail = segments[0], segments[1:]
    if head == "*":
        if isinstance(current, list):
            return any(_has_segments(item, tail) for item in current)
        if isinstance(current, dict):
            return any(_has_segments(value, tail) for value in current.values())
        return False
    return (
        isinstance(current, dict)
        and head in current
        and _has_segments(current[head], tail)
    )


def assert_dotted_path_restored(
    default_obj: Any,
    included_obj: Any,
    full_obj: Any,
    dotted_path: str,
) -> None:
    """Assert dotted_path is present in full_obj, omitted in default_obj, and restored in included_obj."""
    assert has_dotted_path(full_obj, dotted_path), f"Expected {dotted_path!r} in full"
    assert not has_dotted_path(
        default_obj, dotted_path
    ), f"Expected {dotted_path!r} omitted from default"
    segments = [part for part in dotted_path.split(".") if part]
    assert _assert_segments_restored(
        included_obj, full_obj, segments, dotted_path
    ), f"Expected {dotted_path!r} restored in included payload"


def _assert_segments_restored(
    inc_obj: Any,
    full_obj: Any,
    segments: Sequence[str],
    full_path: str,
) -> bool:
    if not segments:
        return True
    head, tail = segments[0], segments[1:]
    if head == "*":
        if isinstance(full_obj, list):
            assert isinstance(inc_obj, list) and len(inc_obj) == len(full_obj)
            matched = False
            for inc_item, full_item in zip(inc_obj, full_obj):
                if not tail or _has_segments(full_item, tail):
                    assert _assert_segments_restored(
                        inc_item, full_item, tail, full_path
                    )
                    matched = True
            return matched
        if isinstance(full_obj, dict):
            assert isinstance(inc_obj, dict)
            matched = False
            for key, full_val in full_obj.items():
                if not tail or _has_segments(full_val, tail):
                    assert key in inc_obj
                    assert _assert_segments_restored(
                        inc_obj[key], full_val, tail, full_path
                    )
                    matched = True
            return matched
        return False
    if isinstance(full_obj, dict) and head in full_obj:
        if not tail or _has_segments(full_obj[head], tail):
            assert isinstance(inc_obj, dict) and head in inc_obj
            return _assert_segments_restored(
                inc_obj[head], full_obj[head], tail, full_path
            )
    return False


def assert_isomorphic_subset(
    subset_obj: Any,
    full_obj: Any,
    path: str = "",
) -> None:
    """Assert every key/value in subset_obj exists identically in full_obj (ignoring top-level run_metadata)."""
    if isinstance(subset_obj, dict):
        assert isinstance(full_obj, dict), f"Type mismatch at {path or '<root>'}"
        if path == "":
            sub_biz = {k for k in subset_obj if k != "run_metadata"}
            full_biz = {k for k in full_obj if k != "run_metadata"}
            if not sub_biz and full_biz:
                raise AssertionError(
                    "Empty dict subset at <root> while full is non-empty"
                )
        for key, sub_val in subset_obj.items():
            if path == "" and key == "run_metadata":
                continue
            child_path = f"{path}.{key}" if path else str(key)
            assert key in full_obj, f"Missing key {child_path!r} in full payload"
            assert_isomorphic_subset(sub_val, full_obj[key], child_path)
        return
    if isinstance(subset_obj, list):
        assert isinstance(full_obj, list) and len(subset_obj) == len(
            full_obj
        ), f"List mismatch at {path or '<root>'}"
        for index, (sub_item, full_item) in enumerate(zip(subset_obj, full_obj)):
            assert_isomorphic_subset(sub_item, full_item, f"{path}[{index}]")
        return
    assert (type(subset_obj) is bool) == (
        type(full_obj) is bool
    ), f"Bool mismatch at {path or '<root>'}"
    assert (
        subset_obj == full_obj
    ), f"Value mismatch at {path or '<root>'}: {subset_obj!r} != {full_obj!r}"


def extract_error_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract normalized issue dictionaries from REST/MCP/CLI/Python error envelopes."""
    issues = payload.get("issues")
    if isinstance(issues, list):
        return [dict(item) for item in issues if isinstance(item, dict)]
    detail = payload.get("detail")
    if isinstance(detail, dict) and isinstance(detail.get("issues"), list):
        return [dict(item) for item in detail["issues"] if isinstance(item, dict)]
    return []


@lru_cache(maxsize=1)
def _cached_full_specs() -> dict[str, dict[str, Any]]:
    import fatebridge

    summary = fatebridge.discover(detail="summary")
    specs: dict[str, dict[str, Any]] = {}
    for family in sorted(summary.get("families", {})):
        manifest = fatebridge.discover(
            family=family,
            detail="full",
            include_output_schema=True,
        )
        for record in manifest.get("tools", []):
            specs[record["tool"]] = record
    return specs


def get_all_full_specs() -> dict[str, dict[str, Any]]:
    """Fetch and cache full discovery records (with output schemas) for all tools."""
    return dict(_cached_full_specs())


def augmented_inputs_for(
    tool_name: str, specs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Return valid inputs for any tool, supplementing minimal discovery examples."""
    if tool_name in AUGMENTED_TOOL_INPUTS:
        return copy.deepcopy(AUGMENTED_TOOL_INPUTS[tool_name])
    example = specs[tool_name].get("example_input")
    assert isinstance(example, dict), f"Tool {tool_name!r} missing dict example_input"
    return copy.deepcopy(example)


def rest_path_for(tool_name: str, specs: dict[str, dict[str, Any]]) -> str:
    """Return the discovered REST route path for a tool."""
    rest_path = specs[tool_name].get("surfaces", {}).get("rest")
    assert isinstance(rest_path, str) and rest_path.startswith("/")
    return rest_path


def call_python_run(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    as_of: str | None = AS_OF,
    include: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    **extra: Any,
) -> SurfaceOutcome:
    """Invoke `fatebridge.run` and normalize its dict outcome."""
    import fatebridge

    kwargs: dict[str, Any] = dict(extra)
    if as_of is not None:
        kwargs["as_of"] = as_of
    if include is not None:
        kwargs["include"] = list(include)
    if fields is not None:
        kwargs["fields"] = list(fields)
    result = fatebridge.run(tool, arguments, **kwargs)
    is_err = "error" in result
    status_code = result.get("status_code") if is_err else 200
    return SurfaceOutcome(
        ok=not is_err,
        status_code=int(status_code) if isinstance(status_code, int) else None,
        payload=result,
    )


async def call_mcp_tool(
    mcp_client: Client,
    name: str,
    args: dict[str, Any] | None = None,
) -> SurfaceOutcome:
    """Invoke an MCP meta-tool with `raise_on_error=False` and no hidden defaults."""
    result = await mcp_client.call_tool(name, args or {}, raise_on_error=False)
    payload: dict[str, Any]
    if result.structured_content is not None:
        payload = dict(result.structured_content)
    elif result.content:
        first_text = getattr(result.content[0], "text", None)
        if isinstance(first_text, str):
            try:
                parsed = json.loads(first_text)
                payload = parsed if isinstance(parsed, dict) else {"error": first_text}
            except json.JSONDecodeError:
                payload = {"error": first_text}
        else:
            payload = {"error": str(result.content[0])}
    else:
        payload = {}
    is_error = bool(result.is_error)
    status_code = payload.get("status_code") if is_error else 200
    return SurfaceOutcome(
        ok=not is_error,
        status_code=int(status_code) if isinstance(status_code, int) else None,
        payload=payload,
    )


def call_rest(
    rest_client: TestClient,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: Any = None,
    headers: dict[str, str] | None = None,
) -> SurfaceOutcome:
    """Invoke a REST GET/POST endpoint and normalize its JSON or text outcome."""
    if method.upper() == "GET":
        response = rest_client.get(path, params=params, headers=headers)
    else:
        response = rest_client.request(
            method.upper(),
            path,
            json={} if json_body is None else json_body,
            params=params,
            headers=headers,
        )
    try:
        parsed = response.json()
        payload = parsed if isinstance(parsed, dict) else {"data": parsed}
    except ValueError:
        payload = {"raw_text": response.text}
    return SurfaceOutcome(
        ok=200 <= response.status_code < 300,
        status_code=response.status_code,
        payload=payload,
    )


def _parse_cli_output(stdout: str, stderr: str) -> dict[str, Any]:
    stripped = stdout.strip()
    if stripped:
        try:
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else {"data": parsed}
        except json.JSONDecodeError:
            pass
    return {"raw_stdout": stdout, "raw_stderr": stderr}


def call_cli(
    args: Sequence[str],
    *,
    stdin_text: str | None = None,
    use_subprocess: bool = False,
    env: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> SurfaceOutcome:
    """Invoke FateBridge CLI in-process by default, or via subprocess for process-boundary tests."""
    if use_subprocess:
        proc = subprocess.run(
            [sys.executable, "-m", "fatebridge", *args],
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**(env or os.environ), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            timeout=timeout,
        )
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    else:
        from fatebridge.cli import run as cli_run

        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        orig_stdin = sys.stdin
        sys.stdin = io.StringIO(stdin_text or "")
        try:
            with (
                contextlib.redirect_stdout(stdout_buf),
                contextlib.redirect_stderr(stderr_buf),
            ):
                exit_code = cli_run(list(args))
        finally:
            sys.stdin = orig_stdin
        stdout, stderr = stdout_buf.getvalue(), stderr_buf.getvalue()

    payload = _parse_cli_output(stdout, stderr)
    ok = exit_code == 0
    status_code = 200 if ok else payload.get("status_code")
    return SurfaceOutcome(
        ok=ok,
        status_code=int(status_code) if isinstance(status_code, int) else None,
        payload=payload,
        exit_code=exit_code,
        raw_stdout=stdout,
        raw_stderr=stderr,
    )


def call_cli_tool(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    as_of: str | None = AS_OF,
    include: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    extra_flags: Sequence[str] = (),
    use_subprocess: bool = False,
) -> SurfaceOutcome:
    """Invoke a single CLI calculation subcommand via `--request-file -`."""
    cli_args: list[str] = [tool, "--request-file", "-"]
    if as_of is not None:
        cli_args.extend(["--as-of", as_of])
    if include is not None:
        cli_args.extend(["--include", *include])
    if fields is not None:
        cli_args.extend(["--fields", *fields])
    cli_args.extend(extra_flags)
    stdin_payload = json.dumps(
        {} if arguments is None else arguments, ensure_ascii=False
    )
    return call_cli(cli_args, stdin_text=stdin_payload, use_subprocess=use_subprocess)


@pytest.fixture(scope="session")
def e2e_as_of() -> str:
    """Canonical frozen UTC timestamp shared across E2E tests."""
    return AS_OF


@pytest.fixture(scope="session")
def all_tool_specs() -> dict[str, dict[str, Any]]:
    """All 91 public tool discovery records (detail='full', include_output_schema=True)."""
    return get_all_full_specs()


@pytest.fixture
def rest_client(rest: TestClient) -> TestClient:
    """Reuse shared `rest` fixture from `tests/support/transports.py`."""
    return rest


@pytest_asyncio.fixture
async def mcp_client() -> AsyncIterator[Client]:
    """In-process FastMCP client backed by shared cached MCP app."""
    async with Client(cached_mcp_app()) as client:
        yield client
