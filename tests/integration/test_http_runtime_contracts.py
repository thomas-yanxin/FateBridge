"""Regression checks for authentication, HTTP metrics, and startup ordering."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import fatebridge.api as api_module
from fatebridge.utils.errors import ErrorEnvelope
from fatebridge.utils.runtime import parse_api_keys
from tests.support.transports import rest

__all__ = ["rest"]


@pytest.mark.parametrize("raw", ["", " ", "\n\t"])
def test_empty_api_key_configuration_remains_optional(raw: str) -> None:
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
def test_malformed_nonempty_api_key_configuration_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match="FATEBRIDGE_API_KEYS") as error:
        parse_api_keys(raw)
    assert "private-value" not in str(error.value)
    assert "private-other" not in str(error.value)


def test_valid_named_and_unnamed_keys_are_preserved() -> None:
    assert parse_api_keys("one") == {"key1": "one"}
    assert parse_api_keys(" agent : one , two ") == {"agent": "one", "key2": "two"}
    assert parse_api_keys("agent:one:two") == {"agent": "one:two"}


def test_api_import_fails_for_malformed_api_key_configuration() -> None:
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


@pytest.mark.parametrize("is_auth_enabled", [False, True])
def test_arbitrary_urls_and_methods_have_bounded_metrics(
    monkeypatch: pytest.MonkeyPatch, is_auth_enabled: bool
) -> None:
    """Arbitrary URL and method values must collapse to fixed metric labels."""
    monkeypatch.setattr(api_module, "REQUEST_METRICS", api_module.RuntimeMetrics())
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(
            header_name="X-API-Key",
            api_keys={"agent": "secret"} if is_auth_enabled else {},
        ),
    )
    unknown_status = 401 if is_auth_enabled else 404
    birth_status = 401 if is_auth_enabled else 422
    with TestClient(api_module.app) as client:
        for index in range(2):
            unknown_path = f"/unknown-{index}"
            assert client.get(unknown_path).status_code == unknown_status
            assert (
                client.request(f"CUSTOM{index}", unknown_path).status_code
                == unknown_status
            )
            assert client.options(unknown_path).status_code == 404
        assert client.post("/api/bazi/birth-chart", json={}).status_code == birth_status
        metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    metric_lines = metrics_response.text.splitlines()
    assert {
        line
        for line in metric_lines
        if line.startswith("fatebridge_http_requests_total{")
    } == {
        f'fatebridge_http_requests_total{{method="GET",path="/unknown",status="{unknown_status}"}} 2.0',
        f'fatebridge_http_requests_total{{method="OTHER",path="/unknown",status="{unknown_status}"}} 2.0',
        'fatebridge_http_requests_total{method="OPTIONS",path="/unknown",status="404"} 2.0',
        f'fatebridge_http_requests_total{{method="POST",path="/api/bazi/birth-chart",status="{birth_status}"}} 1.0',
    }
    for metric_suffix in ("count", "sum"):
        metric_name = f"fatebridge_http_request_duration_seconds_{metric_suffix}"
        assert {
            line.partition(" ")[0]
            for line in metric_lines
            if line.startswith(f"{metric_name}{{")
        } == {
            f'{metric_name}{{method="GET",path="/unknown"}}',
            f'{metric_name}{{method="OTHER",path="/unknown"}}',
            f'{metric_name}{{method="OPTIONS",path="/unknown"}}',
            f'{metric_name}{{method="POST",path="/api/bazi/birth-chart"}}',
        }


def test_metrics_use_route_templates_before_routing_and_for_wrong_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolved and method-mismatch requests must record the same route template."""
    monkeypatch.setattr(api_module, "REQUEST_METRICS", api_module.RuntimeMetrics())
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api_module.app) as client:
        assert client.get("/api/tools/nonexistent").status_code == 404
        assert client.get("/api/bazi/birth-chart").status_code == 405
        metric_lines = client.get("/metrics").text.splitlines()
    assert (
        'fatebridge_http_requests_total{method="GET",path="/unknown",status="404"} 1.0'
        in metric_lines
    )
    assert (
        'fatebridge_http_requests_total{method="GET",path="/api/bazi/birth-chart",status="405"} 1.0'
        in metric_lines
    )


