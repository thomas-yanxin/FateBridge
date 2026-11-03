from __future__ import annotations

"""
FastAPI REST server for FateBridge calculations.
Provides HTTP endpoints for birth analysis, timing, and divination calculations.
"""

import asyncio
import hmac
import logging
import os
import time
from collections import defaultdict
from copy import deepcopy
from threading import Lock
from typing import Any, Callable, Dict, Literal, Optional, Tuple

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response
from starlette.routing import Match

from fatebridge.utils.runtime import (
    get_api_key_header_name,
    get_log_level,
    load_runtime_env,
    parse_allowed_origins,
    parse_api_keys,
)

# Domain imports initialize Swiss Ephemeris. Load its configuration first.
load_runtime_env()

# isort: split

from fatebridge import __version__ as APP_VERSION
from fatebridge.application.discovery import discover_specs
from fatebridge.application.result_delivery import RESULT_STORE
from fatebridge.application.scenarios import discover_scenarios
from fatebridge.core.astro import runtime as astrology_core
from fatebridge.core.execution_context import correlate_error, safe_correlation
from fatebridge.core.predictive import _common as astrology_predictive_core
from fatebridge.services.run_metadata import attach_run_metadata
from fatebridge.utils.errors import (
    ErrorEnvelope,
    ParameterError,
    validation_error_result,
)

# ============================================================================
# Setup
# ============================================================================

