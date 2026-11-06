"""Complete execution must produce business roots; projections may omit them."""

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.application import execution
from fatebridge.application.description import describe_spec
from fatebridge.application.examples import example_input
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.services.tool_catalog import CATALOG


def career_spec():
    return next(spec for spec in CATALOG if spec.key == "bazi_career")


def test_every_catalog_tool_declares_real_complete_business_roots():
    for spec in CATALOG:
        assert spec.required_output_fields, spec.key
        assert set(spec.required_output_fields) <= set(spec.output_model.model_fields)
        assert not set(spec.required_output_fields) & {
            "run_metadata",
            "snapshot_text",
            "result_delivery",
        }
        assert describe_spec(spec)["full_result_required_fields"] == list(
            spec.required_output_fields
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"analysis_type": "bazi_career"},
        {"career_analysis": None},
        {"error": None},
        {"error": "private missing error envelope"},
        {"error": "private malformed error", "error_code": "", "retryable": False},
        {"error": None, "error_code": "validation_error", "retryable": False},
    ],
)
def test_missing_or_null_business_output_is_correlated_internal_error(payload):
    spec = career_spec()
    broken = replace(spec, bind=lambda _: (lambda: payload, (), {}))
    request = spec.request_model.model_validate(example_input(spec))
    with pytest.raises(execution.OutputContractError):
        execution.execute_spec(broken, request)
    result = execution.execute_tool(
        broken,
        request,
        options=ExecutionOptions(trace_id="output-guard", parent_run_id="parent"),
    )
    assert result["error_code"] == "internal_error"
    assert result["trace_id"] == "output-guard"
    assert result["parent_run_id"] == "parent"
    assert "run_metadata" not in result
    assert "private" not in json.dumps(result)


def test_error_result_does_not_require_success_business_roots():
    spec = career_spec()
    failure = {
        "error": "synthetic dependency failure",
        "error_code": "dependency_missing",
        "status_code": 503,
        "retryable": False,
    }
    broken = replace(spec, bind=lambda _: (lambda: failure, (), {}))
    result = execution.execute_tool(
        broken, spec.request_model.model_validate(example_input(spec))
    )
    assert result == failure


def test_missing_root_and_legal_projection_across_rest_mcp_cli(monkeypatch, capsys):
    import fatebridge.api as api
    import fatebridge.cli as cli
    from fatebridge.mcp_server import app as mcp_app

    spec = career_spec()
    inputs = example_input(spec)
    controls = {"trace_id": "missing-root", "parent_run_id": "original-run"}
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)

    async def protocol(arguments):
        async with Client(mcp_app) as connection:
            return await connection.call_tool(
                "bazi_career",
                {"response_char_limit": 0, **inputs, **arguments},
                raise_on_error=False,
            )

    argv = ["bazi_career"]
    for name, value in inputs.items():
        argv += ["--" + name.replace("_", "-"), str(value)]
    for name, value in controls.items():
        argv += ["--" + name.replace("_", "-"), value]

    # The real service still executes and validates before projection. Omitting
    # its primary business root from the wire output remains legitimate.
    projected = {**controls, "fields": ["analysis_type"], "strict_fields": True}
    http = client.post(spec.rest_path, json=inputs, params=projected)
    native = asyncio.run(protocol(projected))
    assert http.status_code == 200 and not native.is_error
    assert "career_analysis" not in http.json()
    assert "career_analysis" not in native.structured_content
    assert cli.run(argv + ["--fields", "analysis_type", "--strict-fields"]) == 0
    assert "career_analysis" not in json.loads(capsys.readouterr().out)

    original = execution.execute_spec

    def corrupt_service(current, request):
        broken = replace(current, bind=lambda _: (lambda: {}, (), {}))
        return original(broken, request)

    monkeypatch.setattr(execution, "execute_spec", corrupt_service)
    http = client.post(spec.rest_path, json=inputs, params=controls)
    native = asyncio.run(protocol(controls))
    assert http.status_code == 500 and native.is_error
    assert cli.run(argv) == 1
    outputs = [
        http.json(),
        native.structured_content,
        json.loads(capsys.readouterr().out),
    ]
    for result in outputs:
        assert result["error_code"] == "internal_error"
        assert result["trace_id"] == controls["trace_id"]
        assert result["parent_run_id"] == controls["parent_run_id"]
