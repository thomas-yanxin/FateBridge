"""FastMCP tool registration and protocol argument adaptation.

Live annotations are required by FastMCP; do not postpone their evaluation."""

import inspect
from copy import copy
from typing import Annotated, Any, Callable, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, Field, ValidationError
from pydantic_core import PydanticUndefined

from fatebridge.application.description import mcp_description
from fatebridge.application.execution import (
    execute_tool,
    invalid_input_result,
    result_is_error,
)
from fatebridge.application.result_delivery import DEFAULT_MCP_RESPONSE_CHARS
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.execution_context import (
    ExecutionOptions,
    correlate_error,
    safe_correlation,
)
from fatebridge.core.schema_cache import model_schema
from fatebridge.transports.flags import COMPACT_FLAG_DESC as _COMPACT_FLAG_DESC
from fatebridge.transports.flags import FIELDS_FLAG_DESC as _FIELDS_FLAG_DESC
from fatebridge.transports.flags import RESPONSE_LIMIT_DESC
from fatebridge.transports.flags import SNAPSHOT_FLAG_DESC as _SNAPSHOT_FLAG_DESC
from fatebridge.transports.flags import STRICT_FIELDS_DESC as _STRICT_FIELDS_DESC
from fatebridge.transports.flags import ResponseCharLimit
from fatebridge.utils.errors import (
    ParameterError,
    handle_calculation_error,
    validation_error_result,
)

_MCP_OMITTED = object()
_MCP_SOLAR_FIELDS = {
    "use_true_solar_time",
    "person1_use_true_solar_time",
    "person2_use_true_solar_time",
}
_MCP_COMPONENT_FIELDS = {
    "birth_minute",
    "person1_birth_minute",
    "person2_birth_minute",
}
_MCP_PRESENCE_FIELDS = _MCP_SOLAR_FIELDS | _MCP_COMPONENT_FIELDS


def _mcp_omitted_default() -> Any:
    return _MCP_OMITTED


def model_parameters(
    model: Type[BaseModel],
    *,
    additional_presence_fields: tuple[str, ...] = (),
) -> Tuple[List[inspect.Parameter], Dict[str, Any]]:
    """Expose constraints while preserving omitted flags and clock components."""
    required: List[inspect.Parameter] = []
    optional: List[inspect.Parameter] = []
    annotations: Dict[str, Any] = {}
    for name, field in model.model_fields.items():
        metadata = copy(field)
        metadata.default = PydanticUndefined
        metadata.default_factory = None
        preserve_omission = (
            name in _MCP_PRESENCE_FIELDS or name in additional_presence_fields
        ) and not field.is_required()
        if preserve_omission:
            # Pydantic fills signature defaults before calling impl. A factory
            # gives omitted inputs a private sentinel without accepting null
            # or changing the request model's actual default.
            metadata.default_factory = _mcp_omitted_default
        ann: Any = Annotated[
            field.annotation if field.annotation is not None else Any, metadata
        ]
        annotations[name] = ann
        if field.is_required():
            required.append(
                inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=ann)
            )
        else:
            default = field.get_default(call_default_factory=True)
            optional.append(
                inspect.Parameter(
                    name,
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=ann,
                    default=inspect.Parameter.empty if preserve_omission else default,
                )
            )
    return required + optional, annotations


def register_mcp(
    app: Any,
    specs: List[ToolSpec],
    *,
    render_response: Callable[..., Any],
    render_error: Callable[..., Any],
) -> List[Any]:
    """Register every spec with an ``mcp_name`` (or key) as a FastMCP tool."""
    from fastmcp.tools import Tool
    from fastmcp.utilities.json_schema import dereference_refs
    from mcp.types import ToolAnnotations

    registered = []
    for spec in specs:
        if spec.mcp_name is None and spec.key is None:
            continue
        protocol_fn = _make_mcp_fn(
            spec,
            render_response=render_response,
            render_error=render_error,
        )
        tool = Tool.from_function(
            protocol_fn,
            name=spec.tool_name,
            description=mcp_description(spec),
            annotations=ToolAnnotations.model_validate(
                spec.execution_hints.as_annotations()
            ),
            tags={spec.family},
            output_schema=(
                model_schema(spec.output_model) if spec.output_model else None
            ),
        )
        presence_fields = _MCP_PRESENCE_FIELDS | (
            {"analysis_minute"} if spec.key == "meihua_analysis" else set()
        )
        for name in presence_fields & spec.request_model.model_fields.keys():
            field = spec.request_model.model_fields[name]
            if not field.is_required():
                # The factory is an adapter detail. Discovery describes the
                # domain default, which the request model applies after omission.
                tool.parameters["properties"][name]["default"] = field.get_default(
                    call_default_factory=True
                )
        # Some hosts render $ref array members as unknown in the model's tool
        # context. Inline input contracts for all tools, using FastMCP's cycle-
        # safe resolver. Keep output schemas shared and runtime validation intact.
        tool.parameters = dereference_refs(tool.parameters)
        app.add_tool(tool)
        registered.append(tool)
    from fatebridge.mcp_transport import InputValidationMiddleware

    app.add_middleware(InputValidationMiddleware(specs))
    return registered


