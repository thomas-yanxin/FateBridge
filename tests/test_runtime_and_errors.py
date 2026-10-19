import asyncio
import json
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.api as api_module
import fatebridge.application.execution as execution
import fatebridge.mcp_server as mcp
from fatebridge import mcp_server as fastmcp_server
from fatebridge.cli import run as cli_run
from fatebridge.core.requests.bazi import BaziBirthRequest
from fatebridge.core.requests.western_timing import WesternTimingRequest
from fatebridge.utils.errors import handle_calculation_error
from fatebridge.utils.formatting import format_error_response
from fatebridge.utils.runtime import (
    load_runtime_env,
    parse_allowed_origins,
    parse_api_keys,
)
from tests.fixtures.surface_payloads import REST_POST_CASES
from tests.fixtures.transports import rest_handler

calculate_birth = rest_handler("bazi_birth")
calculate_western_timing = rest_handler("western_timing_analysis")


def _build_birth_payload() -> dict:
    return {
        "name": "测试者",
        "birth_year": 1990,
        "birth_month": 4,
        "birth_day": 6,
        "birth_hour": 9,
        "birth_minute": 33,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 121.4667,
        "birth_latitude": 31.2167,
        "birth_place": "上海",
    }


def test_load_runtime_env_reads_local_env_without_overriding_existing_values(
    tmp_path, monkeypatch
):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "API_PORT=9000\nLOG_LEVEL=debug\nALLOWED_ORIGINS=http://a.test, http://b.test\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("API_PORT", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    loaded = load_runtime_env(env_path)

    assert loaded["API_PORT"] == "9000"
    assert os.environ["API_PORT"] == "9000"
    assert os.environ["LOG_LEVEL"] == "WARNING"


def test_parse_allowed_origins_filters_blank_entries(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS", "http://a.test, http://b.test,  ,http://c.test"
    )

    assert parse_allowed_origins() == [
        "http://a.test",
        "http://b.test",
        "http://c.test",
    ]


def test_parse_api_keys_supports_named_and_unnamed_entries(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_API_KEYS", "agent:secret-a, secret-b")

    assert parse_api_keys() == {
        "agent": "secret-a",
        "key2": "secret-b",
    }


def test_handle_calculation_error_returns_structured_validation_payload():
    payload = handle_calculation_error(ValueError("出生日期无效"), "命理分析计算")

    assert payload["error"] == "出生日期无效"
    assert payload["error_code"] == "validation_error"
    assert payload["status_code"] == 400
    assert payload["retryable"] is False


def test_format_error_response_preserves_structured_error_metadata():
    payload = {
        "error": "运行依赖缺失",
        "error_code": "dependency_missing",
        "status_code": 503,
        "retryable": False,
    }

    rendered = json.loads(format_error_response(payload, "西占时运分析"))

    assert rendered == {
        "error": "运行依赖缺失",
        "error_code": "dependency_missing",
        "status_code": 503,
        "retryable": False,
        "operation": "西占时运分析",
    }


def test_cli_entrypoints_are_callable():
    assert callable(api_module.main)
    assert callable(fastmcp_server.main)


def test_calculate_birth_route_executes_service_via_threadpool(monkeypatch):
    captured = {}

    async def fake_run_in_threadpool(func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "ok"}

    monkeypatch.setattr(api_module, "run_in_threadpool", fake_run_in_threadpool)

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

    result = asyncio.run(calculate_birth(request))

    assert result["status"] == "ok"
    assert result["run_metadata"]["tool_name"] == "bazi_birth"
    assert result["run_metadata"]["engine"] == "fatebridge-offline"
    assert result["run_metadata"]["run_id"]
    assert result["run_metadata"]["trace_id"]
    assert result["run_metadata"]["generated_at"]
    from fatebridge.application.execution import execute_tool

    assert captured["func"] is execute_tool
    assert captured["args"][0].key == "bazi_birth"
    assert captured["args"][1].name == "张三"


def test_calculate_birth_route_includes_snapshot_contract():
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

    result = asyncio.run(calculate_birth(request))

    assert "person_info" in result["bazi_birth"]
    assert "four_pillars" in result["bazi_birth"]
    assert "snapshot_text" in result
    assert "snapshot_export" in result
    assert "[起盘信息]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]
    assert result["run_metadata"]["tool_name"] == "bazi_birth"


def test_western_timing_route_uses_structured_service_error_status(monkeypatch):
    async def fake_run_in_threadpool(func, *args, **kwargs):
        return {
            "error": "运行依赖缺失",
            "error_code": "dependency_missing",
            "status_code": 503,
            "retryable": False,
        }

    monkeypatch.setattr(api_module, "run_in_threadpool", fake_run_in_threadpool)

    request = WesternTimingRequest(**_build_birth_payload())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(calculate_western_timing(request))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "error": "运行依赖缺失",
        "error_code": "dependency_missing",
        "retryable": False,
    }


