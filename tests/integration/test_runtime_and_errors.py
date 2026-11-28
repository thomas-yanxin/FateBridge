"""Exercise configured runtime behavior and public errors across transports."""

import asyncio
import json
import os
from pathlib import Path
from threading import get_ident
from typing import Literal, NoReturn, Protocol

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from pydantic import BaseModel

import fatebridge.api as api_module
import fatebridge.mcp_server as mcp
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.cli import run as cli_run
from fatebridge.core import almanac, ephemeris_runtime
from fatebridge.core.astro.orbits import ApproximateEphemeris
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.predictive import _common as predictive_runtime
from fatebridge.core.receipt_models import RunMetadata
from fatebridge.core.requests.bazi import BaziBirthRequest
from fatebridge.services import run_metadata
from fatebridge.utils.errors import (
    EphemerisSourceError,
    error_response_payload,
    handle_calculation_error,
)
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.runtime import load_runtime_env, parse_allowed_origins
from tests.fixtures.surface_payloads import REST_POST_CASES, astro_payload
from tests.fixtures.transports import rest_handler
from tests.support.transports import call_calculation


def test_load_runtime_env_reads_local_env_without_overriding_existing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("API_PORT=9000\nLOG_LEVEL=debug\n", encoding="utf-8")

    monkeypatch.setenv("API_PORT", "0")
    monkeypatch.delenv("API_PORT")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    dotenv_settings = load_runtime_env(env_path)

    assert dotenv_settings["API_PORT"] == "9000"
    assert os.environ["API_PORT"] == "9000"
    assert os.environ["LOG_LEVEL"] == "WARNING"


@pytest.mark.parametrize(
    ("configured_origins", "expected_origins"),
    [
        (None, []),
        ("", []),
        (
            "http://a.test, http://b.test,  ,http://c.test",
            ["http://a.test", "http://b.test", "http://c.test"],
        ),
    ],
)
def test_cors_requires_explicit_origins(
    monkeypatch: pytest.MonkeyPatch,
    configured_origins: str | None,
    expected_origins: list[str],
) -> None:
    """An unconfigured deployment must not trust a development browser origin."""
    if configured_origins is None:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_ORIGINS", configured_origins)

    assert parse_allowed_origins() == expected_origins


def test_handle_calculation_error_returns_structured_validation_payload() -> None:
    payload = handle_calculation_error(ValueError("出生日期无效"), "命理分析计算")

    assert payload["error"] == "出生日期无效"
    assert payload["error_code"] == "validation_error"
    assert payload["status_code"] == 400
    assert payload["retryable"] is False


def test_error_response_serialization_preserves_structured_error_metadata() -> None:
    payload = {
        "error": "运行依赖缺失",
        "error_code": "dependency_missing",
        "status_code": 503,
        "retryable": False,
    }

    rendered = json.loads(
        format_json_response(error_response_payload(payload, "西占时运分析"))
    )

    assert rendered == {
        "error": "运行依赖缺失",
        "error_code": "dependency_missing",
        "status_code": 503,
        "retryable": False,
        "operation": "西占时运分析",
    }


def test_calculate_birth_route_executes_service_via_threadpool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The REST route must run the calculation off its event loop thread."""
    route_thread_id = get_ident()
    calculation_thread_ids: list[int] = []

    def observe_calculation_thread(
        spec: ToolSpec,
        request: BaseModel,
        *,
        options: ExecutionOptions,
    ) -> ServiceResult:
        calculation_thread_ids.append(get_ident())
        assert spec.name == "bazi_birth_chart"
        assert isinstance(request, BaziBirthRequest) and request.name == "张三"
        return execute_with_receipt(
            spec,
            request,
            options=options,
        )

    monkeypatch.setattr(api_module, "execute_with_receipt", observe_calculation_thread)
    request = BaziBirthRequest(
        name="张三",
        gender="男",
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.4737,
        birth_place="上海",
    )

    birth_route = rest_handler("bazi_birth_chart")
    result = asyncio.run(birth_route(request))

    assert result["analysis_type"] == "八字命盘"
    assert result["run_metadata"]["tool_name"] == "bazi_birth_chart"
    assert result["run_metadata"]["engine"] == "fatebridge-offline"
    assert result["run_metadata"]["run_id"]
    assert result["run_metadata"]["generated_at"]
    (calculation_thread_id,) = calculation_thread_ids
    assert calculation_thread_id != route_thread_id


def test_western_timing_route_uses_structured_service_error_status(
    rest: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing native dependency must reach the caller as HTTP 503."""
    monkeypatch.setattr(predictive_runtime, "swe", None)
    response = rest.post("/api/astrology/timing", json=astro_payload())

    assert response.status_code == 503
    assert response.json() == {
        "error": "西占推运与返照分析所需依赖缺失，请检查运行环境",
        "error_code": "dependency_missing",
        "retryable": False,
    }


