"""Actual reference byte changes retain safe failure semantics on all adapters."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import human_design_references as refs
from fatebridge.mcp_server import create_mcp_app

PARAMS = dict(
    birth_year=1988,
    birth_month=3,
    birth_day=18,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="Europe/London",
)
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.native_engine_fault
@pytest.mark.parametrize(
    "fault", ["changed", "changed_cache_clear", "cold_unreviewed", "missing", "invalid"]
)
def test_reference_fault_errors_agree_on_rest_mcp_cli(
    tmp_path, monkeypatch, capsys, fault
):
    private = tmp_path / "human_design"
    private.mkdir()
    for name in refs.REFERENCE_NAMES:
        shutil.copy2(ROOT / "src/fatebridge/data/human_design" / name, private / name)
    monkeypatch.setattr(refs, "files", lambda _: tmp_path)
    path = private / "profile-2026-reference.json"
    original = path.read_bytes()
    read_data = refs.reference_data

    def changed(name):
        value = read_data(name)
        if name == path.name and fault.startswith("changed"):
            path.write_bytes(original + b"\n")
            if fault == "changed_cache_clear":
                refs.clear_reference_cache()
        return value

    monkeypatch.setattr(refs, "reference_data", changed)
    # Reader modules bind this imported function; preserve all other source paths.
    from fatebridge.core import human_design_profile

    monkeypatch.setattr(human_design_profile, "reference_data", changed)

    def reset():
        refs.clear_reference_cache()
        path.write_bytes(original)
        if fault == "cold_unreviewed":
            path.write_bytes(original + b"\n")
        elif fault == "missing":
            path.unlink()
        elif fault == "invalid":
            path.write_bytes(b"invalid")

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    reset()
    with TestClient(api.app) as client:
        response = client.post("/api/astro/human-design", json=PARAMS)
    assert response.status_code == 503, response.text
    rest = response.json()

    async def call():
        reset()
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", PARAMS, raise_on_error=False
            )
            assert result.is_error
            return result.structured_content

    native = asyncio.run(call())
    reset()
    flags = [
        "human_design",
        *[
            "--" + key.replace("_", "-") + "=" + str(value)
            for key, value in PARAMS.items()
        ],
    ]
    assert run(flags) == 1
    cli = json.loads(capsys.readouterr().out)
    reason = {
        "changed": "changed",
        "changed_cache_clear": "changed",
        "cold_unreviewed": "identity_mismatch",
        "missing": "unavailable",
        "invalid": "invalid",
    }[fault]
    for result in (rest, native, cli):
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {
                "path": "runtime.ephemeris_data",
                "code": "human_design_reference_" + reason,
            }
        ]
        assert str(tmp_path) not in json.dumps(result)
        assert "interpretation" not in result
