"""Serve FateBridge calculations and result readers over HTTP."""

import asyncio
import logging
import os
import time
import warnings
from copy import deepcopy
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic.warnings import UnsupportedFieldAttributeWarning
from pydantic_core import ErrorDetails
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response
from starlette.routing import Match, Mount, Route, WebSocketRoute

from fatebridge.utils.runtime import (
    get_api_key_header_name,
    get_log_level,
    load_runtime_env,
    parse_allowed_origins,
    parse_api_keys,
)

# note (startup): Load dotenv before importing code that configures Swiss Ephemeris.
load_runtime_env()

# isort: split

from fatebridge import __version__ as APP_VERSION
from fatebridge.application.compute_limits import heavy_calculation_budget
from fatebridge.application.discovery import ToolSurface, discover_specs
from fatebridge.application.execution import execute_tool, result_is_error
from fatebridge.application.result_delivery import RESULT_STORE
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import (
    ExecutionOptions,
    correlate_error,
    safe_correlation,
)
from fatebridge.services.tool_catalog import CATALOG, rest_specs
from fatebridge.transports.http_runtime import (
    API_KEY_EXEMPT_PATHS,
    READINESS_METRICS_MEDIA_TYPE,
    ApiKeyAuthenticator,
    RuntimeMetrics,
    build_readiness_payload,
)
from fatebridge.transports.rest import register_rest
from fatebridge.utils.errors import (
    ErrorEnvelope,
    ParameterError,
    handle_calculation_error,
    validation_issues_result,
)

__all__ = ["ApiKeyAuthenticator", "ErrorEnvelope", "RuntimeMetrics", "app", "main"]