def test_ready_endpoint_reports_required_and_optional_checks() -> None:
    api_module._reset_runtime_state_for_tests()

    client = TestClient(api_module.app)

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["core_api"]["ok"] is True
    assert payload["checks"]["offline_astrology"]["required"] is True
    assert payload["checks"]["western_predictive_runtime"]["required"] is False
    assert payload["checks"]["api_key_auth"]["enabled"] is False
    assert "api_key_quota" not in payload["checks"]
    assert isinstance(payload["checks"]["western_predictive_runtime"]["ok"], bool)


def test_ready_requires_available_offline_ephemeris(
    rest: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FATEBRIDGE_DE441_DIR", str(tmp_path))

    response = rest.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["offline_astrology"]["fallback_available"] is False

    monkeypatch.setattr(ephemeris_runtime, "swe", None)
    response = rest.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["offline_astrology"]["ok"] is False


def test_explicit_missing_de441_dir_raises_de441_archive_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FATEBRIDGE_DE441_DIR", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    almanac.get_solar_terms_for_year.cache_clear()
    try:
        with pytest.raises(EphemerisSourceError) as solar_err:
            almanac.get_solar_terms_for_year(2026, "UTC")
        assert solar_err.value.reason == "de441_archive_missing"

        with pytest.raises(EphemerisSourceError) as orbit_err:
            ApproximateEphemeris(2451545.0, 2451545.0).state("Pluto")
        assert orbit_err.value.reason == "de441_archive_missing"
    finally:
        almanac.get_solar_terms_for_year.cache_clear()


def test_metrics_endpoint_exposes_request_counters() -> None:
    api_module._reset_runtime_state_for_tests()

    client = TestClient(api_module.app)
    client.get("/health")
    client.get("/ready")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert (
        'fatebridge_http_requests_total{method="GET",path="/health",status="200"} 1'
        in response.text
    )
    assert (
        'fatebridge_http_requests_total{method="GET",path="/ready",status="200"} 1'
        in response.text
    )
    assert (
        'fatebridge_http_request_duration_seconds_sum{method="GET",path="/health"} '
        in response.text
    )
    assert 'fatebridge_readiness_state{status="ready"} 1' in response.text
    assert "fatebridge_api_key_auth_enabled 0" in response.text
    assert "fatebridge_api_keys_configured_total 0" in response.text
    assert "fatebridge_api_key_daily_quota" not in response.text


def test_repeated_public_requests_succeed() -> None:
    api_module._reset_runtime_state_for_tests()
    client = TestClient(api_module.app)

    for _ in range(2):
        response = client.post("/api/divination/gua", json={"queries": ["乾"]})
        assert response.status_code == 200


def test_api_key_auth_rejects_missing_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(
            header_name="X-API-Key",
            api_keys={"agent": "secret-key"},
        ),
    )
    client = TestClient(api_module.app)
    response = client.post("/api/divination/gua", json={"queries": ["乾"]})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "APIKey"
    assert response.json() == {
        "error": "缺少或无效的 API key",
        "error_code": "authentication_required",
        "retryable": False,
    }


def test_api_key_auth_keeps_ready_endpoint_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(
            header_name="X-API-Key",
            api_keys={"agent": "secret-key"},
        ),
    )
    client = TestClient(api_module.app)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_repeated_authenticated_requests_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_module._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(
            header_name="X-API-Key", api_keys={"agent": "secret-key"}
        ),
    )
    client = TestClient(api_module.app)
    headers = {"X-API-Key": "secret-key"}

    for _ in range(2):
        response = client.post(
            "/api/divination/gua", json={"queries": ["乾"]}, headers=headers
        )
        assert response.status_code == 200


def test_validation_feedback_is_only_returned_to_the_caller(
    caplog: pytest.LogCaptureFixture,
) -> None:
    message = "未识别的时区：private-name-ephemeris"
    payload = handle_calculation_error(ValueError(message), "测试操作")
    assert payload["error"] == message
    assert payload["error_code"] == "validation_error"
    assert "private-name-ephemeris" not in caplog.text


def test_internal_error_logs_type_and_location_without_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    try:
        raise RuntimeError("private-runtime-ephemeris")
    except RuntimeError as exc:
        payload = handle_calculation_error(exc, "测试操作")
    assert payload["error_code"] == "internal_error"
    assert "RuntimeError" in caplog.text
    assert (
        "test_internal_error_logs_type_and_location_without_exception_text:"
        in caplog.text
    )
    assert "private-runtime-ephemeris" not in caplog.text
    assert "private-runtime-ephemeris" not in payload["error"]


def test_mcp_outer_argument_validation_returns_structured_feedback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def call() -> CallToolResult:
        async with Client(mcp.app) as client:
            return await client.call_tool(
                "run_calculation",
                {
                    "tool": "bazi_birth_chart",
                    "arguments": "private-mcp-input",
                },
                raise_on_error=False,
            )

    result = asyncio.run(call())
    assert result.is_error
    payload = result.structured_content
    assert payload["error_code"] == "validation_error" and not payload["retryable"]
    (issue,) = payload["issues"]
    assert issue["path"] == "arguments" and issue["code"] == "dict_type"
    assert issue["message"]
    assert "private-mcp-input" not in caplog.text