@pytest.mark.parametrize(
    "body",
    [
        "{}",
        '{"name":"sensitive-name","birth_year":"sensitive-value"}',
        '{"name":"sensitive-malformed-json",',
    ],
)
def test_invalid_http_bodies_use_safe_common_error_envelope(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api_module.app) as client:
        response = client.post(
            "/api/bazi/birth-chart",
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


@pytest.mark.parametrize("detail", ["private-detail", "standard", "compact", "audit"])
def test_invalid_http_detail_uses_safe_validation_error(
    rest: TestClient, detail: str
) -> None:
    """Removed detail query param is rejected with 422 without echoing raw input."""
    response = rest.post(
        "/api/divination/gua",
        params={"detail": detail},
        json={"queries": ["乾"]},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "validation_error"
    assert body["issues"][0]["path"] == "detail"
    assert body["issues"][0]["code"] == "extra_forbidden"
    assert body["issues"][0]["constraints"] == {
        "allowed_fields": ["include", "fields", "as_of"]
    }
    assert detail not in response.text

    batch_response = rest.post(
        "/api/batch",
        params={"detail": detail},
        json={
            "calls": [
                {"id": "c1", "tool": "gua_lookup", "arguments": {"queries": ["乾"]}}
            ]
        },
    )
    assert batch_response.status_code == 422
    assert batch_response.json()["error_code"] == "validation_error"
    assert detail not in batch_response.text

    openapi = rest.get("/openapi.json").json()
    calc_params = {
        param["name"]
        for param in openapi["paths"]["/api/divination/gua"]["post"].get(
            "parameters", []
        )
    }
    assert calc_params == {"include", "fields", "as_of"}
    tools_resp = rest.get("/api/tools", params={"detail": "brief"})
    assert tools_resp.status_code == 200


@pytest.mark.parametrize("has_explicit_path", [False, True])
def test_api_loads_dotenv_before_ephemeris_import(
    tmp_path: Path, has_explicit_path: bool
) -> None:
    """Native startup must see dotenv settings and respect an operator override."""
    pytest.importorskip("swisseph")
    env_path = tmp_path / ".env"
    dotenv_ephemeris_path = str(tmp_path / "dotenv-ephe")
    env_path.write_text(f"SE_EPHE_PATH={dotenv_ephemeris_path}\n", encoding="utf-8")
    process_environment = {**os.environ, "FATEBRIDGE_API_KEYS": ""}
    if has_explicit_path:
        expected_path = str(tmp_path / "explicit-ephe")
        process_environment["SE_EPHE_PATH"] = expected_path
    else:
        expected_path = dotenv_ephemeris_path
        process_environment.pop("SE_EPHE_PATH", None)
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
    result = subprocess.run(
        [sys.executable, "-c", script, str(env_path), expected_path],
        env=process_environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_openapi_validation_error_schema_matches_real_http_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_module,
        "API_KEY_AUTHENTICATOR",
        api_module.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api_module.app) as client:
        schema = client.get("/openapi.json").json()
        response = client.post("/api/bazi/birth-chart", json={})
    for routes in schema["paths"].values():
        for operation in routes.values():
            advertised = operation["responses"].get("422")
            if advertised:
                assert advertised["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorEnvelope"
                }
            else:
                pass
    error_schema = schema["components"]["schemas"]["ErrorEnvelope"]
    assert set(error_schema["required"]) <= set(response.json())
    assert set(response.json()) <= set(error_schema["properties"])
    assert response.status_code == 422
    assert ErrorEnvelope.model_validate(response.json()).model_dump(
        exclude_none=True
    ) == (response.json())
