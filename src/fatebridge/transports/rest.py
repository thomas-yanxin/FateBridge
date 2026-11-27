"""Register calculation routes with live FastAPI annotations."""

import inspect
import logging
from typing import Annotated, Protocol

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, JsonValue
from starlette.concurrency import run_in_threadpool

from fatebridge.application.batch import BatchRequest, execute_batch
from fatebridge.application.execution import result_is_error
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import DetailLevel, ExecutionOptions
from fatebridge.transports.flags import FIELDS_FLAG_DESC
from fatebridge.utils.errors import (
    ErrorEnvelope,
    ParameterError,
    handle_calculation_error,
)

logger = logging.getLogger(__name__)

REST_RESERVED_FIELDS = {
    "fields",
    *ExecutionOptions.model_fields,
}


class RestCalculationExecutor(Protocol):
    async def __call__(
        self,
        spec: ToolSpec,
        request: BaseModel,
        *,
        options: ExecutionOptions,
    ) -> ServiceResult: ...


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
            f"Tool '{spec.name}' request model has reserved field name(s) "
            f"{reserved_fields}; these collide with REST output-shaping query params."
        )

    async def calculation_route(
        request: BaseModel,
        *,
        fields: Annotated[list[str] | None, Query(description=FIELDS_FLAG_DESC)] = None,
        as_of: str | None = None,
        detail: DetailLevel = "compact",
    ) -> ServiceResult:
        try:
            logger.info(f"Processing {spec.name} request")
            options = ExecutionOptions(
                as_of=as_of,
                detail=detail,
            )
            result = await execute_service(
                spec,
                request,
                options=options,
            )
            return await run_in_threadpool(
                deliver_response,
                result,
                spec=spec,
                fields=fields,
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

    calculation_route.__name__ = f"rest_{spec.name}"
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
        name=f"rest_{spec.name}",
        operation_id=spec.name,
        summary=spec.name.replace("_", " ").capitalize(),
        response_model=None,
        responses={
            **({200: {"model": spec.output_model}} if spec.output_model else {}),
            **{
                status_code: {"model": ErrorEnvelope}
                for status_code in (400, 401, 422, 500, 503, 504)
            },
        },
    )


def register_batch_route(app: FastAPI, specs: list[ToolSpec]) -> None:
    """Mount POST /api/batch for stateless multi-subject, multi-tool execution."""
    specs_by_name = {spec.name: spec for spec in specs}

    @app.post(
        "/api/batch",
        name="rest_batch",
        operation_id="run_batch",
        summary="Run batch calculations",
        description=(
            "Stateless multi-subject, multi-tool batch execution. "
            "Maps shared subjects and defaults to each tool's contract, "
            "executes calls under one frozen as_of clock, and isolates per-call errors."
        ),
        responses={
            status_code: {"model": ErrorEnvelope}
            for status_code in (400, 401, 422, 500, 503, 504)
        },
    )
    async def batch_route(request: BatchRequest) -> dict[str, JsonValue]:
        try:
            return await run_in_threadpool(execute_batch, specs_by_name, request)
        except ParameterError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.as_result(),
            ) from None
        except Exception as error:
            failure = handle_calculation_error(error, "batch")
            raise HTTPException(
                status_code=failure["status_code"],
                detail=failure,
            ) from None