class RuntimeApproximationCheck(Protocol):
    def __call__(self, record: ServiceResult, /) -> bool: ...


@pytest.mark.parametrize("stage", ["attachment", "validation"])
def test_metadata_failures_are_internal_and_consistent_in_all_transports(
    rest: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    stage: Literal["attachment", "validation"],
) -> None:
    """Runtime receipt failures must hide exception text on all transports."""

    def fail(
        record: ServiceResult,
        *,
        tool_name: str | None = None,
        approximate_record: RuntimeApproximationCheck | None = None,
    ) -> NoReturn:
        # note (metadata): Both receipt boundaries accept the full record and neither may expose it on failure.
        raise ValueError("private-server-error")

    if stage == "attachment":
        monkeypatch.setattr(run_metadata, "build_run_metadata", fail)
    else:
        monkeypatch.setattr(RunMetadata, "model_validate", fail)

    inputs = REST_POST_CASES["/api/bazi/birth-chart"]()
    http = rest.post("/api/bazi/birth-chart", json=inputs)

    async def call() -> CallToolResult:
        async with Client(mcp.app) as client:
            return await call_calculation(
                client, "bazi_birth_chart", inputs, raise_on_error=False
            )

    protocol = asyncio.run(call())
    args = ["bazi_birth_chart"]
    for key, value in inputs.items():
        if value is not None:
            args += [
                "--" + key.replace("_", "-"),
                json.dumps(value) if isinstance(value, bool) else str(value),
            ]
        else:
            pass
    code = cli_run(args)
    cli_output = json.loads(capsys.readouterr().out)
    assert http.status_code == 500 and protocol.is_error and code == 1
    payloads = [http.json(), protocol.structured_content, cli_output]
    for payload in payloads:
        assert payload["error_code"] == "internal_error"
        assert "private" not in json.dumps(payload)
    # note (parity): HTTP status and MCP operation labels are transport metadata.
    normalized = [
        {
            key: value
            for key, value in payload.items()
            if key not in {"status_code", "operation"}
        }
        for payload in payloads
    ]
    assert normalized[0] == normalized[1] == normalized[2]
    assert "private-server-error" not in caplog.text
    assert "ValueError" in caplog.text and ".fail:" in caplog.text


def test_extra_forbidden_suggestions_and_projection_suggestions_across_transports(
    rest: TestClient, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from fatebridge.application.projection import project_fields
    from fatebridge.utils.errors import ParameterError

    bad_payload = {
        **REST_POST_CASES["/api/bazi/birth-chart"](),
        "birth_huor": 10,
    }
    http = rest.post("/api/bazi/birth-chart", json=bad_payload)
    assert http.status_code == 422

    async def call_mcp() -> CallToolResult:
        async with Client(mcp.app) as client:
            return await call_calculation(
                client, "bazi_birth_chart", bad_payload, raise_on_error=False
            )

    mcp_res = asyncio.run(call_mcp())
    assert mcp_res.is_error

    req_file = tmp_path / "bad.json"
    req_file.write_text(json.dumps(bad_payload), encoding="utf-8")
    capsys.readouterr()
    code = cli_run(["bazi_birth_chart", "--request-file", str(req_file)])
    assert code == 1
    cli_res = json.loads(capsys.readouterr().out)

    for body in (http.json(), mcp_res.structured_content, cli_res):
        issue = body["issues"][0]
        assert issue["path"] == "birth_huor"
        assert issue["code"] == "extra_forbidden"
        assert "birth_hour" in issue["constraints"]["suggestions"]

    with pytest.raises(ParameterError) as proj_err:
        project_fields(
            {"bazi_birth": {"day_master": 1}, "summary": "x"}, ["bazi_birth.day_mastr"]
        )
    proj_issue = proj_err.value.issues[0]
    assert proj_issue["code"] == "unknown_projection_path"
    assert proj_issue["constraints"]["suggestions"] == ["day_master"]


def test_request_service_drift_is_not_silently_ignored() -> None:
    from pydantic import BaseModel

    from fatebridge.application.bindings import bind_kwargs
    from fatebridge.application.execution import invoke_validated_service
    from fatebridge.application.tool_spec import ToolSpec

    class Request(BaseModel):
        value: int
        new_option: bool = True

    def service(value: int) -> dict[str, int]:
        return {"value": value}

    spec = ToolSpec(
        name="t",
        bind=bind_kwargs(service),
        request_model=Request,
        summary="",
        operation_label_zh="测试",
        family="",
    )
    with pytest.raises(TypeError, match="new_option"):
        invoke_validated_service(spec, Request(value=1))
