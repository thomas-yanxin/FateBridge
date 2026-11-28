"""Serve FateBridge calculations and capability discovery over HTTP."""

import logging
import time
import warnings
from collections.abc import Collection
from copy import deepcopy

from fastapi import FastAPI, HTTPException, Request
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
    get_api_host,
    get_api_key_header_name,
    get_api_port,
    get_log_level,
    load_runtime_env,
    parse_allowed_origins,
    parse_api_keys,
)

# note (startup): Load dotenv before importing code that configures Swiss Ephemeris.
load_runtime_env()

# isort: split

from fatebridge import __version__ as APP_VERSION
from fatebridge.application.discovery import (
    DiscoveryDetail,
    ToolSurface,
    discover_specs,
)
from fatebridge.application.execution import execute_with_receipt, run_tool
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.services.tool_catalog import all_catalog, rest_specs
from fatebridge.transports.http_runtime import (
    API_KEY_EXEMPT_PATHS,
    READINESS_METRICS_MEDIA_TYPE,
    ApiKeyAuthenticator,
    RuntimeMetrics,
    build_readiness_payload,
)
from fatebridge.transports.rest import register_batch_route, register_rest
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


def _reset_runtime_state_for_tests() -> None:
    REQUEST_METRICS.reset()


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
    ).model_dump(exclude_none=True)


@app.exception_handler(RequestValidationError)
async def _request_validation_error_envelope(
    _request: Request, exception: RequestValidationError
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
    allowed_fields: Collection[str] | None = None
    root_model: type[BaseModel] | None = None
    route = _request.scope.get("route")
    if isinstance(route, APIRoute) and route.dependant.body_params:
        body_type = route.dependant.body_params[0].field_info.annotation
        if isinstance(body_type, type) and issubclass(body_type, BaseModel):
            allowed_fields = body_type.model_fields.keys()
            root_model = body_type
    result = validation_issues_result(
        issues, allowed_fields=allowed_fields, root_model=root_model
    )
    return JSONResponse(
        status_code=result["status_code"],
        content=_build_error_detail(result),
    )


@app.exception_handler(HTTPException)
async def _http_error_envelope(
    _request: Request, exception: HTTPException
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
    return JSONResponse(status_code=exception.status_code, content=response_body)


async def _execute_service(
    spec: ToolSpec,
    request: BaseModel,
    *,
    include: list[str] | None = None,
    fields: list[str] | None = None,
    as_of: str | None = None,
) -> ServiceResult:
    outcome = await run_in_threadpool(
        run_tool,
        spec,
        request,
        include=include,
        fields=fields,
        as_of=as_of,
        executor=execute_with_receipt,
    )
    if outcome.failed:
        raise HTTPException(
            status_code=outcome.status_code,
            detail=_build_error_detail(outcome.payload),
        )
    return outcome.payload


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


exposed_rest_specs = rest_specs()
register_rest(app, exposed_rest_specs, execute_service=_execute_service)
register_batch_route(app, exposed_rest_specs)

# note (Pydantic): Build deferred body adapters while FastAPI's field-alias warning is filtered.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=UnsupportedFieldAttributeWarning)
    for route in app.routes:
        if isinstance(route, APIRoute):
            for body_parameter in route.dependant.body_params:
                body_parameter._type_adapter.rebuild()


@app.get(
    "/api/tools",
    description=(
        "Machine-readable capability manifest for agents.\n\n"
        "Returns the same self-describing record as `fatebridge discover` for every\n"
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
    tools: str | None = None,
    surface: ToolSurface | None = None,
    detail: DiscoveryDetail = "summary",
    include_output_schema: bool = False,
) -> ServiceResult:
    try:
        return discover_specs(
            all_catalog(),
            family=family,
            q=q,
            tool=tool,
            tools=tools,
            surface=surface,
            detail=detail,
            include_output_schema=include_output_schema,
        )
    except ParameterError as exception:
        raise HTTPException(
            status_code=exception.status_code, detail=exception.as_result()
        ) from exception


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=get_api_host(),
        port=get_api_port(),
        log_level=get_log_level().lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
