"""FastAPI route registration and HTTP output/error adaptation.

Live annotations are required by FastAPI; do not postpone their evaluation."""

import inspect
from typing import Annotated, Any, Callable, List, Optional

from pydantic import BeforeValidator, ValidationError

from fatebridge.application.execution import execute_tool, result_is_error
from fatebridge.application.projection import project_fields
from fatebridge.application.result_delivery import bound_response
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.execution_context import (
    ExecutionOptions,
    correlate_error,
    safe_correlation,
)
from fatebridge.transports.flags import FIELDS_FLAG_DESC as _FIELDS_FLAG_DESC
from fatebridge.transports.flags import RESPONSE_LIMIT_DESC
from fatebridge.transports.flags import SNAPSHOT_FLAG_DESC as _SNAPSHOT_FLAG_DESC
from fatebridge.transports.flags import STRICT_FIELDS_DESC as _STRICT_FIELDS_DESC
from fatebridge.transports.flags import ResponseCharLimit
from fatebridge.utils.errors import (
    ErrorEnvelope,
    ParameterError,
    handle_calculation_error,
    validation_error_result,
)

_REST_RESERVED_FIELDS = {
    "include_snapshot_text",
    "fields",
    "strict_fields",
    "response_char_limit",
    *ExecutionOptions.model_fields,
}


def _query_response_budget(value: object) -> object:
    # HTTP query values are strings. Coerce once before evaluating the union;
    # otherwise Literal[0] rejects "0" and the bounded integer branch rejects 0.
    return int(value) if isinstance(value, str) else value


def register_rest(
    app: Any,
    specs: List[ToolSpec],
    *,
    execute_service: Callable[..., Any],
    logger: Any = None,
) -> None:
    """Mount every spec with a ``rest_path`` as a POST route on the FastAPI app."""
    from fastapi import HTTPException

    for spec in specs:
        if not spec.rest_path:
            continue
        # Guard the output-shaping query params against a request-model field of
        # the same name (which FastAPI would route to the body, making the query
        # param unsettable). MCP guards these in ``_make_mcp_fn``; REST-only tools
        # (e.g. astro_relative) never pass through that path, so
        # enforce it here too — fail loud rather than silently shadow a flag.
        _clash = _REST_RESERVED_FIELDS & set(spec.request_model.model_fields)
        if _clash:
            raise ValueError(
                f"Tool '{spec.tool_name}' request model has reserved field name(s) "
                f"{_clash}; these collide with REST output-shaping query params."
            )
        app.add_api_route(
            spec.rest_path,
            make_rest_handler(
                spec,
                execute_service=execute_service,
                http_exception=HTTPException,
                logger=logger,
            ),
            methods=["POST"],
            name=f"rest_{spec.key}",
            operation_id=spec.key,
            response_model=None,
            responses={
                **({200: {"model": spec.output_model}} if spec.output_model else {}),
                **{
                    code: {"model": ErrorEnvelope}
                    for code in (400, 401, 422, 500, 503, 504)
                },
            },
        )


