"""Reusable opaque-box helpers and surface adapters for E2E tests.

Strictly interacts with FateBridge through public entrypoints and discovery
manifests (`fatebridge.discover`, `fatebridge.run`, FastMCP `Client`, FastAPI
`TestClient`, and CLI subprocesses) without importing internal modules.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_AS_OF = "2026-10-12T04:00:00Z"

BLOAT_KEYS: frozenset[str] = frozenset(
    {
        "rule_trace",
        "source_citations",
        "source_catalog",
        "conventions",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[2]

AUGMENTED_TOOL_INPUTS: dict[str, dict[str, Any]] = {
    "ipip_big_five": {
        "action": "score",
        "ratings": [3] * 50,
        "include_item_breakdown": True,
    },
    "knowledge_read": {
        "domain": "human_design",
        "category": "lines",
        "key": "1.1",
    },
    "knowledge_catalog": {},
}

EXTRA_DOMAIN_INPUTS: dict[str, dict[str, Any]] = {
    "knowledge_read_numerology": {
        "domain": "heluo",
        "category": "line_texts",
        "key": "乾為天:1",
    },
    "ipip_big_five_list": {
        "action": "list_items",
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


def strip_run_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of payload without top-level `run_metadata`."""
    cleaned = copy.deepcopy(payload)
    cleaned.pop("run_metadata", None)
    return cleaned


def has_dotted_path(obj: Any, dotted_path: str) -> bool:
    """Return True if a dotted path (with optional `*` wildcards) resolves in obj."""
    segments = [part for part in dotted_path.split(".") if part]
    if not segments:
        return False
    return _has_segments(obj, segments)


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
    if isinstance(current, dict) and head in current:
        return _has_segments(current[head], tail)
    return False


def has_all_dotted_paths(obj: Any, dotted_path: str) -> bool:
    """Return True if a dotted path resolves across every branch of any `*` wildcard."""
    segments = [part for part in dotted_path.split(".") if part]
    if not segments:
        return False
    return _has_all_segments(obj, segments)


def _has_all_segments(current: Any, segments: Sequence[str]) -> bool:
    if not segments:
        return True
    head, tail = segments[0], segments[1:]
    if head == "*":
        if isinstance(current, list):
            return bool(current) and all(
                _has_all_segments(item, tail) for item in current
            )
        if isinstance(current, dict):
            return bool(current) and all(
                _has_all_segments(value, tail) for value in current.values()
            )
        return False
    if isinstance(current, dict) and head in current:
        return _has_all_segments(current[head], tail)
    return False


def assert_dotted_path_restored(
    default_obj: Any,
    included_obj: Any,
    full_obj: Any,
    dotted_path: str,
) -> None:
    """Assert every branch of dotted_path in full_obj is omitted in default_obj and restored in included_obj."""
    assert has_dotted_path(
        full_obj, dotted_path
    ), f"Expected {dotted_path!r} to exist in full payload"
    assert not has_dotted_path(
        default_obj, dotted_path
    ), f"Expected {dotted_path!r} to be omitted from default payload"
    segments = [part for part in dotted_path.split(".") if part]
    matched = _assert_segments_restored(included_obj, full_obj, segments, dotted_path)
    assert matched, f"Expected {dotted_path!r} to be restored in included payload"


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
            assert isinstance(inc_obj, list) and len(inc_obj) == len(full_obj), (
                f"List length mismatch restoring {full_path!r}: "
                f"included={len(inc_obj) if isinstance(inc_obj, list) else type(inc_obj).__name__} "
                f"!= full={len(full_obj)}"
            )
            any_matched = False
            for inc_item, full_item in zip(inc_obj, full_obj):
                if not tail or _has_segments(full_item, tail):
                    assert _assert_segments_restored(
                        inc_item, full_item, tail, full_path
                    )
                    any_matched = True
            return any_matched
        if isinstance(full_obj, dict):
            assert isinstance(
                inc_obj, dict
            ), f"Expected dict restoring {full_path!r}, got {type(inc_obj).__name__}"
            any_matched = False
            for key, full_val in full_obj.items():
                if not tail or _has_segments(full_val, tail):
                    assert (
                        key in inc_obj
                    ), f"Restored payload missing wildcard key {key!r} for {full_path!r}"
                    assert _assert_segments_restored(
                        inc_obj[key], full_val, tail, full_path
                    )
                    any_matched = True
            return any_matched
        return False
    if isinstance(full_obj, dict) and head in full_obj:
        if not tail or _has_segments(full_obj[head], tail):
            assert (
                isinstance(inc_obj, dict) and head in inc_obj
            ), f"Restored payload missing segment {head!r} for {full_path!r}"
            return _assert_segments_restored(
                inc_obj[head], full_obj[head], tail, full_path
            )
    return False


