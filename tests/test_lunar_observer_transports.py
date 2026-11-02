"""New observer integrity errors survive public protocols and real workers."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import lunar_observer
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import build_india
from fatebridge.mcp_server import create_mcp_app
from fatebridge.utils.errors import EphemerisSourceError
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_sources import restore_runtime  # noqa: F401
from tests.test_jyotish_transports import SPECS

REASONS = ["observer_source_window_incoherent", "lunar_motion_center_not_reproduced"]


@pytest.mark.native_engine_fault
@pytest.mark.parametrize("reason", REASONS)
@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_observer_integrity_failures_are_safe_internal_errors_on_all_surfaces(
    reason, key, monkeypatch, capsys, tmp_path
):
    root = Path(__file__).resolve().parents[1]
    e.configure_ephemeris_path(str(root / "ephe"))
    monkeypatch.setenv("SE_EPHE_PATH", str(root / "ephe"))

    def fail(*args, **kwargs):
        raise EphemerisSourceError(reason)

    monkeypatch.setattr(lunar_observer, "fixed_frame_source_remainder", fail)
    payload = {
        **astro_payload(),
        "divisions": [],
        "birth_time_uncertainty_minutes": 0,
        "ephemeris_policy": "require_data_files",
    }
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    spec = SPECS[key]
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = TestClient(api.app).post(spec.rest_path, json=payload)

    async def protocol():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(spec.tool_name, payload, raise_on_error=False)

    native = asyncio.run(protocol())
    capsys.readouterr()
    code = run([spec.tool_name, "--subject-file", str(request)])
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 503 and native.is_error and code == 1
    for body in [rest.json(), json.loads(native.content[0].text), cli]:
        assert body["error_code"] == "ephemeris_source_inconsistent"
        assert body["retryable"] is False
        assert body["issues"] == [{"path": "runtime.ephemeris_data", "code": reason}]
        assert "india" not in body and str(tmp_path) not in json.dumps(body)


@pytest.mark.parametrize("reason", REASONS)
def test_real_native_child_transports_new_integrity_reason_and_is_reaped(
    reason, monkeypatch
):
    from fatebridge.core.astro import native_execution as execution

    root = Path(__file__).resolve().parents[1]
    e.configure_ephemeris_path(str(root / "ephe"))
    bootstrap = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0,{str(root/'src')!r})",
            "from fatebridge.core.astro import lunar_observer, _native_worker",
            "from fatebridge.utils.errors import EphemerisSourceError",
            "def fail(*args,**kwargs):",
            f"    raise EphemerisSourceError({reason!r})",
            "lunar_observer.fixed_frame_source_remainder=fail",
            "_native_worker.main()",
        ]
    )
    original = execution.subprocess.Popen
    children = []

    def started(args, *a, **kw):
        process = original([sys.executable, "-I", "-c", bootstrap], *a, **kw)
        children.append(process)
        return process

    monkeypatch.setattr(execution.subprocess, "Popen", started)
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
        preserve_instant=True,
    )
    with pytest.raises(EphemerisSourceError) as error:
        build_india(birth, divisions=[], ephemeris_policy="require_data_files")
    assert error.value.reason == reason
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed
