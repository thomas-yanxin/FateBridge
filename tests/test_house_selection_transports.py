"""Same typed invalid selection is rejected by REST, native MCP and CLI JSON."""

import asyncio
import json

from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.cli as cli
from fatebridge.application.description import spec_is_cli_safe
from fatebridge.mcp_server import create_mcp_app
from tests.test_house_selection_contract import CODE_SPECS, HOUSE_SPECS, inputs


def test_all_selector_endpoints_reject_invalid_input_before_any_calculation(
    monkeypatch, tmp_path, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid house selection reached calculation")

    monkeypatch.setattr("fatebridge.transports.rest.execute_tool", forbidden)
    monkeypatch.setattr("fatebridge.transports.mcp.execute_tool", forbidden)
    monkeypatch.setattr(cli, "execute_tool", forbidden)
    rest = TestClient(api.app)
    seen = []

    async def run():
        async with Client(create_mcp_app()) as client:
            available_tools = {tool.name for tool in await client.list_tools()}
            for field, specs, issue_code in (
                ("house_system", HOUSE_SPECS, "invalid_house_system"),
                ("hsys", CODE_SPECS, "invalid_house_code"),
            ):
                for i, spec in enumerate(specs):
                    value = [True, 99, 3.7, "unknown-name", " "][i % 5]
                    body = {**inputs(spec), field: value}
                    results = []
                    if spec.rest_path is not None:
                        response = rest.post(spec.rest_path, json=body)
                        assert response.status_code == 422, spec.key
                        results.append(response.json())
                    path = tmp_path / f"{field}-{spec.key}.json"
                    path.write_text(json.dumps(body))
                    capsys.readouterr()
                    cli_available = spec_is_cli_safe(spec)
                    code = cli.run(
                        [
                            spec.tool_name,
                            (
                                "--request-file"
                                if spec.cli_request_file
                                else "--subject-file"
                            ),
                            str(path),
                        ]
                        if cli_available
                        else [spec.tool_name]
                    )
                    local = json.loads(capsys.readouterr().out)
                    if cli_available:
                        assert code == 1, spec.key
                        results.append(local)
                    else:
                        assert (
                            code == 2 and local["error_code"] == "cli_unsupported"
                        ), spec.key
                    if spec.mcp_name is not None:
                        assert spec.tool_name in available_tools
                        native = await client.call_tool(
                            spec.tool_name, body, raise_on_error=False
                        )
                        assert native.is_error, spec.key
                        results.append(json.loads(native.content[0].text))
                    else:
                        # Retain the REST/CLI case; a REST-only compatibility
                        # alias must not be tested as an invented MCP tool.
                        assert spec.tool_name not in available_tools
                    assert results, spec.key
                    for result in results:
                        assert result["issues"][0] == {
                            "path": field,
                            "code": issue_code,
                        }, (spec.key, result)
                        assert (
                            result["retryable"] is False
                            and "run_metadata" not in result
                        )
                    seen.append((field, spec.key))

    asyncio.run(run())
    assert seen == [
        (f, s.key)
        for f, ss in (("house_system", HOUSE_SPECS), ("hsys", CODE_SPECS))
        for s in ss
    ]