def assert_isomorphic_subset(
    subset_obj: Any,
    full_obj: Any,
    path: str = "",
) -> None:
    """Assert that every key/value in subset_obj exists identically in full_obj.

    Top-level `run_metadata` is ignored at `path == ""` because run IDs,
    timestamps, durations, and `omitted_fields` naturally differ across calls.
    """
    if isinstance(subset_obj, dict):
        assert isinstance(full_obj, dict), (
            f"Type mismatch at {path or '<root>'}: "
            f"expected dict, got {type(full_obj).__name__}"
        )
        if path == "":
            sub_biz_keys = {k for k in subset_obj if k != "run_metadata"}
            full_biz_keys = {k for k in full_obj if k != "run_metadata"}
            if not sub_biz_keys and full_biz_keys:
                raise AssertionError(
                    "Empty dict subset at <root> while full payload is non-empty"
                )
        for key, sub_val in subset_obj.items():
            if path == "" and key == "run_metadata":
                continue
            child_path = f"{path}.{key}" if path else str(key)
            assert key in full_obj, f"Missing key {child_path!r} in full payload"
            assert_isomorphic_subset(sub_val, full_obj[key], child_path)
        return

    if isinstance(subset_obj, list):
        assert isinstance(full_obj, list), (
            f"Type mismatch at {path or '<root>'}: "
            f"expected list, got {type(full_obj).__name__}"
        )
        assert len(subset_obj) == len(full_obj), (
            f"List length mismatch at {path or '<root>'}: "
            f"subset={len(subset_obj)} != full={len(full_obj)}"
        )
        for index, (sub_item, full_item) in enumerate(zip(subset_obj, full_obj)):
            assert_isomorphic_subset(sub_item, full_item, f"{path}[{index}]")
        return

    assert (type(subset_obj) is bool) == (type(full_obj) is bool), (
        f"Boolean/scalar type mismatch at {path or '<root>'}: "
        f"{subset_obj!r} ({type(subset_obj).__name__}) vs "
        f"{full_obj!r} ({type(full_obj).__name__})"
    )
    assert subset_obj == full_obj, (
        f"Scalar value mismatch at {path or '<root>'}: "
        f"subset={subset_obj!r} != full={full_obj!r}"
    )


@lru_cache(maxsize=1)
def _cached_full_specs() -> dict[str, dict[str, Any]]:
    import fatebridge

    summary = fatebridge.discover(detail="summary")
    families = summary.get("families", {})
    specs: dict[str, dict[str, Any]] = {}
    for family in sorted(families):
        manifest = fatebridge.discover(
            family=family,
            detail="full",
            include_output_schema=True,
        )
        for record in manifest.get("tools", []):
            tool_name = record["tool"]
            specs[tool_name] = record
    return specs


def get_all_full_specs() -> dict[str, dict[str, Any]]:
    """Fetch and cache full discovery records (with output schemas) for all tools."""
    return dict(_cached_full_specs())


