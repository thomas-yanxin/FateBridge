"""REST, MCP and CLI verify the same retained numerology snapshot."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from tests.test_readonly_result_verification import PAYLOADS, REFERENCE, forbidden


@pytest.mark.parametrize("tool", ["canping", "heluo"])
def test_all_verified_transports_preserve_frozen_payload_without_lock_writes(
    tool, tmp_path, monkeypatch, capsys
):
    case = next(c for c in REFERENCE["cases"] if c["tool"] == tool)
    payload = PAYLOADS[case["id"]]
    store = delivery.ResultStore(tmp_path / "private")
    ref = store.put(payload)
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    monkeypatch.setattr(store, "_locked", forbidden)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    path = "numerology_evidence.birth_clock"
    run_id = payload["run_metadata"]["run_id"]
    response = TestClient(api.app).get(
        f"/api/results/{ref['result_id']}/verified",
        params={
            "expected_sha256": ref["sha256"],
            "expected_run_id": run_id,
            "path": path,
        },
    )
    assert response.status_code == 200, response.text
    assert (
        run(
            [
                "result-read",
                ref["result_id"],
                "--sha256",
                ref["sha256"],
                "--run-id",
                run_id,
                "--path",
                path,
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)

    async def read():
        async with Client(
            create_mcp_app(scenarios="onda-xingpan", tool_scope="topic")
        ) as client:
            uri = f"fatebridge://results/{ref['result_id']}/verified/{run_id}/{ref['sha256']}/fields/{path}/0"
            return json.loads((await client.read_resource(uri))[0].text)

    native = asyncio.run(read())
    assert (
        native
        == cli
        == response.json()
        == store.verified_page(ref["result_id"], ref["sha256"], run_id, path=path)
    )