def _make_mcp_fn(
    spec: ToolSpec,
    *,
    render_response: Callable[..., Any],
    render_error: Callable[..., Any],
) -> Callable[..., Any]:
    from fastmcp.tools import ToolResult

    model = spec.request_model
    params, annotations = model_parameters(
        model,
        additional_presence_fields=(
            ("analysis_minute",) if spec.key == "meihua_analysis" else ()
        ),
    )
    # Transport-level flags appended after model fields; guard against a model
    # field shadowing them (would make the flag unsettable / silently swallowed).
    _reserved = {
        "compact",
        "include_snapshot_text",
        "fields",
        "strict_fields",
        "response_char_limit",
        *ExecutionOptions.model_fields,
    }
    _clash = _reserved & set(model.model_fields)
    if _clash:
        raise ValueError(
            f"Tool '{spec.tool_name}' request model has reserved field name(s) {_clash}; "
            "these collide with MCP transport flags."
        )
    # Annotated[..., Field(description=...)] is what FastMCP/pydantic read for
    # per-parameter docs — inspect.Parameter has no description slot. Without
    # these, an LLM sees three bare flags and has to guess their meaning (and the
    # dotted-path syntax for ``fields`` lived only in CLI help).
    compact_t = Annotated[bool, Field(description=_COMPACT_FLAG_DESC)]
    snapshot_t = Annotated[bool, Field(description=_SNAPSHOT_FLAG_DESC)]
    fields_t = Annotated[Optional[List[str]], Field(description=_FIELDS_FLAG_DESC)]
    strict_t = Annotated[bool, Field(description=_STRICT_FIELDS_DESC)]
    limit_t = Annotated[ResponseCharLimit, Field(description=RESPONSE_LIMIT_DESC)]
    params.append(
        inspect.Parameter(
            "compact",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=compact_t,
            default=True,
        )
    )
    params.append(
        inspect.Parameter(
            "include_snapshot_text",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=snapshot_t,
            default=spec.include_snapshot_text,
        )
    )
    params.append(
        inspect.Parameter(
            "fields",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=fields_t,
            default=None,
        )
    )
    annotations = {
        **annotations,
        "compact": compact_t,
        "include_snapshot_text": snapshot_t,
        "fields": fields_t,
        "strict_fields": strict_t,
        "response_char_limit": limit_t,
    }
    params.append(
        inspect.Parameter(
            "strict_fields",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=strict_t,
            default=False,
        )
    )
    params.append(
        inspect.Parameter(
            "response_char_limit",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=limit_t,
            default=DEFAULT_MCP_RESPONSE_CHARS,
        )
    )
    for name, definition in ExecutionOptions.model_fields.items():
        annotation = Annotated[Optional[str], Field(description=definition.description)]
        annotations[name] = annotation
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
                default=None,
            )
        )

    def impl(**kwargs: Any) -> Any:
        compact = kwargs.pop("compact", True)
        include_snapshot_text = kwargs.pop(
            "include_snapshot_text", spec.include_snapshot_text
        )
        fields = kwargs.pop("fields", None)
        strict_fields = kwargs.pop("strict_fields", False)
        response_char_limit = kwargs.pop(
            "response_char_limit", DEFAULT_MCP_RESPONSE_CHARS
        )
        controls = {
            name: kwargs.pop(name, None) for name in ExecutionOptions.model_fields
        }
        kwargs = {
            name: value for name, value in kwargs.items() if value is not _MCP_OMITTED
        }
        try:
            options = ExecutionOptions.model_validate(controls)
            from fatebridge.transports.request_context import MCP_REQUEST

            contextual = MCP_REQUEST.get()
            request = (
                contextual[1]
                if contextual is not None and contextual[0] == spec.key
                else model(**kwargs)
            )
            result = execute_tool(spec, request, options=options)
        except ValidationError as exc:
            return render_error(
                correlate_error(
                    validation_error_result(exc), safe_correlation(controls)
                ),
                spec.operation_label_zh,
                compact=compact,
            )
        except ValueError:
            # Binding/domain ValueError remains a generic 400. Model validation
            # has its own sanitized 422 path above.
            return render_error(
                invalid_input_result(spec), spec.operation_label_zh, compact=compact
            )
        except Exception as exc:
            return render_error(
                handle_calculation_error(exc, spec.operation_label_zh),
                spec.operation_label_zh,
                compact=compact,
            )
        if result_is_error(spec, result):
            return render_error(result, spec.operation_label_zh, compact=compact)
        try:
            return render_response(
                result,
                compact=compact,
                include_snapshot_text=include_snapshot_text,
                fields=fields,
                strict_fields=strict_fields,
                tool_name=spec.run_metadata_name,
                response_char_limit=response_char_limit,
            )
        except ParameterError as exc:
            return render_error(
                correlate_error(exc.as_result(), options),
                spec.operation_label_zh,
                compact=compact,
            )

    impl.__name__ = spec.tool_name
    impl.__doc__ = spec.summary
    setattr(impl, "__signature__", inspect.Signature(params))
    impl.__annotations__ = {**annotations, "return": ToolResult}
    return impl
