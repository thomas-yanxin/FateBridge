"""Verified result readers preserve authentication, scope and event-loop isolation."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from tests.support.result_delivery import store


@pytest.fixture
def stored(store):
    payload = {
        "ziwei_birth": {"flag": False},
        "run_metadata": {"run_id": "original-run", "tool_name": "ziwei_birth"},
    }
    return store, payload, store.put(payload)


@pytest.mark.parametrize("bad", ["digest", "run"])
def test_all_transports_reject_storage_corruption_or_wrong_run(
    stored, monkeypatch, capsys, bad
):
    store, _, ref = stored
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    run_id = "other-run" if bad == "run" else "original-run"
    if bad == "digest":
        path = Path(ref["file_path"]).with_suffix(".meta")
        metadata = json.loads(path.read_text())
        metadata["sha256"] = "0" * 64
        path.write_text(json.dumps(metadata))
    response = TestClient(api.app).get(
        f"/api/results/{ref['result_id']}/verified",
        params=dict(expected_run_id=run_id),
    )
    assert response.status_code == 422
    assert run(["result-read", ref["result_id"], "--run-id", run_id]) == 1
    assert json.loads(capsys.readouterr().out)["retryable"] is False

    async def read():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            with pytest.raises(Exception):
                await client.read_resource(
                    f"fatebridge://results/{ref['result_id']}/verified/{run_id}/0"
                )

    asyncio.run(read())


def test_verified_resource_cannot_read_a_tool_hidden_by_mcp_scope(stored):
    _, _, ref = stored

    async def read():
        async with Client(create_mcp_app(families="fengshui")) as client:
            with pytest.raises(Exception, match="未在当前 MCP 配置中公开"):
                await client.read_resource(
                    f"fatebridge://results/{ref['result_id']}/verified/original-run/0"
                )

    asyncio.run(read())


def test_verified_rest_endpoint_keeps_api_authentication(stored, monkeypatch):
    _, _, ref = stored
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(
            header_name="X-API-Key", api_keys={"test": "fixture-secret"}
        ),
    )
    client = TestClient(api.app)
    url = f"/api/results/{ref['result_id']}/verified"
    params = dict(expected_run_id="original-run")
    assert client.get(url, params=params).status_code == 401
    assert (
        client.get(
            url, params=params, headers={"X-API-Key": "fixture-secret"}
        ).status_code
        == 200
    )


def test_verified_rest_integrity_check_runs_off_the_async_event_loop(
    stored, monkeypatch
):
    import threading

    store, _, ref = stored
    observed = []
    original = store.verified_page

    def record(*args, **kwargs):
        observed.append(threading.get_ident())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return original(*args, **kwargs)
        pytest.fail("Full-payload decoding/hash ran on the async request loop")

    monkeypatch.setattr(store, "verified_page", record)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).get(
        f"/api/results/{ref['result_id']}/verified",
        params=dict(
            expected_run_id="original-run",
            path="ziwei_birth.flag",
        ),
    )
    assert response.status_code == 200
    assert len(observed) == 1
