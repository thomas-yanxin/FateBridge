"""FateBridge — deterministic Chinese metaphysics, divination, and astrology engine.

Lazy Python SDK exports (`discover`, `tools`, `run`, `batch`) load the central
catalog only when called so `import fatebridge` remains near-instant.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel

    from fatebridge.application.discovery import DiscoveryDetail, ToolSurface
    from fatebridge.application.tool_spec import ServiceResult

__version__ = "0.1.1"
__author__ = "thomas-yanxin"

__all__ = ["__version__", "__author__", "discover", "tools", "run", "batch"]


def discover(
    family: str | None = None,
    q: str | None = None,
    tool: str | None = None,
    tools: list[str] | str | None = None,
    surface: ToolSurface | None = None,
    detail: DiscoveryDetail = "summary",
    include_output_schema: bool = False,
) -> ServiceResult:
    """Discover tools, counts, input schemas, and field contracts."""
    from fatebridge.application.discovery import discover_specs
    from fatebridge.services.tool_catalog import (
        all_catalog,
        get_specs,
        known_tool_names,
    )

    requested_exact: list[str] = []
    if tool is not None and tools is None:
        requested_exact = [tool]
    elif tools is not None and tool is None:
        requested_exact = (
            [part.strip() for part in tools.split(",") if part.strip()]
            if isinstance(tools, str)
            else [str(item).strip() for item in tools if str(item).strip()]
        )
    known = set(known_tool_names())
    if (
        requested_exact
        and family is None
        and q is None
        and all(name in known for name in requested_exact)
    ):
        source_specs = get_specs(requested_exact)
    else:
        source_specs = all_catalog()

    return discover_specs(
        source_specs,
        family=family,
        q=q,
        tool=tool,
        tools=tools,
        surface=surface,
        detail=detail,
        include_output_schema=include_output_schema,
    )


def tools(family: str | None = None) -> list[ServiceResult]:
    """Return tool summary records, optionally filtered by family."""
    tool_rows = discover(family=family)["tools"]
    assert isinstance(tool_rows, list)
    return [row for row in tool_rows if isinstance(row, dict)]


def run(
    tool: str,
    arguments: Mapping[str, object] | None = None,
    *,
    include: list[str] | None = None,
    fields: list[str] | None = None,
    as_of: str | None = None,
    **kwargs: object,
) -> ServiceResult:
    """Validate inputs, run a deterministic tool calculation, and project the response."""
    from fatebridge.application.execution import run_tool
    from fatebridge.services.tool_catalog import get_spec, known_tool_names
    from fatebridge.utils.errors import ParameterError, unknown_tool_error

    spec = get_spec(tool)
    if spec is None:
        raise unknown_tool_error(tool, known_tool_names())

    if arguments is not None and not isinstance(arguments, Mapping):
        raise ParameterError(
            "请求参数无效",
            [
                {
                    "path": "arguments",
                    "code": "dict_type",
                    "message": "Input should be a valid dictionary",
                }
            ],
        )
    merged: dict[str, object] = {
        **({} if arguments is None else arguments),
        **kwargs,
    }
    return run_tool(
        spec,
        merged,
        include=include,
        fields=fields,
        as_of=as_of,
        raise_parameter_error=True,
    ).payload


def batch(
    calls: Sequence[Mapping[str, object] | BaseModel],
    *,
    subjects: Mapping[str, Mapping[str, object] | BaseModel] | None = None,
    context: Mapping[str, object] | BaseModel | None = None,
    defaults: Mapping[str, object] | None = None,
    as_of: str | None = None,
    stop_on_error: bool = False,
) -> ServiceResult:
    """Validate and execute a stateless multi-subject, multi-tool batch calculation."""
    from fatebridge.application.batch import BatchRequest, execute_batch
    from fatebridge.application.execution import run_guarded_operation
    from fatebridge.services.tool_catalog import (
        all_catalog,
        get_specs,
        known_tool_names,
    )

    def _run_batch() -> ServiceResult:
        batch_request = BatchRequest.model_validate(
            {
                "subjects": {} if subjects is None else subjects,
                "context": context,
                "defaults": {} if defaults is None else defaults,
                "calls": calls,
                "as_of": as_of,
                "stop_on_error": stop_on_error,
            }
        )
        known = set(known_tool_names())
        requested_names = [call.tool for call in batch_request.calls]
        batch_specs = (
            get_specs(requested_names)
            if all(name in known for name in requested_names)
            else all_catalog()
        )
        return execute_batch(
            {spec.name: spec for spec in batch_specs},
            batch_request,
        )

    return run_guarded_operation(
        "batch",
        _run_batch,
        allowed_fields=BatchRequest.model_fields.keys(),
        root_model=BatchRequest,
    ).payload
