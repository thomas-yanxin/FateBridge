"""A real mid-batch asteroid byte change has safe semantics on all surfaces."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import human_design_cycles as cycles
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app


@pytest.mark.native_engine_fault
def test_actual_changed_asteroid_returns_a_nonretryable_source_error_on_three_surfaces(
    tmp_path, monkeypatch, capsys
):
    # Do not hold the native lock across yield/HTTP requests: TestClient calls
    # the service on a different thread. Only private disposable copies change.
    private_ephemeris = tmp_path / "ephe"
    private_ephemeris.mkdir()
    root = Path(__file__).resolve().parents[1]
    for name in ("sepl_18.se1", "semo_18.se1", "seas_18.se1"):
        shutil.copy2(root / "ephe" / name, private_ephemeris / name)
        (private_ephemeris / name).chmod(0o644)
    monkeypatch.setenv("SE_EPHE_PATH", str(private_ephemeris))
    monkeypatch.setattr(cycles, "HORIZON_DAYS", 8.0)
    original = runtime.ephemeris_call
    path = private_ephemeris / "seas_18.se1"
    original_bytes = path.read_bytes()
    count = 0

    def reset():
        nonlocal count
        path.write_bytes(original_bytes)
        count = 0

    def native(operation, *args, **kwargs):
        nonlocal count
        result = original(operation, *args, **kwargs)
        if operation == "calc" and args[1] == 15:
            count += 1
            if count == 2:
                with path.open("ab") as handle:
                    handle.write(b"actual-transport-source-change")
        return result

    monkeypatch.setattr(runtime, "ephemeris_call", native)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        require_swiss_files=True,
        cycle_reference_datetime="2050-01-01T00:00:00Z",
    )
    reset()
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=params)
    assert response.status_code == 503
    rest = response.json()

    async def call():
        reset()
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", params, raise_on_error=False
            )
            assert result.is_error
            return result.structured_content

    native_result = asyncio.run(call())
    reset()
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 1
    cli = json.loads(capsys.readouterr().out)
    for result in (rest, native_result, cli):
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "changed_during"}
        ]
        assert str(private_ephemeris) not in json.dumps(result)