def augmented_inputs_for(
    tool_name: str,
    specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return a fresh valid input payload for any tool, using augmented inputs."""
    if tool_name in AUGMENTED_TOOL_INPUTS:
        return copy.deepcopy(AUGMENTED_TOOL_INPUTS[tool_name])
    record = specs[tool_name]
    example = record.get("example_input")
    assert isinstance(
        example, dict
    ), f"Tool {tool_name!r} has no dict example_input in discovery manifest"
    return copy.deepcopy(example)


def rest_path_for(tool_name: str, specs: dict[str, dict[str, Any]]) -> str:
    """Return the discovered REST route path for a tool."""
    surfaces = specs[tool_name].get("surfaces", {})
    rest_path = surfaces.get("rest")
    assert isinstance(rest_path, str) and rest_path.startswith(
        "/"
    ), f"Tool {tool_name!r} does not expose a REST path: {surfaces!r}"
    return rest_path


def call_python_run(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    as_of: str | None = DEFAULT_AS_OF,
    include: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    **extra: Any,
) -> SurfaceOutcome:
    """Invoke `fatebridge.run` and normalize its dict outcome.

    Exceptions raised directly by `fatebridge.run` (e.g., unknown tool,
    removed parameters, or invalid `include`/`fields`) propagate so callers can
    assert exception behavior explicitly.
    """
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
    mcp_client: Any,
    name: str,
    args: dict[str, Any] | None = None,
) -> SurfaceOutcome:
    """Invoke an MCP meta-tool with `raise_on_error=False`."""
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


def call_rest_post(
    rest_client: Any,
    path: str,
    json_body: dict[str, Any] | None = None,
    *,
    params: Any = None,
    headers: dict[str, str] | None = None,
) -> SurfaceOutcome:
    """Invoke a REST POST endpoint and normalize its JSON outcome."""
    response = rest_client.post(
        path,
        json={} if json_body is None else json_body,
        params=params,
        headers=headers,
    )
    payload = _parse_rest_json(response)
    return SurfaceOutcome(
        ok=200 <= response.status_code < 300,
        status_code=response.status_code,
        payload=payload,
    )


def call_rest_get(
    rest_client: Any,
    path: str,
    *,
    params: Any = None,
    headers: dict[str, str] | None = None,
) -> SurfaceOutcome:
    """Invoke a REST GET endpoint and normalize its JSON outcome."""
    response = rest_client.get(path, params=params, headers=headers)
    payload = _parse_rest_json(response)
    return SurfaceOutcome(
        ok=200 <= response.status_code < 300,
        status_code=response.status_code,
        payload=payload,
    )


def _parse_rest_json(response: Any) -> dict[str, Any]:
    try:
        parsed = response.json()
    except ValueError:
        return {"raw_text": response.text}
    if isinstance(parsed, dict):
        return parsed
    return {"data": parsed}


def call_cli(
    args: Sequence[str],
    *,
    stdin_text: str | None = None,
    timeout: float = 60.0,
) -> SurfaceOutcome:
    """Execute `python -m fatebridge ...` in a UTF-8 subprocess."""
    proc = subprocess.run(
        [sys.executable, "-m", "fatebridge", *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        timeout=timeout,
    )
    stdout = proc.stdout.strip()
    payload: dict[str, Any]
    if stdout:
        try:
            parsed = json.loads(stdout)
            payload = parsed if isinstance(parsed, dict) else {"data": parsed}
        except json.JSONDecodeError:
            payload = {"raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
    else:
        payload = {"raw_stdout": proc.stdout, "raw_stderr": proc.stderr}

    ok = proc.returncode == 0
    status_code = 200 if ok else payload.get("status_code")
    return SurfaceOutcome(
        ok=ok,
        status_code=int(status_code) if isinstance(status_code, int) else None,
        payload=payload,
        exit_code=proc.returncode,
        raw_stdout=proc.stdout,
        raw_stderr=proc.stderr,
    )


def call_cli_tool(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    as_of: str | None = DEFAULT_AS_OF,
    include: Sequence[str] | None = None,
    fields: Sequence[str] | None = None,
    extra_flags: Sequence[str] = (),
    timeout: float = 60.0,
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
    return call_cli(cli_args, stdin_text=stdin_payload, timeout=timeout)


def extract_error_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract normalized issue dictionaries from REST/MCP/CLI error envelopes."""
    issues = payload.get("issues")
    if isinstance(issues, list):
        return [dict(item) for item in issues if isinstance(item, dict)]
    detail = payload.get("detail")
    if isinstance(detail, dict) and isinstance(detail.get("issues"), list):
        return [dict(item) for item in detail["issues"] if isinstance(item, dict)]
    return []