configured_log_level = logging.getLevelName(get_log_level())
logging.basicConfig(
    level=(
        configured_log_level if isinstance(configured_log_level, int) else logging.INFO
    ),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class FateBridgeApi(FastAPI):
    def openapi(self) -> ServiceResult:
        """Describe middleware authentication without changing its runtime policy."""
        if self.openapi_schema is None:
            self.openapi_schema = get_openapi(
                title=self.title,
                version=self.version,
                description=self.description,
                routes=self.routes,
            )
        schema = deepcopy(self.openapi_schema)
        schema.setdefault("components", {}).setdefault("securitySchemes", {})[
            "APIKey"
        ] = {
            "type": "apiKey",
            "in": "header",
            "name": API_KEY_AUTHENTICATOR.header_name,
        }
        if API_KEY_AUTHENTICATOR.is_enabled:
            for path, operations in schema["paths"].items():
                if path not in API_KEY_EXEMPT_PATHS:
                    for operation in operations.values():
                        operation["security"] = [{"APIKey": []}]
        return schema


app = FateBridgeApi(
    title="FateBridge API",
    description="API for FateBridge calculations across BaZi, divination, timing, and offline astrology charts with local ephemeris preference",
    version=APP_VERSION,
    responses={422: {"model": ErrorEnvelope}},
)
API_KEY_AUTHENTICATOR = ApiKeyAuthenticator(
    header_name=get_api_key_header_name(),
    api_keys=parse_api_keys(),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(),
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", API_KEY_AUTHENTICATOR.header_name],
)

REQUEST_METRICS = RuntimeMetrics()
HTTP_METHODS = frozenset(
    {"GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH"}
)
HEAVY_CALC_SEMAPHORE: asyncio.Semaphore | None = None
HEAVY_CALC_SEMAPHORE_LOOP: asyncio.AbstractEventLoop | None = None


def _reset_runtime_state_for_tests() -> None:
    global HEAVY_CALC_SEMAPHORE, HEAVY_CALC_SEMAPHORE_LOOP
    REQUEST_METRICS.reset()
    HEAVY_CALC_SEMAPHORE = None
    HEAVY_CALC_SEMAPHORE_LOOP = None


def _metrics_route_path(request: Request) -> str:
    """Resolve a fixed route label before routing and authentication run."""
    partial_route_path: str | None = None
    for route in app.routes:
        route_match, _ = route.matches(request.scope)
        route_path = (
            route.path
            if isinstance(route, (Route, Mount, WebSocketRoute))
            else "/unknown"
        )
        if route_match == Match.FULL:
            return route_path
        elif route_match == Match.PARTIAL and partial_route_path is None:
            partial_route_path = route_path
    return partial_route_path or "/unknown"


@app.middleware("http")
async def instrument_request_lifecycle(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    method = request.method.upper()
    metrics_path = _metrics_route_path(request)
    metrics_method = method if method in HTTP_METHODS else "OTHER"

    if (
        API_KEY_AUTHENTICATOR.is_enabled
        and method != "OPTIONS"
        and request.url.path not in API_KEY_EXEMPT_PATHS
    ):
        authenticated_key_id = API_KEY_AUTHENTICATOR.authenticate(request)
        if authenticated_key_id is None:
            REQUEST_METRICS.observe(
                method=metrics_method,
                path=metrics_path,
                status_code=401,
                duration_seconds=0.0,
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "缺少或无效的 API key",
                    "error_code": "authentication_required",
                    "retryable": False,
                },
                headers={"WWW-Authenticate": "APIKey"},
            )
        else:
            request.state.api_key_id = authenticated_key_id

    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as error:
        failure = RuntimeError("REST request handling failed")
        failure.__cause__ = error
        response = JSONResponse(
            status_code=500,
            content=_build_error_detail(
                handle_calculation_error(failure, metrics_path)
            ),
        )

    REQUEST_METRICS.observe(
        method=metrics_method,
        path=metrics_path,
        status_code=response.status_code,
        duration_seconds=time.perf_counter() - started_at,
    )
    return response


def _build_error_detail(result: ServiceResult) -> ServiceResult:
    return ErrorEnvelope(
        error=result["error"],
        error_code=result.get("error_code", "internal_error"),
        retryable=result.get("retryable", False),
        issues=result.get("issues"),
        trace_id=result.get("trace_id"),
        parent_run_id=result.get("parent_run_id"),
    ).model_dump(exclude_none=True)


@app.exception_handler(RequestValidationError)
async def _request_validation_error_envelope(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    issues: list[ErrorDetails] = []
    for issue in exception.errors():
        issue_location = issue["loc"]
        if issue_location and issue_location[0] in {
            "body",
            "query",
            "path",
            "header",
            "cookie",
        }:
            normalized_issue: ErrorDetails = issue.copy()
            normalized_issue["loc"] = issue_location[1:]
            issues.append(normalized_issue)
        else:
            issues.append(issue)
    result = correlate_error(
        validation_issues_result(issues),
        safe_correlation(dict(request.query_params)),
    )
    return JSONResponse(
        status_code=result["status_code"],
        content=_build_error_detail(result),
    )


@app.exception_handler(HTTPException)
async def _http_error_envelope(
    request: Request, exception: HTTPException
) -> JSONResponse:
    """Render HTTP exceptions in the common top-level error format."""
    detail = exception.detail
    if isinstance(detail, dict) and "error_code" in detail:
        response_body = _build_error_detail({**detail, "error": detail.get("error")})
    else:
        response_body = _build_error_detail(
            {
                "error": detail,
                "error_code": (
                    "validation_error"
                    if exception.status_code == 400
                    else "internal_error"
                ),
                "retryable": False,
            }
        )
    response_body = correlate_error(
        response_body, safe_correlation(dict(request.query_params))
    )
    return JSONResponse(status_code=exception.status_code, content=response_body)


def _get_heavy_calc_semaphore() -> asyncio.Semaphore:
    global HEAVY_CALC_SEMAPHORE, HEAVY_CALC_SEMAPHORE_LOOP
    event_loop = asyncio.get_running_loop()
    if HEAVY_CALC_SEMAPHORE is None or (
        HEAVY_CALC_SEMAPHORE_LOOP is not None
        and HEAVY_CALC_SEMAPHORE_LOOP is not event_loop
    ):
        HEAVY_CALC_SEMAPHORE = asyncio.Semaphore(
            heavy_calculation_budget().max_concurrency
        )
    HEAVY_CALC_SEMAPHORE_LOOP = event_loop
    return HEAVY_CALC_SEMAPHORE


async def _execute_service(
    spec: ToolSpec,
    request: BaseModel,
    *,
    options: ExecutionOptions,
    fields: list[str] | None,
    include_snapshot_text: bool | None,
) -> ServiceResult:
    if spec.cpu_bound:
        async with _get_heavy_calc_semaphore():
            result = await run_in_threadpool(
                execute_tool,
                spec,
                request,
                options=options,
                fields=fields,
                include_snapshot_text=include_snapshot_text,
            )
    else:
        result = await run_in_threadpool(
            execute_tool,
            spec,
            request,
            options=options,
            fields=fields,
            include_snapshot_text=include_snapshot_text,
        )
    if result_is_error(result):
        raise HTTPException(
            status_code=int(result.get("status_code", 500)),
            detail=_build_error_detail(result),
        )
    else:
        return result


@app.get("/health", response_model=ServiceResult)
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check() -> JSONResponse:
    """Readiness endpoint that reports required and optional runtime checks."""
    payload = build_readiness_payload(API_KEY_AUTHENTICATOR)
    status_code = 200 if payload["status"] == "ready" else 503
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/metrics")
async def metrics_endpoint() -> PlainTextResponse:
    """Prometheus-style text metrics for request volume and readiness state."""
    return PlainTextResponse(
        REQUEST_METRICS.render_prometheus(
            readiness_status=build_readiness_payload(API_KEY_AUTHENTICATOR)["status"],
            api_key_auth_enabled=API_KEY_AUTHENTICATOR.is_enabled,
            configured_api_keys=API_KEY_AUTHENTICATOR.configured_keys,
        ),
        media_type=READINESS_METRICS_MEDIA_TYPE,
    )


register_rest(app, rest_specs(), execute_service=_execute_service)

# note (Pydantic): Build deferred body adapters while FastAPI's field-alias warning is filtered.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=UnsupportedFieldAttributeWarning)
    for route in app.routes:
        if isinstance(route, APIRoute):
            for body_parameter in route.dependant.body_params:
                body_parameter._type_adapter.rebuild()


@app.get("/api/results/{result_id}")
async def result_manifest(result_id: str) -> ServiceResult:
    """Read the manifest of a retained result under normal API authentication."""
    try:
        return await run_in_threadpool(RESULT_STORE.manifest, result_id)
    except ParameterError as exception:
        raise HTTPException(status_code=404, detail=exception.as_result()) from None


@app.get("/api/results/{result_id}/pages")
async def result_page(
    result_id: str,
    offset: int = Query(default=0, ge=0),
    path: str | None = Query(default=None, max_length=1000),
) -> ServiceResult:
    """Retrieve a bounded page or field from the original run, without recalculation."""
    try:
        return await run_in_threadpool(RESULT_STORE.page, result_id, offset, path)
    except ParameterError as exception:
        raise HTTPException(status_code=404, detail=exception.as_result()) from None


@app.get("/api/results/{result_id}/payload")
async def result_payload(result_id: str) -> ServiceResult:
    """Download the selected response from the original run in one request."""
    try:
        return await run_in_threadpool(RESULT_STORE.get, result_id)
    except ParameterError as exception:
        raise HTTPException(status_code=404, detail=exception.as_result()) from None


@app.get("/api/results/{result_id}/verified")
async def verified_result_page(
    result_id: str,
    expected_run_id: str = Query(pattern=r"^[A-Za-z0-9_-]{1,128}$"),
    offset: int = Query(default=0, ge=0),
    path: str | None = Query(default=None, max_length=1000),
) -> ServiceResult:
    """Verify the full original payload before reading one bounded page."""
    try:
        return await run_in_threadpool(
            RESULT_STORE.verified_page,
            result_id,
            expected_run_id,
            offset,
            path,
        )
    except ParameterError as exception:
        raise HTTPException(status_code=422, detail=exception.as_result()) from None


@app.get(
    "/api/tools",
    description=(
        "Machine-readable capability manifest for agents.\n\n"
        "Returns the same self-describing record as ``fatebridge describe`` for every\n"
        "catalog tool — parameters, types, surfaces, family — so an agent can\n"
        "enumerate the framework's capabilities and call conventions without scraping\n"
        "the Markdown docs. Derived from the central ToolSpec catalog, so it never\n"
        "drifts from the live tool set."
    ),
)
async def list_tools(
    family: str | None = None,
    q: str | None = None,
    tool: str | None = None,
    surface: ToolSurface | None = None,
    detail: Literal["index", "summary", "full"] = "full",
) -> ServiceResult:
    try:
        return discover_specs(
            CATALOG,
            family=family,
            q=q,
            tool=tool,
            surface=surface,
            detail=detail,
        )
    except ParameterError as exception:
        raise HTTPException(
            status_code=422, detail=exception.as_result()
        ) from exception


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8010")),
        log_level=get_log_level().lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
