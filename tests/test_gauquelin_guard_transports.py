"""Exercise live REST, MCP and CLI rejection before calculation is dispatched."""

import asyncio
import json

from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.cli as cli
from fatebridge.mcp_server import create_mcp_app
from tests.test_gauquelin_request_guard import HOUSE_SPECS, payload


def test_all_live_house_system_tools_reject_g_on_three_transports(
    monkeypatch, capsys, tmp_path
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("unsupported36-sector request reached calculation")

    monkeypatch.setattr("fatebridge.transports.rest.execute_tool", forbidden)
    monkeypatch.setattr("fatebridge.transports.mcp.execute_tool", forbidden)
    monkeypatch.setattr(cli, "execute_tool", forbidden)
    rest = TestClient(api.app)
    results = []

    async def exercise():
        async with Client(create_mcp_app()) as client:
            for index, spec in enumerate(HOUSE_SPECS):
                values = ("G", "gauquelin_sectors", "Ｇ")
                value = values[index % len(values)]
                request = {**payload(spec), "house_system": value}
                response = rest.post(spec.rest_path, json=request)
                subject = tmp_path / f"{spec.key}.json"
                subject.write_text(
                    json.dumps(
                        {k: v for k, v in request.items() if k != "house_system"}
                    )
                )
                capsys.readouterr()
                code = cli.run(
                    [
                        spec.tool_name,
                        "--subject-file",
                        str(subject),
                        "--house-system",
                        value,
                    ]
                )
                local = json.loads(capsys.readouterr().out)
                protocol = await client.call_tool(
                    spec.tool_name, request, raise_on_error=False
                )
                native = json.loads(protocol.content[0].text)
                assert (
                    response.status_code == 422 and code == 1 and protocol.is_error
                ), spec.key
                bodies = [response.json(), local, native]
                for error in bodies:
                    assert error["error_code"] == "validation_error", (spec.key, error)
                    assert error["retryable"] is False
                    assert "run_metadata" not in error
                    assert error["issues"][0]["path"] == "house_system", error
                    assert (
                        error["issues"][0]["code"] == "unsupported_house_system"
                    ), error
                    assert (
                        "36" in error["error"] and "Gauquelin" in error["error"]
                    ), error
                results.append(spec.key)

    asyncio.run(exercise())
    assert results == [s.key for s in HOUSE_SPECS]
