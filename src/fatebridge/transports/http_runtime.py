"""Track REST authentication, readiness and request metrics."""

import hmac
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Final, Literal, TypedDict

from fastapi import Request

import fatebridge.core.ephemeris_runtime as ephemeris_runtime
from fatebridge.core.astro.de441_source import coefficient_files_available

API_KEY_EXEMPT_PATHS: Final = frozenset(
    {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}
)
READINESS_METRICS_MEDIA_TYPE: Final = "text/plain; version=0.0.4"
ReadinessStatus = Literal["ready", "not_ready"]


@dataclass(frozen=True, kw_only=True)
class ApiCredential:
    credential_id: str
    secret_bytes: bytes


class ApiKeyAuthenticator:
    def __init__(self, *, header_name: str, api_keys: dict[str, str]) -> None:
        self.header_name: str = header_name
        self.known_credentials: tuple[ApiCredential, ...] = tuple(
            ApiCredential(
                credential_id=credential_id, secret_bytes=secret.encode("utf-8")
            )
            for credential_id, secret in api_keys.items()
        )

    @property
    def is_enabled(self) -> bool:
        return bool(self.known_credentials)

    @property
    def configured_keys(self) -> int:
        return len(self.known_credentials)

    def authenticate(self, request: Request) -> str | None:
        submitted_secret = request.headers.get(self.header_name)
        if not submitted_secret:
            return None
        else:
            pass

        # note (authentication): Compare every credential so a match does not end the scan early.
        submitted_bytes = submitted_secret.encode("utf-8")
        matched_credential_id: str | None = None
        for credential in self.known_credentials:
            if hmac.compare_digest(submitted_bytes, credential.secret_bytes):
                matched_credential_id = credential.credential_id
            else:
                pass
        return matched_credential_id


class ReadinessCheck(TypedDict):
    ok: bool
    required: bool


class CoreApiCheck(ReadinessCheck):
    detail: str


class OfflineAstrologyCheck(ReadinessCheck):
    swisseph_available: bool
    fallback_available: bool


class PredictiveRuntimeCheck(ReadinessCheck):
    swisseph_available: bool
    engine_backend: str


class ApiAuthenticationCheck(ReadinessCheck):
    enabled: bool
    header_name: str
    configured_keys: int


class ReadinessChecks(TypedDict):
    core_api: CoreApiCheck
    offline_astrology: OfflineAstrologyCheck
    western_predictive_runtime: PredictiveRuntimeCheck
    api_key_auth: ApiAuthenticationCheck


class ReadinessPayload(TypedDict):
    status: ReadinessStatus
    checks: ReadinessChecks


def build_readiness_payload(authenticator: ApiKeyAuthenticator) -> ReadinessPayload:
    is_swisseph_available = ephemeris_runtime.swe is not None
    has_de441_coefficients = coefficient_files_available()
    checks: ReadinessChecks = {
        "core_api": {"ok": True, "required": True, "detail": "FastAPI app initialized"},
        "offline_astrology": {
            "ok": is_swisseph_available or has_de441_coefficients,
            "required": True,
            "swisseph_available": is_swisseph_available,
            "fallback_available": has_de441_coefficients,
        },
        "western_predictive_runtime": {
            "ok": is_swisseph_available,
            "required": False,
            "swisseph_available": is_swisseph_available,
            "engine_backend": "fatebridge_swisseph_native",
        },
        "api_key_auth": {
            "ok": True,
            "required": False,
            "enabled": authenticator.is_enabled,
            "header_name": authenticator.header_name,
            "configured_keys": authenticator.configured_keys,
        },
    }
    readiness_checks: tuple[ReadinessCheck, ...] = (
        checks["core_api"],
        checks["offline_astrology"],
        checks["western_predictive_runtime"],
        checks["api_key_auth"],
    )
    are_required_checks_ok = all(
        check["ok"] for check in readiness_checks if check["required"]
    )
    return {
        "status": "ready" if are_required_checks_ok else "not_ready",
        "checks": checks,
    }


@dataclass(kw_only=True)
class RequestDuration:
    request_count: int = 0
    total_seconds: float = 0.0


def prometheus_escape(label: str) -> str:
    return label.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class RuntimeMetrics:
    def __init__(self) -> None:
        self.request_counts: defaultdict[tuple[str, str, int], int] = defaultdict(int)
        self.request_durations: defaultdict[tuple[str, str], RequestDuration] = (
            defaultdict(RequestDuration)
        )
        self.lock: Lock = Lock()

    def observe(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        with self.lock:
            self.request_counts[(method, path, status_code)] += 1
            duration = self.request_durations[(method, path)]
            duration.request_count += 1
            duration.total_seconds += duration_seconds

    def render_prometheus(
        self,
        *,
        readiness_status: ReadinessStatus,
        api_key_auth_enabled: bool,
        configured_api_keys: int,
    ) -> str:
        with self.lock:
            request_counts = sorted(self.request_counts.items())
            request_durations = [
                (method, path, duration.request_count, duration.total_seconds)
                for (method, path), duration in sorted(self.request_durations.items())
            ]

        lines = [
            "# HELP fatebridge_http_requests_total Total HTTP requests handled by FateBridge.",
            "# TYPE fatebridge_http_requests_total counter",
            *(
                f'fatebridge_http_requests_total{{method="{prometheus_escape(method)}",path="{prometheus_escape(path)}",status="{status_code}"}} {count:.1f}'
                for (method, path, status_code), count in request_counts
            ),
            "# HELP fatebridge_http_request_duration_seconds_sum Total request duration in seconds grouped by method and path.",
            "# TYPE fatebridge_http_request_duration_seconds_sum counter",
            *(
                f'fatebridge_http_request_duration_seconds_sum{{method="{prometheus_escape(method)}",path="{prometheus_escape(path)}"}} {total_seconds:.6f}'
                for method, path, _, total_seconds in request_durations
            ),
            "# HELP fatebridge_http_request_duration_seconds_count Number of observed requests grouped by method and path.",
            "# TYPE fatebridge_http_request_duration_seconds_count counter",
            *(
                f'fatebridge_http_request_duration_seconds_count{{method="{prometheus_escape(method)}",path="{prometheus_escape(path)}"}} {count:.1f}'
                for method, path, count, _ in request_durations
            ),
            "# HELP fatebridge_readiness_state Current readiness state of the API.",
            "# TYPE fatebridge_readiness_state gauge",
            f'fatebridge_readiness_state{{status="{readiness_status}"}} 1',
            "# HELP fatebridge_api_key_auth_enabled Whether API key authentication is enabled.",
            "# TYPE fatebridge_api_key_auth_enabled gauge",
            f"fatebridge_api_key_auth_enabled {int(api_key_auth_enabled)}",
            "# HELP fatebridge_api_keys_configured_total Number of configured API keys.",
            "# TYPE fatebridge_api_keys_configured_total gauge",
            f"fatebridge_api_keys_configured_total {configured_api_keys}",
        ]
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self.lock:
            self.request_counts.clear()
            self.request_durations.clear()