def make_rest_handler(
    spec: ToolSpec,
    *,
    execute_service: Callable[..., Any],
    http_exception: Any,
    logger: Any = None,
) -> Callable[..., Any]:
    from fastapi import Query

    model = spec.request_model
    error_label = spec.rest_error_label or f"{spec.operation_label_zh}参数"
    # A bare ``List`` param without ``Query()`` is read by FastAPI as a *body*
    # field, which would force the request model to embed under ``request`` and
    # break the flat body contract. Marking both params as Query keeps the body
    # exactly as before (the flat request model) and exposes these as query
    # params (``?include_snapshot_text=false&fields=a&fields=b``).
    snapshot_t = Annotated[bool, Query(description=_SNAPSHOT_FLAG_DESC)]
    fields_t = Annotated[Optional[List[str]], Query(description=_FIELDS_FLAG_DESC)]
    strict_t = Annotated[bool, Query(description=_STRICT_FIELDS_DESC)]
    limit_t = Annotated[
        ResponseCharLimit,
        BeforeValidator(_query_response_budget),
        Query(description=RESPONSE_LIMIT_DESC),
    ]
    execution_annotations = {
        name: Annotated[Optional[str], Query(description=definition.description)]
        for name, definition in ExecutionOptions.model_fields.items()
    }

    # Output-shaping query params, mirroring the MCP transport flags so a REST
    # caller can trim a 50KB payload to the few fields it needs. Defaults
    # reproduce the historical full payload exactly (no snapshot dropped, no
    # projection), so existing clients and golden masters see no change.
    # ``compact`` is intentionally omitted — HTTP/JSON serialization is FastAPI's
    # job and is already unindented. ``request`` is the only required parameter.
    async def handler(
        request: Any,
        include_snapshot_text: bool = spec.include_snapshot_text,
        fields: Optional[List[str]] = None,
        strict_fields: bool = False,
        response_char_limit: int = 0,
        as_of: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
    ) -> Any:  # signature injected below
        try:
            if logger is not None:
                logger.info("Processing %s request", spec.tool_name)
            options = ExecutionOptions(
                as_of=as_of, trace_id=trace_id, parent_run_id=parent_run_id
            )
            result = await execute_service(
                execute_tool,
                spec,
                request,
                tool_name=spec.run_metadata_name,
                cpu_bound=spec.cpu_bound,
                error_is_fatal=spec.error_is_fatal,
                options=options,
            )
            # Mirror the MCP/CLI path (see _render_protocol_response): only reshape
            # successful payloads so a transform keyed on a domain field can
            # never corrupt an error envelope.
            # Project AFTER run_metadata is attached (execute_service did it) so
            # provenance survives a selection; then drop snapshot_text if opted
            # out. Order matches MCP's _render_protocol_response.
            if not result_is_error(spec, result):
                result = project_fields(result, fields, strict_fields=strict_fields)
            if not include_snapshot_text and "snapshot_text" in result:
                result = {k: v for k, v in result.items() if k != "snapshot_text"}
            return bound_response(result, response_char_limit)
        except ValidationError as exc:
            raise http_exception(status_code=422, detail=validation_error_result(exc))
        except ParameterError as exc:
            raise http_exception(status_code=422, detail=exc.as_result())
        except ValueError:
            raise http_exception(status_code=400, detail=f"无效的{error_label}")
        except http_exception:
            raise
        except Exception as exc:  # noqa: BLE001
            if logger is not None:
                logger.error(
                    "Unexpected error during %s: %s", spec.tool_name, exc, exc_info=True
                )
            failure = handle_calculation_error(exc, spec.operation_label_zh)
            raise http_exception(status_code=failure["status_code"], detail=failure)

    handler.__name__ = f"rest_{spec.key}"
    handler.__doc__ = spec.summary
    setattr(
        handler,
        "__signature__",
        inspect.Signature(
            [
                inspect.Parameter(
                    "request",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=model,
                ),
                inspect.Parameter(
                    "include_snapshot_text",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=snapshot_t,
                    default=spec.include_snapshot_text,
                ),
                inspect.Parameter(
                    "fields",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=fields_t,
                    default=None,
                ),
                inspect.Parameter(
                    "strict_fields",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=strict_t,
                    default=False,
                ),
                inspect.Parameter(
                    "response_char_limit",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=limit_t,
                    default=0,
                ),
                *[
                    inspect.Parameter(
                        name,
                        inspect.Parameter.KEYWORD_ONLY,
                        annotation=annotation,
                        default=None,
                    )
                    for name, annotation in execution_annotations.items()
                ],
            ]
        ),
    )
    handler.__annotations__ = {
        "request": model,
        "include_snapshot_text": snapshot_t,
        "fields": fields_t,
        "strict_fields": strict_t,
        "response_char_limit": limit_t,
        **execution_annotations,
        "return": dict,
    }
    return handler
