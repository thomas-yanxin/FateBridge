"""Verified result readers preserve authentication, scope and event-loop isolation."""

import asyncio
import json
import threading
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from mcp import MCPError

import fatebridge.api as api
from fatebridge.application import result_delivery as delivery
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from tests.support.result_delivery import store
from tests.support.transports import cached_mcp_app


class StoredResult(NamedTuple):
    store: delivery.ResultStore
    payload: ServiceResult
    reference: ServiceResult


@pytest.fixture
def stored(store: delivery.ResultStore) -> StoredResult:
    payload = {
        "ziwei_birth": {"flag": False},
        "run_metadata": {"run_id": "original-run", "tool_name": "ziwei_birth_chart"},
    }
    return StoredResult(store, payload, store.put(payload))


@pytest.mark.parametrize("bad", ["digest", "run"])
def test_all_transports_reject_storage_corruption_or_wrong_run(
    stored: StoredResult,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    bad: str,
) -> None:
    store, _, ref = stored
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    run_id = "other-run" if bad == "run" else "original-run"
    if bad == "digest":
        path = Path(ref["file_path"])
        record = json.loads(path.read_text(encoding="utf-8"))
        record["payload"]["ziwei_birth"]["flag"] = True
        path.write_text(json.dumps(record), encoding="utf-8")
    else:
        pass
    response = TestClient(api.app).get(
        f"/api/results/{ref['result_id']}/verified",
        params=dict(expected_run_id=run_id),
    )
    assert response.status_code == 422
    assert run(["result-read", ref["result_id"], "--run-id", run_id]) == 1
    assert json.loads(capsys.readouterr().out)["retryable"] is False

    async def read() -> None:
        async with Client(cached_mcp_app(families="metaphysics")) as client:
            with pytest.raises(MCPError):
                await client.read_resource(
                    f"fatebridge://results/{ref['result_id']}/verified/{run_id}/0"
                )

    asyncio.run(read())


@pytest.mark.parametrize("tool_name", ["ziwei_birth_chart", ["ziwei_birth_chart"]])
def test_verified_resource_rejects_hidden_or_malformed_tool_identity(
    store: delivery.ResultStore, tool_name: str | list[str]
) -> None:
    """A malformed retained tool name is denied with the normal scope error."""
    ref = store.put(
        {"run_metadata": {"run_id": "original-run", "tool_name": tool_name}}
    )

    async def read() -> None:
        async with Client(cached_mcp_app(families="fengshui")) as client:
            with pytest.raises(MCPError, match="未在当前 MCP 配置中公开"):
                await client.read_resource(
                    f"fatebridge://results/{ref['result_id']}/verified/original-run/0"
                )

    asyncio.run(read())


def test_verified_rest_endpoint_keeps_api_authentication(
    stored: StoredResult, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_rest_exports_original_payload_in_one_authenticated_read(
    stored: StoredResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, payload, ref = stored
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={"test": "secret"}),
    )
    original = store._record
    reads = []

    def record(result_id: str) -> delivery.RetainedResult:
        reads.append(result_id)
        return original(result_id)

    url = store.manifest(ref["result_id"])["rest_export_path"]
    monkeypatch.setattr(store, "_record", record)
    client = TestClient(api.app)
    assert client.get(url).status_code == 401
    response = client.get(url, headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert response.json() == payload
    assert reads == [ref["result_id"]]


def test_verified_rest_integrity_check_runs_off_the_async_event_loop(
    stored: StoredResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _, ref = stored
    observed = []
    original = store.verified_page

    def record(
        result_id: str, expected_run_id: str, offset: int, path: str | None
    ) -> ServiceResult:
        observed.append(threading.get_ident())
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return original(result_id, expected_run_id, offset, path)
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
