"""FateBridge — deterministic Chinese metaphysics, divination, and astrology engine.

Lazy Python SDK exports (`discover`, `tools`, `run`) load the central catalog
only when called so `import fatebridge` remains near-instant.
"""

from __future__ import annotations

from typing import Any, Literal

__version__ = "0.1.1"
__author__ = "thomas-yanxin"

__all__ = ["__version__", "__author__", "discover", "tools", "run"]


def discover(
    family: str | None = None,
    q: str | None = None,
    tool: str | None = None,
    detail: Literal["summary", "full"] = "summary",
    include_output_schema: bool = False,
) -> dict[str, Any]:
    """Discover tools, counts, input schemas, and field contracts."""
    from fatebridge.application.discovery import discover_specs
    from fatebridge.services.tool_catalog import CATALOG

    return discover_specs(
        CATALOG,
        family=family,
        q=q,
        tool=tool,
        detail=detail,
        include_output_schema=include_output_schema,
    )


def tools(family: str | None = None) -> list[dict[str, Any]]:
    """Return tool summary records, optionally filtered by family."""
    tool_rows: list[dict[str, Any]] = discover(family=family)["tools"]
    return tool_rows


def run(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    detail: Literal["compact", "audit"] = "compact",
    fields: list[str] | None = None,
    as_of: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Validate inputs, run a deterministic tool calculation, and project the response."""
    import difflib

    from fatebridge.application.execution import execute_with_receipt, result_is_error
    from fatebridge.application.response_delivery import deliver_response
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.utils.errors import ParameterError, handle_calculation_error

    merged: dict[str, Any] = {**(arguments or {}), **kwargs}
    spec = next((item for item in CATALOG if item.name == tool), None)
    if spec is None:
        suggestions = difflib.get_close_matches(
            tool, sorted(item.name for item in CATALOG), n=5, cutoff=0.4
        )
        issue: dict[str, object] = {"path": "tool", "code": "unknown_tool"}
        if suggestions:
            issue["constraints"] = {"suggestions": suggestions}
        raise ParameterError(f"未知工具: {tool}", [issue], status_code=404)

    options = ExecutionOptions.model_validate({"as_of": as_of, "detail": detail})
    try:
        request = spec.request_model.model_validate(merged)
        result = execute_with_receipt(spec, request, options=options)
    except Exception as exc:  # noqa: BLE001 - expose consistent public error envelope
        return handle_calculation_error(exc, spec.operation_label_zh)
    if result_is_error(result):
        return result
    return deliver_response(result, spec=spec, fields=fields, detail=options.detail)
