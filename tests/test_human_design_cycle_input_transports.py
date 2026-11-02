"""Real adapters preserve request clock decisions and runtime source failures."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.core.human_design_cycle_input as clocks
from fatebridge.cli import run
from fatebridge.core.astro import native_execution, runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "tests/fixtures/human-design-cycle-input-plan.json").read_text()
)


def setup_api(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )


async def mcp_call(params):
    async with Client(create_mcp_app(families="astro")) as client:
        result = await client.call_tool(
            "human_design", {**params, "response_char_limit": 0}, raise_on_error=False
        )
        return result.is_error, result.structured_content


def cli_call(params, capsys):
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    status = run(flags)
    return status, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("valid", [True, False])
def test_dirty_parent_uses_same_correct_real_three_surface_clock_decision(
    monkeypatch, capsys, valid
):
    setup_api(monkeypatch)
    original = clocks.validate_cycle_reference
    checks = []

    def dirty(**kwargs):
        runtime.swe.set_delta_t_userdef(0.1)
        try:
            return original(**kwargs)
        finally:
            try:
                assert runtime.swe.deltat_ex(2451545.0, runtime.swe.FLG_SWIEPH) == 0.1
                checks.append(True)
            finally:
                runtime.swe.set_delta_t_userdef(runtime.swe.DELTAT_AUTOMATIC)

    monkeypatch.setattr(clocks, "validate_cycle_reference", dirty)
    params = PLAN["cases"][0 if valid else 1]["input"]
    with TestClient(api.app) as client:
        rest = client.post("/api/astro/human-design", json=params)
    failed, mcp = asyncio.run(mcp_call(params))
    status, cli = cli_call(params, capsys)
    assert len(checks) >= 3
    if valid:
        assert rest.status_code == 200 and not failed and status == 0, (
            rest.text,
            mcp,
            cli,
        )
        outputs = [rest.json(), mcp, cli]
        for result in outputs:
            checked = verify_human_design_reading(result)
            assert checked["status"] == "verified_fixed_template_reading", checked
            assert (
                result["cycle_context"]["reference_jd_tt"]
                >= result["time_scales"]["personality"]["jd_tt"]
            )
            assert (
                result["native_execution_context"]["mechanism"] == "fresh_exec_process"
            )
            result.pop("run_metadata")
        assert outputs[0] == outputs[1] == outputs[2]
    else:
        assert rest.status_code == 422 and failed and status == 1
        for result in (rest.json(), mcp, cli):
            assert (
                result["error_code"] == "validation_error"
                and result["retryable"] is False
            )


@pytest.mark.parametrize(
    "filename", ["swe_deltat.txt", "sedeltat.txt", "seleapsec.txt"]
)
def test_real_preflight_auxiliary_change_is_source_503_on_all_adapters(
    tmp_path, monkeypatch, capsys, filename
):
    setup_api(monkeypatch)
    original = native_execution._receive
    current = None
    seen = []

    def receive(*args):
        result = original(*args)
        if result.get("kind") == "ready":
            (current / filename).write_text("# Created after request-clock snapshot\n")
            seen.append(True)
        return result

    monkeypatch.setattr(native_execution, "_receive", receive)
    params = PLAN["cases"][0]["input"]
    current = tmp_path / "rest"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    with TestClient(api.app) as client:
        rest = client.post("/api/astro/human-design", json=params)
    assert rest.status_code == 503, rest.text
    current = tmp_path / "mcp"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    failed, mcp = asyncio.run(mcp_call(params))
    assert failed
    current = tmp_path / "cli"
    current.mkdir()
    monkeypatch.setenv("SE_EPHE_PATH", str(current))
    status, cli = cli_call(params, capsys)
    assert status == 1 and seen == [True] * 3
    for result in (rest.json(), mcp, cli):
        assert result["error_code"] == "ephemeris_source_inconsistent"
        assert result["retryable"] is False
        assert result["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "auxiliary_changed_during"}
        ]
        assert str(tmp_path) not in json.dumps(result)