def test_ready_endpoint_reports_required_and_optional_checks():
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


def test_metrics_endpoint_exposes_request_counters():
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


def test_repeated_public_requests_succeed():
    api_module._reset_runtime_state_for_tests()
    client = TestClient(api_module.app)

    for _ in range(2):
        response = client.post("/api/divination/gua", json={"query": "乾"})
        assert response.status_code == 200


def test_api_key_auth_rejects_missing_key_when_configured(monkeypatch):
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
    response = client.post("/api/divination/gua", json={"query": "乾"})

    assert response.status_code == 401
    # REST errors render as a flat top-level envelope (matching MCP/CLI), not
    # nested under FastAPI's ``detail`` key.
    assert response.json() == {
        "error": "缺少或无效的 API key",
        "error_code": "authentication_required",
        "retryable": False,
    }


def test_api_key_auth_accepts_valid_key_when_configured(monkeypatch):
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
    response = client.post(
        "/api/divination/gua",
        json={"query": "乾"},
        headers={"X-API-Key": "secret-key"},
    )

    assert response.status_code == 200


def test_api_key_auth_keeps_ready_endpoint_public(monkeypatch):
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


def test_repeated_authenticated_requests_succeed(monkeypatch):
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
            "/api/divination/gua", json={"query": "乾"}, headers=headers
        )
        assert response.status_code == 200


def test_value_error_logged_as_warning_without_traceback(caplog):
    """A user/domain input rejection (ValueError -> 400) must not log a full
    stack trace; that floods the error log with crash-looking noise."""
    import logging

    with caplog.at_level(logging.WARNING, logger="fatebridge.utils.errors"):
        handle_calculation_error(ValueError("未识别的六十四卦名称：ZZZ"), "卦义检索")

    records = [r for r in caplog.records if r.name == "fatebridge.utils.errors"]
    assert records, "expected a log record"
    for rec in records:
        assert rec.levelno == logging.WARNING
        assert rec.exc_info is None  # no traceback attached


def test_internal_error_logged_at_error_with_traceback(caplog):
    """A genuine internal fault (-> 500) should still log ERROR + traceback."""
    import logging

    with caplog.at_level(logging.WARNING, logger="fatebridge.utils.errors"):
        payload = handle_calculation_error(RuntimeError("boom"), "测试操作")

    assert payload["error_code"] == "internal_error"
    err_records = [
        r
        for r in caplog.records
        if r.name == "fatebridge.utils.errors" and r.levelno == logging.ERROR
    ]
    assert err_records, "expected an ERROR record for an internal fault"
    assert any(r.exc_info is not None for r in err_records)


@pytest.mark.parametrize("stage", ["attachment", "validation"])
def test_metadata_failures_are_internal_and_correlated_in_all_transports(
    monkeypatch, capsys, caplog, stage
):
    from fatebridge.services import run_metadata

    def fail(*args, **kwargs):
        raise ValueError("private-server-error")

    if stage == "attachment":
        monkeypatch.setattr(run_metadata, "attach_run_metadata", fail)
    else:
        original = execution.validate_output

        def validate(spec, result):
            if "run_metadata" in result:
                raise execution.OutputContractError("private-server-error")
            return original(spec, result)

        monkeypatch.setattr(execution, "validate_output", validate)

    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = REST_POST_CASES["/api/cn/bazi/birth"]()
    controls = {"trace_id": "review-trace", "parent_run_id": "review-parent"}
    http = TestClient(api.app).post("/api/cn/bazi/birth", json=inputs, params=controls)

    async def call():
        async with Client(mcp.app) as client:
            return await client.call_tool(
                "bazi_birth", {**inputs, **controls}, raise_on_error=False
            )

    protocol = asyncio.run(call())
    args = ["bazi_birth"]
    for key, value in {**inputs, **controls}.items():
        if value is not None:
            args += [
                "--" + key.replace("_", "-"),
                json.dumps(value) if isinstance(value, bool) else str(value),
            ]
    code = cli_run(args)
    cli_output = json.loads(capsys.readouterr().out)
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    payloads = [http.json(), protocol.structured_content, cli_output]
    for payload in payloads:
        assert payload["error_code"] == "internal_error"
        assert payload["trace_id"] == controls["trace_id"]
        assert payload["parent_run_id"] == controls["parent_run_id"]
        assert "private" not in json.dumps(payload)
    # REST conveys status on the HTTP response; MCP also labels the operation.
    normalized = [
        {
            key: value
            for key, value in payload.items()
            if key not in {"status_code", "operation"}
        }
        for payload in payloads
    ]
    assert normalized[0] == normalized[1] == normalized[2]
    # Sanitization must preserve the actual failure in server-side diagnostics.
    assert any(
        record.exc_info and "private-server-error" in str(record.exc_info[1])
        for record in caplog.records
        if record.name == "fatebridge.utils.errors"
    )
