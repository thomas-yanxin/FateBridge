"""Register calculation routes with live FastAPI annotations."""

import inspect
import logging
from typing import Annotated, Protocol

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, BeforeValidator
from starlette.concurrency import run_in_threadpool

from fatebridge.application.execution import result_is_error
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import DetailLevel, ExecutionOptions
from fatebridge.transports.flags import (
    FIELDS_FLAG_DESC,
    RESPONSE_LIMIT_DESC,
    SNAPSHOT_FLAG_DESC,
    STRICT_FIELDS_DESC,
    ResponseCharLimit,
    invalid_response_budget,
)
from fatebridge.utils.errors import ErrorEnvelope, handle_calculation_error

logger = logging.getLogger(__name__)

REST_RESERVED_FIELDS = {
    "include_snapshot_text",
    "fields",
    "strict_fields",
    "response_char_limit",
    *ExecutionOptions.model_fields,
}


class RestCalculationExecutor(Protocol):
    async def __call__(
        self,
        spec: ToolSpec,
        request: BaseModel,
        *,
        options: ExecutionOptions,
        fields: list[str] | None,
        include_snapshot_text: bool | None,
    ) -> ServiceResult: ...


def query_response_budget(raw_budget: str | int) -> int:
    # note (FastAPI): Convert query text before the union checks the literal zero.
    try:
        return int(raw_budget)
    except ValueError:
        raise invalid_response_budget() from None


def register_rest(
    app: FastAPI,
    specs: list[ToolSpec],
    *,
    execute_service: RestCalculationExecutor,
) -> None:
    """Mount the catalog's HTTP calculation routes."""
    for spec in specs:
        if not spec.rest_path:
            continue
        else:
            register_rest_route(app, spec, spec.rest_path, execute_service)


def register_rest_route(
    app: FastAPI,
    spec: ToolSpec,
    route_path: str,
    execute_service: RestCalculationExecutor,
) -> None:
    """Bind one tool's body model and the shared output controls to a POST route."""
    # note (FastAPI): A reserved field in the body would hide the matching query parameter.
    reserved_fields = REST_RESERVED_FIELDS.intersection(spec.request_model.model_fields)
    if reserved_fields:
        raise ValueError(
            f"Tool '{spec.tool_name}' request model has reserved field name(s) "
            f"{reserved_fields}; these collide with REST output-shaping query params."
        )
    else:
        pass

    async def calculation_route(
        request: BaseModel,
        *,
        include_snapshot_text: Annotated[
            bool | None, Query(description=SNAPSHOT_FLAG_DESC)
        ] = None,
        fields: Annotated[list[str] | None, Query(description=FIELDS_FLAG_DESC)] = None,
        strict_fields: Annotated[bool, Query(description=STRICT_FIELDS_DESC)] = False,
        response_char_limit: Annotated[
            ResponseCharLimit,
            BeforeValidator(query_response_budget),
            Query(description=RESPONSE_LIMIT_DESC),
        ] = 0,
        as_of: str | None = None,
        trace_id: str | None = None,
        parent_run_id: str | None = None,
        detail: DetailLevel = "standard",
    ) -> ServiceResult:
        try:
            logger.info(f"Processing {spec.tool_name} request")
            options = ExecutionOptions(
                as_of=as_of,
                trace_id=trace_id,
                parent_run_id=parent_run_id,
                detail=detail,
            )
            result = await execute_service(
                spec,
                request,
                options=options,
                fields=fields,
                include_snapshot_text=include_snapshot_text,
            )
            return await run_in_threadpool(
                deliver_response,
                result,
                spec=spec,
                fields=fields,
                strict_fields=strict_fields,
                include_snapshot_text=include_snapshot_text,
                response_char_limit=response_char_limit,
                detail=options.detail,
                failed=result_is_error(result),
            )
        except HTTPException:
            raise
        except Exception as error:
            failure = handle_calculation_error(error, spec.operation_label_zh)
            raise HTTPException(
                status_code=failure["status_code"], detail=failure
            ) from None

    calculation_route.__name__ = f"rest_{spec.key}"
    calculation_route.__doc__ = spec.summary
    calculation_route.__annotations__["request"] = spec.request_model
    for parameter_name, definition in ExecutionOptions.model_fields.items():
        annotation = definition.annotation
        assert annotation is not None
        calculation_route.__annotations__[parameter_name] = Annotated[
            annotation, Query(description=definition.description)
        ]
    # note (FastAPI): Keep the concrete body annotation and defaults shared with execution options.
    route_signature = inspect.signature(calculation_route)
    setattr(
        calculation_route,
        "__signature__",
        route_signature.replace(
            parameters=[
                (
                    parameter.replace(
                        default=ExecutionOptions.model_fields[parameter.name].default
                    )
                    if parameter.name in ExecutionOptions.model_fields
                    else parameter
                )
                for parameter in route_signature.parameters.values()
            ],
            return_annotation=inspect.Signature.empty,
        ),
    )
    app.add_api_route(
        route_path,
        calculation_route,
        methods=["POST"],
        name=f"rest_{spec.key}",
        operation_id=spec.tool_name,
        summary=spec.tool_name.replace("_", " ").capitalize(),
        response_model=None,
        responses={
            **({200: {"model": spec.output_model}} if spec.output_model else {}),
            **{
                status_code: {"model": ErrorEnvelope}
                for status_code in (400, 401, 422, 500, 503, 504)
            },
        },
    )
