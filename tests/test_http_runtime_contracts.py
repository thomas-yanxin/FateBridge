"""Regression checks for authentication, HTTP metrics, and startup ordering."""

import os
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from fatebridge import api as api_module
from fatebridge.utils.runtime import parse_api_keys


@pytest.mark.parametrize("raw", ["", " ", "\n\t"])
def test_empty_api_key_configuration_remains_optional(raw):
    assert parse_api_keys(raw) == {}


@pytest.mark.parametrize(
    "raw",
    [
        "agent:",
        ":private-value",
        ",",
        "agent:private-value,",
        "agent:private-value,,second:private-other",
        "agent:private-value,agent:private-other",
        "key2:private-value,private-other",
    ],
)
def test_malformed_nonempty_api_key_configuration_is_rejected(raw):
    with pytest.raises(ValueError, match="FATEBRIDGE_API_KEYS") as error:
        parse_api_keys(raw)
    assert "private-value" not in str(error.value)
    assert "private-other" not in str(error.value)


def test_valid_named_and_unnamed_keys_are_preserved():
    assert parse_api_keys("one") == {"key1": "one"}
    assert parse_api_keys(" agent : one , two ") == {"agent": "one", "key2": "two"}
    assert parse_api_keys("agent:one:two") == {"agent": "one:two"}


def test_api_import_fails_for_malformed_api_key_configuration():
    env = {**os.environ, "FATEBRIDGE_API_KEYS": "agent:"}
    result = subprocess.run(
        [sys.executable, "-c", "import fatebridge.api"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "ValueError: FATEBRIDGE_API_KEYS" in result.stderr


@pytest.mark.parametrize("auth_enabled", [False, True])
def test_arbitrary_urls_and_methods_have_bounded_metrics(monkeypatch, auth_enabled):
    metrics = api_module.RuntimeMetrics()
    monkeypatch.setattr(api_module, "REQUEST_METRICS", metrics)
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(
            header_name="X-API-Key",
            api_keys={"agent": "secret"} if auth_enabled else {},
        ),
    )
    with TestClient(api_module.app) as client:
        for index in range(50):
            unknown = f"/unknown-{index}"
            assert client.get(unknown).status_code == (401 if auth_enabled else 404)
            assert client.request(f"CUSTOM{index}", unknown).status_code == (
                401 if auth_enabled else 404
            )
            client.options(unknown)
        assert client.post("/api/cn/bazi/birth", json={}).status_code == (
            401 if auth_enabled else 422
        )

    # Three unknown-path method labels, plus the fixed business route.
    assert len(metrics._request_counts) == 4
    assert len(metrics._duration_counts) == 4
    assert len(metrics._duration_sums) == 4
    assert {path for _, path in metrics._duration_counts} == {
        "/unknown",
        "/api/cn/bazi/birth",
    }
    assert ("OTHER", "/unknown") in metrics._duration_counts


def test_metrics_use_route_templates_before_routing_and_for_wrong_method(monkeypatch):
    app = FastAPI()
    app.add_api_route("/items/{item_id}", lambda item_id: item_id, methods=["GET"])
    monkeypatch.setattr(api_module, "app", app)
    for method in ("GET", "POST"):
        request = Request({"type": "http", "path": "/items/123", "method": method})
        assert api_module._metrics_route_path(request) == "/items/{item_id}"


@pytest.mark.parametrize(
    "body",
    [
        "{}",
        '{"name":"sensitive-name","birth_year":"sensitive-value"}',
        '{"name":"sensitive-malformed-json",',
    ],
)
def test_invalid_http_bodies_use_safe_common_error_envelope(monkeypatch, body):
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api_module.app) as client:
        response = client.post(
            "/api/cn/bazi/birth",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert {k: v for k, v in response.json().items() if k != "issues"} == {
        "error": "请求参数无效",
        "error_code": "validation_error",
        "retryable": False,
    }
    assert response.json()["issues"]
    assert "sensitive" not in response.text


def test_api_loads_dotenv_before_ephemeris_import(tmp_path):
    pytest.importorskip("swisseph")
    env_path = tmp_path / ".env"
    expected_path = str(tmp_path / "configured-ephe")
    env_path.write_text(f"SE_EPHE_PATH={expected_path}\n", encoding="utf-8")
    script = """
import os
import sys
from pathlib import Path
import swisseph
from fatebridge.utils import runtime

runtime.DEFAULT_ENV_PATH = Path(sys.argv[1])
calls = []
swisseph.set_ephe_path = calls.append
import fatebridge.api
assert calls, 'ephemeris was not configured'
assert calls[0] == sys.argv[2], (calls, os.environ.get('SE_EPHE_PATH'))
"""
    env = {**os.environ, "FATEBRIDGE_API_KEYS": ""}
    env.pop("SE_EPHE_PATH", None)
    result = subprocess.run(
        [sys.executable, "-c", script, str(env_path), expected_path],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_openapi_validation_error_schema_matches_real_http_response(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api_module.app) as client:
        schema = client.get("/openapi.json").json()
        response = client.post("/api/cn/bazi/birth", json={})
    for routes in schema["paths"].values():
        for operation in routes.values():
            advertised = operation["responses"].get("422")
            if advertised:
                assert advertised["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorEnvelope"
                }
    error_schema = schema["components"]["schemas"]["ErrorEnvelope"]
    assert set(error_schema["required"]) <= set(response.json())
    assert set(response.json()) <= set(error_schema["properties"])
    assert {"trace_id", "parent_run_id"} <= set(error_schema["properties"])
    assert response.status_code == 422
    assert api_module.ErrorEnvelope.model_validate(response.json()).model_dump(
        exclude_none=True
    ) == (response.json())