# Configure logging
logging.basicConfig(
    level=getattr(logging, get_log_level(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="FateBridge API",
    description="API for FateBridge calculations across BaZi, divination, timing, and offline astrology charts with local ephemeris preference",
    version=APP_VERSION,
    responses={422: {"model": ErrorEnvelope}},
)

# ============================================================================
# CORS Configuration - FIXED SECURITY ISSUE
# ============================================================================

# Get allowed origins from environment variable, default to localhost for development
ALLOWED_ORIGINS = parse_allowed_origins()
API_KEY_HEADER_NAME = get_api_key_header_name()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,  # FIXED: Changed from True (security issue)
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", API_KEY_HEADER_NAME],
)


_DEFAULT_HEAVY_CALC_MAX_CONCURRENCY = min(4, max(1, os.cpu_count() or 1))
try:
    HEAVY_CALC_MAX_CONCURRENCY = max(
        1,
        int(
            os.getenv(
                "FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY",
                str(_DEFAULT_HEAVY_CALC_MAX_CONCURRENCY),
            )
        ),
    )
except ValueError:
    logger.warning(
        "Invalid integer for %s, falling back to %s",
        "FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY",
        _DEFAULT_HEAVY_CALC_MAX_CONCURRENCY,
    )
    HEAVY_CALC_MAX_CONCURRENCY = _DEFAULT_HEAVY_CALC_MAX_CONCURRENCY
HEAVY_CALC_SEMAPHORE: Optional[asyncio.Semaphore] = None
HEAVY_CALC_SEMAPHORE_LOOP: Optional[asyncio.AbstractEventLoop] = None


def _prometheus_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class RuntimeMetrics:
    def __init__(self) -> None:
        self._request_counts: Dict[Tuple[str, str, str], float] = defaultdict(float)
        self._duration_sums: Dict[Tuple[str, str], float] = defaultdict(float)
        self._duration_counts: Dict[Tuple[str, str], float] = defaultdict(float)
        self._lock = Lock()

    def observe(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        status = str(status_code)
        with self._lock:
            self._request_counts[(method, path, status)] += 1.0
            self._duration_sums[(method, path)] += duration_seconds
            self._duration_counts[(method, path)] += 1.0

    def render_prometheus(
        self,
        *,
        readiness_status: str,
        api_key_auth_enabled: bool,
        configured_api_keys: int,
    ) -> str:
        with self._lock:
            request_counts = dict(self._request_counts)
            duration_sums = dict(self._duration_sums)
            duration_counts = dict(self._duration_counts)

        lines = [
            "# HELP fatebridge_http_requests_total Total HTTP requests handled by FateBridge.",
            "# TYPE fatebridge_http_requests_total counter",
        ]
        for (method, path, status), count in sorted(request_counts.items()):
            lines.append(
                'fatebridge_http_requests_total{method="%s",path="%s",status="%s"} %.1f'
                % (
                    _prometheus_escape(method),
                    _prometheus_escape(path),
                    _prometheus_escape(status),
                    count,
                )
            )

        lines.extend(
            [
                "# HELP fatebridge_http_request_duration_seconds_sum Total request duration in seconds grouped by method and path.",
                "# TYPE fatebridge_http_request_duration_seconds_sum counter",
            ]
        )
        for (method, path), duration_sum in sorted(duration_sums.items()):
            lines.append(
                'fatebridge_http_request_duration_seconds_sum{method="%s",path="%s"} %.6f'
                % (
                    _prometheus_escape(method),
                    _prometheus_escape(path),
                    duration_sum,
                )
            )

        lines.extend(
            [
                "# HELP fatebridge_http_request_duration_seconds_count Number of observed requests grouped by method and path.",
                "# TYPE fatebridge_http_request_duration_seconds_count counter",
            ]
        )
        for (method, path), count in sorted(duration_counts.items()):
            lines.append(
                'fatebridge_http_request_duration_seconds_count{method="%s",path="%s"} %.1f'
                % (
                    _prometheus_escape(method),
                    _prometheus_escape(path),
                    count,
                )
            )

        lines.extend(
            [
                "# HELP fatebridge_readiness_state Current readiness state of the API.",
                "# TYPE fatebridge_readiness_state gauge",
                'fatebridge_readiness_state{status="%s"} 1'
                % _prometheus_escape(readiness_status),
                "# HELP fatebridge_api_key_auth_enabled Whether API key authentication is enabled.",
                "# TYPE fatebridge_api_key_auth_enabled gauge",
                f"fatebridge_api_key_auth_enabled {1 if api_key_auth_enabled else 0}",
                "# HELP fatebridge_api_keys_configured_total Number of configured API keys.",
                "# TYPE fatebridge_api_keys_configured_total gauge",
                f"fatebridge_api_keys_configured_total {configured_api_keys}",
            ]
        )
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._request_counts.clear()
            self._duration_sums.clear()
            self._duration_counts.clear()


class ApiKeyAuthenticator:
    def __init__(self, *, header_name: str, api_keys: Dict[str, str]) -> None:
        self.header_name = header_name
        self.api_keys = dict(api_keys)
        # Order-stable list for constant-time comparison against every secret.
        self._known_secrets: Tuple[Tuple[bytes, str], ...] = tuple(
            (secret.encode("utf-8"), key_id) for key_id, secret in self.api_keys.items()
        )

    @property
    def enabled(self) -> bool:
        return bool(self._known_secrets)

    def authenticate(self, request: Request) -> Optional[str]:
        if not self.enabled:
            return None

        secret = request.headers.get(self.header_name)
        if not secret:
            return None

        # hmac.compare_digest avoids short-circuiting on mismatch byte,
        # preventing timing-based key probing. We must compare against every
        # configured secret unconditionally so total runtime does not leak
        # how many candidates matched a prefix of the supplied value.
        candidate_bytes = secret.encode("utf-8")
        matched_id: Optional[str] = None
        for known_secret, key_id in self._known_secrets:
            if hmac.compare_digest(candidate_bytes, known_secret):
                matched_id = key_id
        return matched_id


API_KEY_EXEMPT_PATHS = frozenset(
    {
        "/health",
        "/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)
API_KEY_AUTHENTICATOR = ApiKeyAuthenticator(
    header_name=API_KEY_HEADER_NAME,
    api_keys=parse_api_keys(),
)
REQUEST_METRICS = RuntimeMetrics()


def _build_readiness_payload() -> Dict[str, Any]:
    from importlib.util import find_spec

    western_swisseph_available = astrology_predictive_core.swe is not None
    checks: Dict[str, Dict[str, Any]] = {
        "core_api": {
            "ok": True,
            "required": True,
            "detail": "FastAPI app initialized",
        },
        "offline_astrology": {
            "ok": True,
            "required": True,
            "swisseph_available": astrology_core.swe is not None,
            "fallback_available": True,
        },
        "western_predictive_runtime": {
            "ok": western_swisseph_available,
            "required": False,
            "swisseph_available": astrology_predictive_core.swe is not None,
            "kerykeion_available": find_spec("kerykeion") is not None,
            "engine_backend": "fatebridge_swisseph_native",
        },
        "api_key_auth": {
            "ok": True,
            "required": False,
            "enabled": API_KEY_AUTHENTICATOR.enabled,
            "header_name": API_KEY_AUTHENTICATOR.header_name,
            "configured_keys": len(API_KEY_AUTHENTICATOR.api_keys),
        },
    }
    required_checks_ok = all(
        item["ok"] for item in checks.values() if item.get("required")
    )
    return {
        "status": "ready" if required_checks_ok else "not_ready",
        "checks": checks,
    }


def _build_authentication_detail() -> Dict[str, Any]:
    return _build_error_detail(
        {
            "error": "缺少或无效的 API key",
            "error_code": "authentication_required",
            "retryable": False,
        }
    )


def _reset_runtime_state_for_tests() -> None:
    global HEAVY_CALC_SEMAPHORE, HEAVY_CALC_SEMAPHORE_LOOP
    REQUEST_METRICS.reset()
    HEAVY_CALC_SEMAPHORE = None
    HEAVY_CALC_SEMAPHORE_LOOP = None


def _metrics_route_path(request: Request) -> str:
    """Resolve a fixed route label even before routing/authentication runs."""
    partial_path: Optional[str] = None
    for route in app.routes:
        match, _ = route.matches(request.scope)
        route_path = getattr(route, "path", "/unknown")
        if match == Match.FULL:
            return str(route_path)
        if match == Match.PARTIAL and partial_path is None:
            partial_path = str(route_path)
    return partial_path or "/unknown"


@app.middleware("http")
async def instrument_request_lifecycle(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    path = request.url.path
    method = request.method.upper()
    metrics_path = _metrics_route_path(request)
    metrics_method = (
        method
        if method
        in {
            "GET",
            "HEAD",
            "POST",
            "PUT",
            "DELETE",
            "CONNECT",
            "OPTIONS",
            "TRACE",
            "PATCH",
        }
        else "OTHER"
    )

    if method != "OPTIONS" and path not in API_KEY_EXEMPT_PATHS:
        if API_KEY_AUTHENTICATOR.enabled:
            authenticated_key_id = API_KEY_AUTHENTICATOR.authenticate(request)
            if authenticated_key_id is None:
                auth_response = JSONResponse(
                    status_code=401,
                    content=_build_authentication_detail(),
                )
                REQUEST_METRICS.observe(
                    method=metrics_method,
                    path=metrics_path,
                    status_code=401,
                    duration_seconds=0.0,
                )
                return auth_response

            request.state.api_key_id = authenticated_key_id

    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        REQUEST_METRICS.observe(
            method=metrics_method,
            path=metrics_path,
            status_code=500,
            duration_seconds=time.perf_counter() - started_at,
        )
        raise

    REQUEST_METRICS.observe(
        method=metrics_method,
        path=metrics_path,
        status_code=response.status_code,
        duration_seconds=time.perf_counter() - started_at,
    )
    return response


def _build_error_detail(result: Dict[str, Any]) -> Dict[str, Any]:
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
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Validation errors may contain the submitted body or secrets in messages.
    result = correlate_error(
        validation_error_result(exc),
        safe_correlation(dict(request.query_params)),
    )
    return JSONResponse(
        status_code=result["status_code"],
        content=_build_error_detail(result),
    )


@app.exception_handler(HTTPException)
async def _http_error_envelope(request: Request, exc: HTTPException) -> JSONResponse:
    """Render every HTTPException as a flat top-level error envelope.

    REST historically nested the error under FastAPI's ``detail`` key, while MCP
    and the CLI emit a flat ``{error, error_code, retryable}``. This handler
    flattens the HTTP body so all three surfaces agree — an agent branches on the
    same top-level ``error_code`` everywhere — and backfills ``error_code`` for
    the bare-string 400/500 paths that previously carried none. The exception
    object keeps its ``.detail`` intact for in-process callers that inspect it.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "error_code" in detail:
        body = _build_error_detail({**detail, "error": detail.get("error")})
    else:
        body = _build_error_detail(
            {
                "error": detail,
                "error_code": (
                    "validation_error" if exc.status_code == 400 else "internal_error"
                ),
                "retryable": False,
            }
        )
    body = correlate_error(body, safe_correlation(dict(request.query_params)))
    return JSONResponse(status_code=exc.status_code, content=body)


def _get_heavy_calc_semaphore() -> asyncio.Semaphore:
    global HEAVY_CALC_SEMAPHORE, HEAVY_CALC_SEMAPHORE_LOOP
    loop = asyncio.get_running_loop()
    if HEAVY_CALC_SEMAPHORE is not None and HEAVY_CALC_SEMAPHORE_LOOP is None:
        HEAVY_CALC_SEMAPHORE_LOOP = loop
        return HEAVY_CALC_SEMAPHORE
    if HEAVY_CALC_SEMAPHORE is None or HEAVY_CALC_SEMAPHORE_LOOP is not loop:
        HEAVY_CALC_SEMAPHORE = asyncio.Semaphore(HEAVY_CALC_MAX_CONCURRENCY)
        HEAVY_CALC_SEMAPHORE_LOOP = loop
    return HEAVY_CALC_SEMAPHORE


async def _execute_service(
    service: Callable[..., Dict[str, Any]],
    *args: Any,
    error_is_fatal: Optional[Callable[[Dict[str, Any]], bool]] = None,
    tool_name: Optional[str] = None,
    cpu_bound: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    if cpu_bound:
        async with _get_heavy_calc_semaphore():
            result = await run_in_threadpool(service, *args, **kwargs)
    else:
        result = await run_in_threadpool(service, *args, **kwargs)
    fatal_error = error_is_fatal(result) if error_is_fatal else "error" in result
    if fatal_error:
        raise HTTPException(
            status_code=int(result.get("status_code", 500)),
            detail=_build_error_detail(result),
        )
    # tool_name is supplied by the catalog registrar (spec.run_metadata_name);
    # the neutral fallback only guards a stray non-catalog caller.
    return attach_run_metadata(result, tool_name=tool_name or "unknown_tool")


# ============================================================================
# Request/Response Models
# ============================================================================


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check() -> JSONResponse:
    """Readiness endpoint that reports required and optional runtime checks."""
    payload = _build_readiness_payload()
    status_code = 200 if payload["status"] == "ready" else 503
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/metrics")
async def metrics_endpoint() -> PlainTextResponse:
    """Prometheus-style text metrics for request volume and readiness state."""
    readiness_status = _build_readiness_payload()["status"]
    return PlainTextResponse(
        REQUEST_METRICS.render_prometheus(
            readiness_status=readiness_status,
            api_key_auth_enabled=API_KEY_AUTHENTICATOR.enabled,
            configured_api_keys=len(API_KEY_AUTHENTICATOR.api_keys),
        ),
        media_type="text/plain; version=0.0.4",
    )


# ============================================================================
# Main
# ============================================================================


# ============================================================================
# Catalog-driven REST registration. Every business POST route is declared once
# in fatebridge/services/tool_catalog.py and mounted here. To add a route, edit
# the catalog — not this file.
# ============================================================================

from fatebridge.services.tool_catalog import (  # noqa: E402
    CATALOG,
    rest_specs,
)
from fatebridge.transports.rest import register_rest

register_rest(
    app,
    rest_specs(),
    execute_service=_execute_service,
    logger=logger,
)


def _contract_openapi() -> Dict[str, Any]:
    """Describe middleware authentication without changing its runtime policy."""
    if app.openapi_schema is None:
        app.openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
    schema = deepcopy(app.openapi_schema)
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["APIKey"] = {
        "type": "apiKey",
        "in": "header",
        "name": API_KEY_AUTHENTICATOR.header_name,
    }
    if API_KEY_AUTHENTICATOR.enabled:
        for path, operations in schema["paths"].items():
            if path not in API_KEY_EXEMPT_PATHS:
                for operation in operations.values():
                    operation["security"] = [{"APIKey": []}]
    return schema


app.openapi = _contract_openapi  # type: ignore[method-assign]


@app.get("/api/results/{result_id}")
async def result_manifest(result_id: str) -> Dict[str, Any]:
    """Read the manifest of a retained result under normal API authentication."""
    try:
        return RESULT_STORE.manifest(result_id)
    except ParameterError as exc:
        raise HTTPException(status_code=404, detail=exc.as_result()) from None


@app.get("/api/results/{result_id}/pages")
async def result_page(
    result_id: str,
    offset: int = Query(default=0, ge=0),
    path: Optional[str] = Query(default=None, max_length=1000),
) -> Dict[str, Any]:
    """Retrieve a bounded page or field from the original run, without recalculation."""
    try:
        return RESULT_STORE.page(result_id, offset, path)
    except ParameterError as exc:
        raise HTTPException(status_code=404, detail=exc.as_result()) from None


@app.get("/api/results/{result_id}/verified")
async def verified_result_page(
    result_id: str,
    expected_sha256: str = Query(pattern=r"^[0-9a-f]{64}$"),
    expected_run_id: str = Query(pattern=r"^[A-Za-z0-9_-]{1,128}$"),
    offset: int = Query(default=0, ge=0),
    path: Optional[str] = Query(default=None, max_length=1000),
) -> Dict[str, Any]:
    """Verify the full original payload before reading one bounded page."""
    try:
        return await run_in_threadpool(
            RESULT_STORE.verified_page,
            result_id,
            expected_sha256,
            expected_run_id,
            offset,
            path,
        )
    except ParameterError as exc:
        raise HTTPException(status_code=422, detail=exc.as_result()) from None


@app.get("/api/tools")
async def list_tools(
    family: Optional[str] = None,
    scenario: Optional[str] = None,
    q: Optional[str] = None,
    tool: Optional[str] = None,
    surface: Optional[Literal["rest", "mcp", "cli"]] = None,
    detail: Literal["summary", "full"] = "full",
) -> Dict[str, Any]:
    """Machine-readable capability manifest for agents.

    Returns the same self-describing record as ``fatebridge describe`` for every
    catalog tool — parameters, types, surfaces, family — so an agent can
    enumerate the framework's capabilities and call conventions without scraping
    the Markdown docs. Derived from the central ToolSpec catalog, so it never
    drifts from the live tool set.
    """
    try:
        return discover_specs(
            CATALOG,
            family=family,
            scenario=scenario,
            q=q,
            tool=tool,
            surface=surface,
            detail=detail,
        )
    except ParameterError as exc:
        raise HTTPException(status_code=422, detail=exc.as_result())


@app.get("/api/scenarios")
async def list_scenarios(
    scenario: Optional[str] = None,
    surface: Optional[Literal["rest", "mcp", "cli"]] = None,
    detail: Literal["summary", "full"] = "full",
) -> Dict[str, Any]:
    """Packaged scenario routing joined to the current central tool catalog."""
    try:
        return discover_scenarios(
            CATALOG, scenario=scenario, surface=surface, detail=detail
        )
    except ParameterError as exc:
        raise HTTPException(status_code=422, detail=exc.as_result())


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8010")),
        log_level=get_log_level().lower(),
    )


if __name__ == "__main__":
    main()
