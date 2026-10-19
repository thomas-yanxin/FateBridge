"""Discovery cannot offer budgets that the shared renderer refuses."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.api import app as rest_app
from fatebridge.application.result_delivery import bound_response
from fatebridge.mcp_server import create_mcp_app
from fatebridge.mcp_transport import OutputFlags
from fatebridge.utils.errors import ParameterError


def test_rest_mcp_flags_and_renderer_agree_on_disjoint_response_budget():
    async def schema():
        async with Client(create_mcp_app(families="bazi")) as client:
            tools = await client.list_tools()
            career = next(tool for tool in tools if tool.name == "bazi_career")
            return career.input_schema["properties"]["response_char_limit"]

    mcp_schema = asyncio.run(schema())
    rest_schema = next(
        parameter["schema"]
        for parameter in rest_app.openapi()["paths"]["/api/cn/bazi/career"]["post"][
            "parameters"
        ]
        if parameter["name"] == "response_char_limit"
    )
    validators = [Draft202012Validator(s) for s in (rest_schema, mcp_schema)]
    for value in [0, 4096, 8192, 65536]:
        assert all(validator.is_valid(value) for validator in validators)
        assert OutputFlags(response_char_limit=value).response_char_limit == value
        assert bound_response({"status": "small"}, value) == {"status": "small"}
    for value in [-1, 1, 4095, 65537]:
        assert not any(validator.is_valid(value) for validator in validators)
        with pytest.raises(ValidationError):
            OutputFlags(response_char_limit=value)
        with pytest.raises(ParameterError):
            bound_response({"status": "small"}, value)


def test_explicit_zero_http_budget_and_invalid_budget_before_execution(monkeypatch):
    import fatebridge.api as api
    from fatebridge.application.examples import example_input
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.transports import rest

    spec = next(spec for spec in CATALOG if spec.key == "bazi_career")
    inputs = example_input(spec)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    for value in [0, 4096, 65536]:
        response = client.post(
            spec.rest_path, json=inputs, params={"response_char_limit": value}
        )
        assert response.status_code == 200, response.json()
        assert "error" not in response.json()
        if value == 0:
            assert "career_analysis" in response.json()
            assert "result_delivery" not in response.json()

    def must_not_execute(*args, **kwargs):
        pytest.fail("invalid HTTP budget must fail before domain execution")

    monkeypatch.setattr(rest, "execute_tool", must_not_execute)
    for value in [1, 4095, 65537, "invalid"]:
        response = client.post(
            spec.rest_path, json=inputs, params={"response_char_limit": value}
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "validation_error"
